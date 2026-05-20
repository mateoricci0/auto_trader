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
from .config import MAX_OPEN_POSITIONS, RISK_PER_TRADE
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


def get_open_positions(client: Client) -> dict[str, dict]:
    """
    Devuelve posiciones que el bot abrió y que siguen activas (OCO pendiente).
    Elimina del estado las que ya se cerraron (SL o TP alcanzado).
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
            active[pair] = {
                "qty":        pos["qty"],
                "entry_price": pos["entry_price"],
                "value_usdt": pos["qty"] * price,
            }
        else:
            # OCO ya ejecutada → posición cerrada
            pnl_est = (pos.get("tp", 0) + pos.get("sl", 0)) / 2  # solo log
            logger.info("Posición cerrada (SL/TP alcanzado): %s", pair)
            state.remove_position(pair)

    return active


def enter_position(client: Client, signal: Signal) -> bool:
    """
    Entra en una posición: BUY market + OCO sell (SL + TP).
    Devuelve True si la entrada fue exitosa.
    """
    balance = _get_balance_usdt(client)
    if balance < 10:
        logger.warning("Saldo USDT insuficiente: %.2f", balance)
        return False

    step_size, min_qty = _get_step_size(client, signal.pair)
    tick_size = _get_tick_size(client, signal.pair)

    risk_usdt     = balance * RISK_PER_TRADE
    risk_per_unit = signal.price - signal.sl
    if risk_per_unit <= 0:
        logger.warning("SL >= precio de entrada en %s — skip", signal.pair)
        return False

    quantity = _round_qty(risk_usdt / risk_per_unit, step_size)
    if quantity < min_qty:
        logger.warning("%s: cantidad %.6f < mínimo %.6f — skip", signal.pair, quantity, min_qty)
        return False

    try:
        buy_order = client.order_market_buy(symbol=signal.pair, quantity=quantity)
        logger.info("COMPRA %s | qty=%.6f | precio≈%.4f", signal.pair, quantity, signal.price)

        tp_price = _round_price(signal.tp,         tick_size)
        sl_price = _round_price(signal.sl,         tick_size)
        sl_limit = _round_price(signal.sl * 0.999, tick_size)

        client.create_oco_order(
            symbol=signal.pair,
            side="SELL",
            quantity=quantity,
            price=tp_price,
            stopPrice=sl_price,
            stopLimitPrice=sl_limit,
            stopLimitTimeInForce="GTC",
        )
        logger.info("OCO colocado %s | TP=%s SL=%s", signal.pair, tp_price, sl_price)

        # Registrar la posición en el estado local
        state.add_position(signal.pair, quantity, signal.price, signal.sl, signal.tp)
        return True

    except BinanceAPIException as exc:
        logger.error("Error al operar %s: %s", signal.pair, exc)
        return False


def run_cycle(client: Client, signals: list[Signal], pairs: list[str]) -> None:
    """
    Ejecuta un ciclo completo:
    - Comprueba posiciones propias (bot_state.json) y cierra las que ya se ejecutaron
    - Entra en las mejores señales hasta llenar MAX_OPEN_POSITIONS
    """
    open_pos = get_open_positions(client)
    n_open   = len(open_pos)

    logger.info("Posiciones abiertas (propias): %d/%d", n_open, MAX_OPEN_POSITIONS)
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
            entered += 1

    if entered == 0 and signals:
        logger.info("Señales encontradas pero ninguna ejecutada.")
    elif not signals:
        logger.info("Sin señales en este ciclo.")
