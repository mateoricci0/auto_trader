"""
Punto de entrada del bot. Carga las API keys del .env y arranca el loop.

Uso:
    py scripts/run_bot.py

Requisitos previos:
    1. Crear cuenta en testnet.binance.vision (login con GitHub)
    2. Generar API Key + Secret Key en el testnet
    3. Copiar .env.example a .env y rellenar las claves
    4. pip install python-binance python-dotenv openai
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
    print("Copia .env.example a .env y rellena BINANCE_TESTNET_API_KEY y BINANCE_TESTNET_API_SECRET")
    sys.exit(1)

if not DEEPSEEK_KEY:
    print("AVISO: DEEPSEEK_API_KEY no configurada — el bot usará solo reglas técnicas.")
    print("Añade tu clave en el .env para activar el cerebro IA.\n")

from bot.main import run
run(API_KEY, API_SECRET, DEEPSEEK_KEY)
