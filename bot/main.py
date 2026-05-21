"""
Loop principal del bot. Corre indefinidamente hasta Ctrl+C.
"""
import logging
import time
from datetime import datetime

from binance.client import Client

from . import ai_brain, state
from .config import PAIRS, TIMEFRAME
from .scanner import scan
from .trader import _get_balance_usdt, get_open_positions, run_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

_INTERVAL_MAP = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900,
    "30m": 1800, "1h": 3600, "4h": 14400,
}
LOOP_SECONDS = _INTERVAL_MAP.get(TIMEFRAME, 900)


def _print_account_summary(client: Client) -> float:
    """Muestra saldo, P&L de sesión y posiciones abiertas. Devuelve saldo USDT."""
    balance  = _get_balance_usdt(client)
    sess     = state.get_session_stats()
    open_pos = get_open_positions(client)

    start_bal   = sess.get("start_balance", balance)
    session_pnl = sess.get("gross_pnl", 0.0)
    daily_pnl   = state.get_daily_pnl()
    trades      = sess.get("trades", 0)
    wins        = sess.get("wins", 0)
    losses      = sess.get("losses", 0)
    win_rate    = (wins / trades * 100) if trades > 0 else 0.0

    # Valor estimado de posiciones abiertas (USDT bloqueado en cripto)
    open_value = sum(p["value_usdt"] for p in open_pos.values())
    total_val  = balance + open_value

    sign_sess  = "+" if session_pnl >= 0 else ""
    sign_daily = "+" if daily_pnl  >= 0 else ""

    logger.info("┌─────────────────────────────────────────────┐")
    logger.info("│  SALDO USDT libre:   %10.2f USDT         │", balance)
    logger.info("│  Valor en posiciones:%10.2f USDT         │", open_value)
    logger.info("│  TOTAL estimado:     %10.2f USDT         │", total_val)
    logger.info("│  P&L sesión:         %s%9.2f USDT         │", sign_sess, session_pnl)
    logger.info("│  P&L hoy:            %s%9.2f USDT         │", sign_daily, daily_pnl)
    logger.info("│  Trades sesión: %d  (W:%d / L:%d  WR:%.0f%%)  │",
                trades, wins, losses, win_rate)
    logger.info("└─────────────────────────────────────────────┘")

    if open_pos:
        logger.info("  Posiciones abiertas:")
        for pair, pos in open_pos.items():
            logger.info("    %-10s | qty=%.4f | entrada=%.4f | actual=%.4f | no realizado=%s",
                        pair, pos["qty"], pos["entry_price"],
                        pos["current_price"], pos["unrealized_str"])

    return balance


def run(api_key: str, api_secret: str, deepseek_key: str = "", trading_capital: float = 500.0) -> None:
    ai_brain.init(deepseek_key)

    # Aplicar el capital elegido por el usuario
    import bot.config as _cfg
    _cfg.TRADING_CAPITAL = trading_capital

    logger.info("=" * 55)
    logger.info("  AUTO_TRADER BOT — Binance Testnet")
    logger.info("  Pares: %d | Timeframe: %s | Intervalo: %ds",
                len(PAIRS), TIMEFRAME, LOOP_SECONDS)
    logger.info("  Cerebro: %s", "DeepSeek AI" if ai_brain.is_available() else "reglas técnicas")
    logger.info("  Capital: %.2f USDT", trading_capital)
    logger.info("=" * 55)

    client = Client(api_key, api_secret, testnet=True)

    server_time = client.get_server_time()
    client.timestamp_offset = server_time["serverTime"] - int(time.time() * 1000)

    try:
        info    = client.get_account()
        balance = float(next(b for b in info["balances"] if b["asset"] == "USDT")["free"])
        logger.info("Conectado. Saldo USDT: %.2f", balance)
        state.init_session(balance)
        state.init_daily(balance)
    except Exception as exc:
        logger.error("No se pudo conectar a Binance testnet: %s", exc)
        raise

    cycle = 0
    while True:
        cycle += 1
        logger.info("─── Ciclo %d — %s ───", cycle, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        try:
            _print_account_summary(client)
            signals = scan(client)
            logger.info("Señales válidas: %d", len(signals))
            run_cycle(client, signals)
        except Exception as exc:
            logger.error("Error en ciclo %d: %s", cycle, exc, exc_info=True)

        logger.info("Próximo ciclo en %ds...\n", LOOP_SECONDS)
        time.sleep(LOOP_SECONDS)
