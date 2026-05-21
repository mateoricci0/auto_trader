"""
Gestiona posiciones abiertas y ejecuta órdenes en Binance testnet.
Entrada: orden MARKET. SL + TP: orden OCO (cancela automáticamente al tocar uno).
Las posiciones se rastrean en bot_state.json — ignora balances iniciales del testnet.
"""
import logging
import math

from binance.client import Client
from binance.exceptions import BinanceAPIException

from . import state
from . import config as _cfg
from .config import DAILY_LOSS_LIMIT, MAX_OPEN_POSITIONS, MAX_POSITION_PCT, RISK_PER_TRADE
from .scanner import Signal

logger = logging.getLogger(__name__)


def _get_balance_usdt(client: Client) -> float:
    account = client.get_account()
    for asset in account["balances"]:
        if asset["asset"] == "USDT":
            return float(asset["free"])
    return 0.0


def _get_step_size(client: Client, pair: str) -> tuple[float, float]:
    info = client.get_symbol_info(pair)
    for f in info["filters"]:
        if f["filterType"] == "LOT_SIZE":
            return float(f["stepSize"]), float(f["minQty"])
    return 0.00001, 0.00001


def _round_qty(quantity: float, step_size: float) -> float:
    precision = int(round(-math.log10(step_size)))
    return round(math.floor(quantity / step_size) * step_size, precision)


def _round_price(price: float, tick_size: float) -> str:
    precision = int(round(-math.log10(tick_size)))
    return f"{round(price, precision):.{precision}f}"


def _get_tick_size(client: Client, pair: str) -> float:
    info = client.get_symbol_info(pair)
    for f in info["filters"]:
        if f["filterType"] == "PRICE_FILTER":
            return float(f["tickSize"])
    return 0.01


def _is_oco_active(client: Client, pair: str) -> bool:
    """True si hay órdenes OCO abiertas para este par (posición aún activa)."""
    try:
        open_orders = client.get_open_orders(symbol=pair)
        return len(open_orders) > 0
    except Exception as exc:
        logger.warning("No se pudo comprobar órdenes abiertas en %s: %s", pair, exc)
        return True  # conservador: asumir activa si hay error


def _get_exit_price(client: Client, pair: str) -> float | None:
    """Obtiene el precio real de cierre de la última orden de venta ejecutada."""
    try:
        trades = client.get_my_trades(symbol=pair, limit=10)
        for trade in reversed(trades):
            if not trade["isBuyer"]:   # es una venta → cierre de posición
                return float(trade["price"])
    except Exception as exc:
        logger.warning("No se pudo obtener precio de cierre de %s: %s", pair, exc)
    return None


def get_open_positions(client: Client) -> dict[str, dict]:
    """
    Devuelve posiciones activas. Cuando una OCO se ejecuta, calcula el P&L real
    consultando el historial de trades de Binance y lo registra en el estado.
    """
    tracked = state.get_positions()
    active  = {}

    for pair, pos in tracked.items():
        if _is_oco_active(client, pair):
            try:
                ticker = client.get_symbol_ticker(symbol=pair)
                price  = float(ticker["price"])
            except Exception:
                price = pos["entry_price"]

            unrealized = (price - pos["entry_price"]) * pos["qty"]
            sign = "+" if unrealized >= 0 else ""
            active[pair] = {
                "qty":         pos["qty"],
                "entry_price": pos["entry_price"],
                "current_price": price,
                "value_usdt":  pos["qty"] * price,
                "unrealized":  unrealized,
                "unrealized_str": f"{sign}{unrealized:.2f} USDT",
            }
        else:
            # OCO ejecutada → buscar precio real de salida
            exit_price = _get_exit_price(client, pair)
            entry      = pos["entry_price"]
            qty        = pos["qty"]

            if exit_price:
                pnl = (exit_price - entry) * qty
            else:
                # Fallback: inferir por precio actual
                try:
                    ticker     = client.get_symbol_ticker(symbol=pair)
                    exit_price = float(ticker["price"])
                except Exception:
                    exit_price = entry
                pnl = (exit_price - entry) * qty

            state.record_closed_trade(pair, entry, exit_price, qty, pnl)
            state.remove_position(pair)

    return active


