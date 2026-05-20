"""Configuración central del bot. Edita aquí para cambiar comportamiento."""

# Pares a monitorear — top cripto por volumen
PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
]

# Timeframe de las velas
TIMEFRAME = "15m"          # 15 minutos — cambia a "5m" para más trades

# Parámetros de estrategia (EMA cross + RSI filter)
EMA_FAST      = 9
EMA_SLOW      = 21
RSI_PERIOD    = 14
RSI_MAX       = 65         # No comprar si RSI > 65 (sobrecomprado)
ATR_PERIOD    = 14
ATR_SL_MULT   = 2.0        # Stop loss = 2 × ATR bajo el precio de entrada
ATR_TP_MULT   = 3.0        # Take profit = 3 × ATR sobre el precio de entrada

# Gestión de riesgo
RISK_PER_TRADE      = 0.02  # 2% del capital por operación
MAX_OPEN_POSITIONS  = 3     # Máximo de posiciones simultáneas

# Cuántas velas históricas pedir (más = indicadores más estables)
CANDLES_LIMIT = 100
