"""Configuración central del bot."""

# ── Pares ────────────────────────────────────────────────────────────────────
PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
]

CORR_GROUPS = [
    {"BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"},
    {"XRPUSDT", "ADAUSDT", "DOGEUSDT"},
    {"AVAXUSDT", "DOTUSDT", "LINKUSDT"},
]
MAX_PER_CORR_GROUP = 1

# ── Capital de trading ────────────────────────────────────────────────────────
# El bot opera SOLO con este presupuesto. Cambia este valor para ajustar cuánto
# arriesgas. El resto del saldo queda intacto.
TRADING_CAPITAL = 500.0   # USDT — equivale a ~500 €

# ── Timeframe ────────────────────────────────────────────────────────────────
TIMEFRAME     = "1m"      # 1 minuto — escanea cada minuto
CANDLES_LIMIT = 200       # 200 velas de historia

# ── Indicadores ──────────────────────────────────────────────────────────────
EMA_FAST   = 9
EMA_SLOW   = 21
RSI_PERIOD = 14
ATR_PERIOD = 14

# ── Calidad de señal ─────────────────────────────────────────────────────────
MIN_SL_DISTANCE_PCT = 0.002   # SL mínimo 0.2% bajo el precio de entrada
MIN_TP_DISTANCE_PCT = 0.003   # TP mínimo 0.3% sobre el precio de entrada
MIN_RR_RATIO        = 1.5     # TP debe ser ≥ 1.5× la distancia al SL
MIN_CONFIDENCE      = 0.60    # Descartar señales de baja convicción

# ── Gestión de riesgo ─────────────────────────────────────────────────────────
RISK_PER_TRADE     = 0.04    # 4% del TRADING_CAPITAL por operación (más agresivo)
MAX_POSITION_PCT   = 0.40    # Hasta 40% del capital por posición
MAX_OPEN_POSITIONS = 3
DAILY_LOSS_LIMIT   = 0.08    # Parar si la pérdida diaria supera el 8% del capital
