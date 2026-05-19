# Decisiones de Diseño — Fase 0

Registro de las decisiones tomadas y sus justificaciones. Útil para entender el razonamiento
detrás de cada elección y para no repetir debates ya resueltos.

---

## ¿Por qué Alpaca y no Binance?

Alpaca opera en **mercados regulados de Estados Unidos** (NYSE, NASDAQ). Binance opera en cripto.

- **Regulación**: las acciones US están bajo supervisión de la SEC. Las criptomonedas operan en un entorno regulatorio incierto y cambiante.
- **Datos históricos**: para acciones US existen décadas de datos de alta calidad. Las criptomonedas tienen historial corto y mayor manipulación potencial.
- **Liquidez y horario**: las acciones US tienen horario fijo (9:30-16:00 ET), lo que simplifica el sistema. Cripto opera 24/7 con liquidez muy variable.
- **Objetivo de aprendizaje**: comprender el funcionamiento de mercados regulados es más valioso a largo plazo que empezar con cripto.

---

## ¿Por qué acciones y no futuros o forex?

- **Complejidad operativa**: los futuros tienen vencimientos, rolls y márgenes que añaden complejidad innecesaria en Fase 0.
- **Apalancamiento**: forex y futuros tienen apalancamiento implícito que puede destruir una cuenta pequeña rápidamente.
- **Liquidez de acciones blue-chip**: SPY, AAPL, NVDA y TSLA tienen millones de acciones negociadas diariamente — el slippage es mínimo.
- **Paper trading gratuito**: Alpaca ofrece cuentas demo gratuitas con datos en tiempo real para acciones.

---

## ¿Por qué estos 4 activos?

| Activo | Razón |
|---|---|
| **SPY** | ETF del S&P500 — benchmark del mercado, extremadamente líquido, permite evaluar estrategias sobre el mercado broad |
| **AAPL** | La acción más seguida del mundo — alta liquidez, tendencias técnicas relativamente respetadas |
| **NVDA** | Alta volatilidad y tendencia fuerte (IA boom) — testea estrategias de seguimiento de tendencia |
| **TSLA** | Muy alta volatilidad, movimientos extremos — testea robustez de los stops y el position sizing |

Los cuatro juntos cubren distintos perfiles de volatilidad y liquidez, lo que da más información sobre qué tipo de activo funciona con cada estrategia.

---

## ¿Por qué estas 5 estrategias?

Son las estrategias técnicas clásicas más enseñadas y utilizadas en la literatura de trading algorítmico. No se eligieron por creer que funcionan — se eligieron para **testear con datos si funcionan**, que es exactamente el objetivo del experimento.

1. **EMA Cross**: la más simple de seguimiento de tendencia. Referencia básica.
2. **RSI Mean Reversion**: contraparte de la anterior — estrategia de reversión.
3. **Bollinger Breakout**: momentum con contexto de volatilidad.
4. **MACD Trend**: cruce de medias con filtro de tendencia incorporado.
5. **ATR Trailing**: gestión de posición dinámica sin señal de entrada fija.

---

## ¿Por qué MaxDrawdown < 20%?

- El 20% es un umbral de referencia habitual en la industria para estrategias retail.
- Un drawdown del 20% ya es psicológicamente duro de aguantar en trading real.
- Por encima del 25-30%, la mayoría de traders abandonan el sistema, lo que lo hace inútil aunque sea rentable en el largo plazo.
- En backtesting los drawdowns reales tienden a ser peores que los históricos, por lo que el umbral del 20% en backtest implica tolerancia real de 25-30%.

---

## ¿Por qué todo el testing posterior en demo?

La Fase 0 es un experimento en laboratorio con datos históricos. Los datos históricos **no predicen el futuro** — solo permiten descartar estrategias claramente malas. Las que pasen los filtros necesitan validarse en condiciones de mercado real:

1. **Datos en tiempo real** son diferentes a datos históricos (bid-ask, slippage real, retrasos de ejecución)
2. **El comportamiento propio cambia** cuando hay dinero real en juego
3. **Los mercados cambian** — una estrategia que funcionó en 2023-2025 puede no funcionar en 2026
4. **El coste del error en demo es cero**; en live puede ser todo el capital

---

## ¿Por qué walk-forward y no simple train/test split?

Un split simple (entrenar en 70%, testear en 30%) tiene un problema: los parámetros se optimizan una sola vez y el test solo se evalúa una vez. Hay riesgo de que ese único test sea favorable por azar.

El walk-forward simula múltiples ciclos de "entrenar, decidir, ejecutar" sucesivos, lo que da una distribución de resultados en lugar de un único número. Es más cercano a la realidad operativa.

---

## ¿Por qué no optimizar más parámetros o usar grids más grandes?

Cuantos más parámetros se optimizan y cuantas más combinaciones se prueban, mayor es el riesgo de **overfitting**: encontrar parámetros que funcionan en los datos históricos por pura coincidencia estadística.

Los grids son deliberadamente pequeños (6-9 combinaciones por estrategia) para reducir este riesgo. La filosofía es: si la estrategia tiene ventaja real, debería funcionar con parámetros razonables; si solo funciona con parámetros muy específicos, probablemente es overfitting.

---

## Historial de correcciones tras auditoría técnica

Antes de implementar, se realizó una auditoría del diseño inicial que identificó los siguientes errores y sus correcciones:

| ID | Error original | Corrección aplicada |
|---|---|---|
| FIX #1 | Datos `1h` descargados desde 2021 (imposible en yfinance) | Límite real de 730 días, descarga en bloques |
| FIX #2 | NumTrades evaluado en folds de 3 meses | Solo en OOS final de 6 meses |
| FIX #3 | `position_size()` definido pero no usado en `next()` | Integración obligatoria en todas las estrategias |
| FIX #4 | Parámetros elegidos mirando resultados en test (leakage) | Selección solo por Sharpe en TRAIN |
| FIX #5 | Slippage fijo para todos los activos | Slippage diferenciado: SPY<AAPL<NVDA<TSLA |
| FIX #6 | Sin benchmark buy & hold | Añadido a todas las métricas y filtros |
| FIX menor | Sin órdenes individuales OOS guardadas | `fase0_oos_trades.parquet` |
| FIX menor | Sin validación explícita de no-contaminación | `assert` en `run_oos_final.py` |
| FIX menor | Mismas ventanas temporales para `1d` y `1h` | `1h`: train=4m, test=1m, step=1m |