def enter_position(client: Client, signal: Signal) -> bool:
    """
    Entra en una posición: BUY market + OCO sell (SL + TP).
    Devuelve True si la entrada fue exitosa.
    """
    balance = _get_balance_usdt(client)
    # Operar solo con _cfg.TRADING_CAPITAL (el presupuesto asignado), no con todo el saldo
    capital = min(_cfg.TRADING_CAPITAL, balance)
    if balance < 10:
        logger.warning("Saldo USDT insuficiente: %.2f", balance)
        return False

    step_size, min_qty = _get_step_size(client, signal.pair)
    tick_size = _get_tick_size(client, signal.pair)

    risk_usdt     = capital * RISK_PER_TRADE
    risk_per_unit = signal.price - signal.sl
    if risk_per_unit <= 0:
        logger.warning("SL >= precio de entrada en %s — skip", signal.pair)
        return False

    # Tamaño por riesgo, limitado al MAX_POSITION_PCT del capital asignado
    qty_by_risk = risk_usdt / risk_per_unit
    qty_by_cap  = (capital * MAX_POSITION_PCT) / signal.price
    quantity    = _round_qty(min(qty_by_risk, qty_by_cap), step_size)

    if quantity < min_qty:
        logger.warning("%s: cantidad %.6f < mínimo %.6f — skip", signal.pair, quantity, min_qty)
        return False

    cost_usdt = quantity * signal.price
    if cost_usdt > balance * 0.99:
        logger.warning("%s: coste %.2f USDT supera el saldo disponible — skip", signal.pair, cost_usdt)
        return False

    tp_pct = (signal.tp - signal.price) / signal.price * 100
    sl_pct = (signal.price - signal.sl) / signal.price * 100
    gain_est = (signal.tp - signal.price) * quantity
    logger.info("%s | capital=%.0f USDT | riesgo=%.2f USDT | ganancia potencial=+%.2f USDT (TP +%.2f%% / SL -%.2f%%)",
                signal.pair, capital, risk_usdt, gain_est, tp_pct, sl_pct)

    try:
        buy_order = client.order_market_buy(symbol=signal.pair, quantity=quantity)
        logger.info("COMPRA %s | qty=%.6f | precio≈%.4f", signal.pair, quantity, signal.price)

        tp_price = _round_price(signal.tp,         tick_size)
        sl_price = _round_price(signal.sl,         tick_size)
        sl_limit = _round_price(signal.sl * 0.999, tick_size)

        # Nueva API de Binance: orderList/oco con aboveType/belowType
        client._post("orderList/oco", True, data={
            "symbol":            signal.pair,
            "side":              "SELL",
            "quantity":          str(quantity),
            "aboveType":         "LIMIT_MAKER",
            "abovePrice":        tp_price,
            "belowType":         "STOP_LOSS_LIMIT",
            "belowStopPrice":    sl_price,
            "belowPrice":        sl_limit,
            "belowTimeInForce":  "GTC",
        })
        logger.info("OCO colocado %s | TP=%s SL=%s", signal.pair, tp_price, sl_price)

        # Registrar la posición en el estado local
        state.add_position(signal.pair, quantity, signal.price, signal.sl, signal.tp)
        return True

    except BinanceAPIException as exc:
        logger.error("Error al operar %s: %s", signal.pair, exc)
        return False


