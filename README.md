# auto_trader — Fase 0: Backtesting Sistemático

> **Experimento educativo.** El objetivo es descubrir con datos reales si alguna estrategia
> técnica clásica tiene ventaja estadística medible. Todo el testing posterior se realiza
> en cuentas demo. **No es asesoramiento financiero.**

**Fase actual:** 0 — Validación histórica  
**Resultados:** ver `reports/RECOMENDACION.md` (generado tras ejecutar el pipeline)

---

## Activos evaluados

| Ticker | Tipo | Razón |
|---|---|---|
| SPY | ETF S&P500 | Benchmark del mercado |
| AAPL | Acción | Alta liquidez, blue-chip |
| NVDA | Acción | Alta volatilidad, tendencia IA |
| TSLA | Acción | Volatilidad extrema, testea robustez |

## Estrategias probadas (5)

| Estrategia | Tipo |
|---|---|
| EMA Cross | Seguimiento de tendencia |
| RSI Mean Reversion | Reversión a la media |
| Bollinger Breakout | Momentum con volatilidad |
| MACD Trend | Seguimiento de tendencia |
| ATR Trailing Stop | Stop dinámico |

---

## Cómo reproducir desde cero

```bash
git clone https://github.com/mateoricci0/auto_trader.git
cd auto_trader
pip install -r requirements.txt

python scripts/download_all.py    # Descarga datos (SPY, AAPL, NVDA, TSLA)
python scripts/run_fase0.py       # Walk-forward (~20-40 min)
python scripts/run_oos_final.py   # Análisis OOS → reports/RECOMENDACION.md
python scripts/build_report.py    # Reporte HTML interactivo
```

## Tests

```bash
python -m pytest tests/ -v
```

---

## Estructura

```
auto_trader/
├── data/
│   ├── loader.py              # Descarga, caché y split train/OOS
│   └── cache/                 # Parquets cacheados (gitignored)
├── strategies/
│   ├── base.py                # StrategyBase con position_size()
│   ├── indicators.py          # EMA, ATR, RSI, MACD, Bollinger (pure pandas)
│   └── ema_cross.py, ...      # Una estrategia por archivo
├── backtest/
│   ├── engine.py              # run_walk_forward, run_oos_backtest
│   ├── grids.py               # Grids de parámetros
│   └── metrics.py             # passes_filters, beats_buy_hold
├── scripts/
│   ├── download_all.py        # Descarga datos
│   ├── run_fase0.py           # Walk-forward completo
│   ├── run_oos_final.py       # OOS final + RECOMENDACION.md
│   └── build_report.py        # Notebook → HTML
├── notebooks/
│   └── fase0_analisis.ipynb   # Análisis visual interactivo
├── reports/
│   └── RECOMENDACION.md       # Generado automáticamente
├── docs/
│   ├── METODOLOGIA.md         # Explicación de cada decisión técnica
│   └── DECISIONES.md          # Por qué se eligió cada herramienta/activo
└── tests/
```

---

## Filtros de aceptación (OOS final)

| Filtro | Umbral |
|---|---|
| Sharpe Ratio | > 1.0 |
| Max Drawdown | < 20% |
| Profit Factor | > 1.3 |
| Num Trades | ≥ 30 |
| Supera Buy & Hold | sí (criterio adicional) |

---

## Limitaciones conocidas

- Datos `1h` limitados a ~730 días (límite de yfinance)
- Solo posiciones largas (long-only)
- Universo de solo 4 activos
- Slippage estimado, no medido empíricamente
- Un único período OOS puede ser atípico

---

## Próximos pasos

- **Fase 1**: paper trading en cuenta demo Alpaca con la estrategia candidata (si existe)
- La Fase 1 se diseña a partir de `reports/RECOMENDACION.md`

Ver [docs/METODOLOGIA.md](docs/METODOLOGIA.md) y [docs/DECISIONES.md](docs/DECISIONES.md) para el razonamiento completo.