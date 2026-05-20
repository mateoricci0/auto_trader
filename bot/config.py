"""Configuración central del bot."""

# ── Pares ────────────────────────────────────────────────────────────────────
PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
]

# Grupos de correlación alta: el bot evita llenar todos los slots con el mismo grupo
CORR_GROUPS = [
    {"BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"},   # Large caps correladas
    {"XRPUSDT", "ADAUSDT", "DOGEUSDT"},              # Mid caps
    {"AVAXUSDT", "DOTUSDT", "LINKUSDT"},             # Altcoins
]
MAX_PER_CORR_GROUP = 1   # máximo 1 posición por grupo de correlación

# ── Timeframe ────────────────────────────────────────────────────────────────
TIMEFRAME     = "1m"
CANDLES_LIMIT = 200    # 200 velas = 200 min de historia en 1m (más estable)

# ── Indicadores ──────────────────────────────────────────────────────────────
EMA_FAST   = 9
EMA_SLOW   = 21
RSI_PERIOD = 14
ATR_PERIOD = 14

# ── Calidad de señal ─────────────────────────────────────────────────────────
MIN_SL_DISTANCE_PCT = 0.004   # SL mínimo 0.4% por debajo del precio de entrada
MIN_RR_RATIO        = 2.5     # TP debe ser al menos 2.5× la distancia al SL
MIN_CONFIDENCE      = 0.70    # Descartar señales de baja convicción

# ── Gestión de riesgo ─────────────────────────────────────────────────────────
RISK_PER_TRADE     = 0.02    # 2% del capital por operación
MAX_POSITION_PCT   = 0.20    # Nunca más del 20% del capital en una sola posición
MAX_OPEN_POSITIONS = 3       # Posiciones simultáneas máximas
DAILY_LOSS_LIMIT   = 0.05    # Parar si pérdida diaria supera el 5% del capital
