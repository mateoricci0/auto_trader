# auto_trader — Fase 0: Investigación de Estrategias Base

Sistema de trading algorítmico para acciones US. Fase 0 es backtesting puro sobre datos históricos, sin conexión a brokers ni APIs externas.

## Objetivo de Fase 0

Validar sobre datos históricos qué estrategia técnica clásica (si alguna) cumple los filtros de aceptación mínimos para ser considerada en producción.

**Filtros de aceptación (todos deben cumplirse en periodo out-of-sample):**
- Sharpe ratio > 1.0
- Máximo drawdown < 20%
- Profit factor > 1.3
- Número de operaciones ≥ 30

## Activos evaluados

| Ticker | Descripción |
|--------|-------------|
| SPY | S&P 500 ETF — benchmark de mercado |
| AAPL | Apple — mega-cap tech |
| NVDA | NVIDIA — alta volatilidad, momentum |
| TSLA | Tesla — alta volatilidad, tendencias fuertes |

## Estrategias a evaluar

| Estrategia | Lógica |
|------------|--------|
| EMA Cross | Cruce de medias exponenciales (fast/slow) |
| RSI Mean-Reversion | Compra en sobreventa, vende en sobrecompra |
| Bollinger Breakout | Ruptura de banda superior con confirmación de volumen |
| MACD Trend | Señal de cruce MACD sobre línea cero |
| ATR Trailing | Stop trailing basado en ATR, trend-following |

## Instalación

```bash
git clone https://github.com/mateoricci0/auto_trader.git
cd auto_trader
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

## Uso

```bash
# Descargar datos históricos
python scripts/download_all.py

# Ejecutar backtests con walk-forward
python scripts/run_fase0.py

# Análisis out-of-sample final
python scripts/run_oos_final.py

# Generar reporte HTML
python scripts/build_report.py
```

## Tests

```bash
pytest
```

## Estructura

```
auto_trader/
├── data/                    # parquet con datos históricos (gitignored)
│   └── loader.py            # descarga y caché de datos
├── strategies/              # una estrategia por archivo
├── backtest/                # motor de backtest y walk-forward
├── reports/                 # outputs HTML y parquet (gitignored excepto .gitkeep)
├── tests/                   # tests unitarios
├── notebooks/               # análisis exploratorio
├── scripts/                 # scripts de ejecución
├── docs/                    # metodología y decisiones de diseño
├── .env.example             # variables de entorno requeridas (Fase 1+)
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Próximos pasos

Ver [docs/DECISIONES.md](docs/DECISIONES.md) para contexto de decisiones de diseño.
Fase 1 depende del resultado de Fase 0 — ver [reports/RECOMENDACION.md](reports/RECOMENDACION.md) una vez completado.