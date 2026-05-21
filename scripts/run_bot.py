"""
Punto de entrada del bot. Carga las API keys del .env y arranca el loop.

Uso:
    py scripts/run_bot.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
import os

load_dotenv(ROOT / ".env")

API_KEY      = os.getenv("BINANCE_TESTNET_API_KEY", "")
API_SECRET   = os.getenv("BINANCE_TESTNET_API_SECRET", "")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")

if not API_KEY or not API_SECRET:
    print("ERROR: Faltan las claves de Binance en el archivo .env")
    sys.exit(1)

if not DEEPSEEK_KEY:
    print("AVISO: DEEPSEEK_API_KEY no configurada — el bot usará solo reglas técnicas.\n")

# ── Preguntar capital de trading ──────────────────────────────────────────────
print("=" * 50)
print("  AUTO_TRADER BOT — Binance Testnet")
print("=" * 50)

while True:
    try:
        raw = input("\n¿Con cuánto USDT quieres operar? (ej: 100): ").strip()
        capital = float(raw)
        if capital <= 0:
            print("  El capital debe ser mayor que 0.")
            continue
        break
    except ValueError:
        print("  Introduce un número válido (ej: 100 o 500.50).")

print(f"\n  Capital asignado: {capital:.2f} USDT")
print(f"  Riesgo por trade: ~{capital * 0.04:.2f} USDT (4%)")
print(f"  Ganancia potencial por trade: ~{capital * 0.04 * 3:.2f} USDT (TP 3× el riesgo)\n")

from bot.main import run
run(API_KEY, API_SECRET, DEEPSEEK_KEY, trading_capital=capital)
