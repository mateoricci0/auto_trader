"""
Loop principal del bot. Corre indefinidamente hasta Ctrl+C.
Cada 15 minutos (configurable): escanea pares → detecta señales → opera.
"""
import logging
import os
import time
from datetime import datetime

from binance.client import Client

from .config import PAIRS, TIMEFRAME
from .scanner import scan
from .trader import run_cycle

# Logging con timestamp
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

# Intervalo en segundos según el timeframe configurado
_INTERVAL_MAP = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900,
    "30m": 1800, "1h": 3600, "4h": 14400,
}
LOOP_SECONDS = _INTERVAL_MAP.get(TIMEFRAME, 900)


def run(api_key: str, api_secret: str) -> None:
    """Inicia el bot. Llama a esta función desde run_bot.py."""
    logger.info("=" * 55)
    logger.info("  AUTO_TRADER BOT — Binance Testnet")
    logger.info("  Pares: %d | Timeframe: %s | Intervalo: %ds",
                len(PAIRS), TIMEFRAME, LOOP_SECONDS)
    logger.info("=" * 55)

    client = Client(api_key, api_secret, testnet=True)

    # Verificar conexión
    try:
        info = client.get_account()
        usdt = next(b for b in info["balances"] if b["asset"] == "USDT")
        logger.info("Conectado. Saldo USDT: %.2f", float(usdt["free"]))
    except Exception as exc:
        logger.error("No se pudo conectar a Binance testnet: %s", exc)
        raise

    cycle = 0
    while True:
        cycle += 1
        logger.info("─── Ciclo %d — %s ───", cycle, datetime.now().strftime("%Y-%m-%d %H:%M"))

        try:
            signals = scan(client)
            logger.info("Señales encontradas: %d", len(signals))
            run_cycle(client, signals, PAIRS)
        except Exception as exc:
            logger.error("Error en ciclo %d: %s", cycle, exc)

        logger.info("Siguiente ciclo en %d segundos...\n", LOOP_SECONDS)
        time.sleep(LOOP_SECONDS)