def close_all_positions(client: Client) -> None:
    """
    Cancela todas las OCOs abiertas y vende a mercado todas las posiciones rastreadas.
    Usado al arrancar (limpiar sesión anterior) o al salir con Ctrl+C.
    """
    tracked = state.get_positions()
    if not tracked:
        logger.info("No hay posiciones abiertas que cerrar.")
        return

    logger.info("Cerrando %d posición(es)...", len(tracked))
    for pair, pos in list(tracked.items()):
        # 1. Cancelar órdenes abiertas una a una (cancel_open_orders no existe en esta versión)
        try:
            open_orders = client.get_open_orders(symbol=pair)
            for order in open_orders:
                try:
                    client.cancel_order(symbol=pair, orderId=order["orderId"])
                except Exception:
                    pass
            if open_orders:
                logger.info("Órdenes canceladas: %s (%d)", pair, len(open_orders))
        except Exception as exc:
            logger.warning("No se pudieron cancelar órdenes de %s: %s", pair, exc)

        # 2. Comprobar saldo real del activo antes de vender
        step_size, min_qty = _get_step_size(client, pair)
        base = pair.replace("USDT", "")
        try:
            account  = client.get_account()
            balances = {b["asset"]: float(b["free"]) for b in account["balances"]}
            real_qty = _round_qty(balances.get(base, 0.0), step_size)
        except Exception:
            real_qty = 0.0

        if real_qty < min_qty:
            # OCO ya se ejecutó sola — solo limpiar estado
            logger.info("%s: OCO ya ejecutada, limpiando estado.", pair)
            exit_price = _get_exit_price(client, pair) or pos["entry_price"]
            pnl = (exit_price - pos["entry_price"]) * pos["qty"]
            state.record_closed_trade(pair, pos["entry_price"], exit_price, pos["qty"], pnl)
            state.remove_position(pair)
            continue

        # 3. Vender a mercado
        try:
            client.order_market_sell(symbol=pair, quantity=real_qty)
            logger.info("VENTA MERCADO %s | qty=%.6f", pair, real_qty)
            try:
                ticker     = client.get_symbol_ticker(symbol=pair)
                exit_price = float(ticker["price"])
            except Exception:
                exit_price = pos["entry_price"]
            pnl = (exit_price - pos["entry_price"]) * real_qty
            state.record_closed_trade(pair, pos["entry_price"], exit_price, real_qty, pnl)
        except Exception as exc:
            logger.error("Error vendiendo %s: %s", pair, exc)

        state.remove_position(pair)

    logger.info("Todas las posiciones cerradas.")


def run_cycle(client: Client, signals: list[Signal]) -> None:
    """
    Ejecuta un ciclo completo:
    - Comprueba límite de pérdida diaria
    - Verifica posiciones propias y cierra las ya ejecutadas
    - Entra en las mejores señales hasta llenar MAX_OPEN_POSITIONS
    """
    balance = _get_balance_usdt(client)
    capital = min(_cfg.TRADING_CAPITAL, balance)
    state.init_daily(balance)

    if state.check_daily_limit(balance, DAILY_LOSS_LIMIT):
        logger.warning("Bot en pausa por límite de pérdida diaria. Reintentará mañana.")
        return

    open_pos = get_open_positions(client)
    n_open   = len(open_pos)

    logger.info("Posiciones abiertas (propias): %d/%d | Capital operativo: %.2f USDT",
                n_open, MAX_OPEN_POSITIONS, capital)
    for pair, pos in open_pos.items():
        logger.info("  %s: %.6f (≈%.2f USDT) | entrada=%.4f",
                    pair, pos["qty"], pos["value_usdt"], pos["entry_price"])

    if n_open >= MAX_OPEN_POSITIONS:
        logger.info("Máximo de posiciones alcanzado. Esperando cierre.")
        return

    slots   = MAX_OPEN_POSITIONS - n_open
    entered = 0

    for signal in signals:
        if entered >= slots:
            break
        if signal.pair in open_pos:
            logger.info("Ya en posición en %s — skip", signal.pair)
            continue
        ok = enter_position(client, signal)
        if ok:
            state.record_trade()
            entered += 1

    if entered == 0 and signals:
        logger.info("Señales encontradas pero ninguna ejecutada.")
    elif not signals:
        logger.info("Sin señales en este ciclo.")
