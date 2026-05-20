"""
Punto de entrada del bot. Carga las API keys del .env y arranca el loop.

Uso:
    py scripts/run_bot.py

Requisitos previos:
    1. Crear cuenta en testnet.binance.vision (login con GitHub)
    2. Generar API Key + Secret Key en el testnet
    3. Copiar .env.example a .env y rellenar las claves
    4. pip install python-binance python-dotenv
"""
import sys
from pathlib import Path

# Añadir raíz del proyecto al path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
import os

load_dotenv(ROOT / ".env")

API_KEY    = os.getenv("BINANCE_TESTNET_API_KEY", "")
API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET", "")

if not API_KEY or not API_SECRET:
    print("ERROR: Faltan las claves de Binance en el archivo .env")
    print("Copia .env.example a .env y rellena BINANCE_TESTNET_API_KEY y BINANCE_TESTNET_API_SECRET")
    sys.exit(1)

from bot.main import run
run(API_KEY, API_SECRET)
