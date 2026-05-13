# PROMPTS_FASE0.md — auto_trader

Prompts secuenciales para Claude Code. Ejecutar **en orden**, verificando que cada paso termina sin errores antes de pasar al siguiente. Cada prompt es una sesión independiente.

**Objetivo Fase 0:** validar sobre datos históricos qué estrategia técnica clásica (si alguna) cumple los filtros de aceptación para pasar a Fase 1.

**Working norms aplicadas:**
- Plan-first, un objetivo por sesión
- Verificar funcionando, no solo construir
- Simplicidad sobre elegancia
- Fix errores de forma autónoma y loguear el patrón

---

## PROMPT 0 — Setup del repositorio

```
Vas a inicializar el repositorio auto_trader. Estoy en Windows, usa rutas compatibles.

CONTEXTO:
- Repo ya creado en GitHub: auto_trader (privado)
- Fase 0: backtesting puro sobre acciones US (SPY, AAPL, NVDA, TSLA)
- Sin Alpaca, sin DeepSeek, sin Supabase todavía
- Python 3.11+
- Working directory: el que indique el usuario

OBJETIVO ÚNICO de esta sesión: dejar el repo con estructura, dependencias instaladas, .gitignore, README inicial y primera commit. NADA más.

TAREAS:
1. Crear estructura de carpetas:
   auto_trader/
   ├── data/                    # parquet con datos históricos (gitignored)
   ├── strategies/              # una estrategia por archivo
   ├── backtest/                # motor de backtest y walk-forward
   ├── reports/                 # outputs HTML y notebooks (gitignored excepto .gitkeep)
   ├── tests/                   # tests unitarios
   ├── notebooks/               # análisis exploratorio
   ├── .env.example
   ├── .gitignore
   ├── requirements.txt
   ├── README.md
   └── pyproject.toml

2. requirements.txt con versiones pinneadas:
   - pandas>=2.2
   - numpy>=1.26
   - yfinance>=0.2.40
   - backtesting>=0.3.3
   - pandas-ta>=0.3.14b
   - matplotlib>=3.8
   - plotly>=5.20
   - pyarrow>=15.0    # para parquet
   - pytest>=8.0
   - jupyter>=1.0
   - python-dotenv>=1.0
   - tabulate>=0.9

3. .gitignore: venv, __pycache__, *.parquet, .env, reports/*.html (NO ignorar reports/.gitkeep), notebooks/.ipynb_checkpoints

4. README.md inicial con:
   - Título y descripción de Fase 0
   - Activos: SPY, AAPL, NVDA, TSLA
   - Estrategias a evaluar: EMA cross, RSI mean-reversion, Bollinger breakout, MACD, ATR trailing
   - Cómo instalar (venv + pip install)
   - Cómo ejecutar tests

5. Crear venv, instalar requirements, verificar que `import yfinance, backtesting, pandas_ta` funciona sin errores.

6. Commit inicial: "chore: estructura inicial de Fase 0"

NO IMPLEMENTES estrategias ni backtests todavía. Solo estructura.

Al terminar, ejecuta `pip list | findstr -i "pandas yfinance backtesting"` y muéstrame el output para confirmar instalación correcta.
```

---

## PROMPT 1 — Módulo de datos

```
Vas a implementar el módulo de descarga y caché de datos históricos.

CONTEXTO:
- Repo auto_trader inicializado (PROMPT 0 completado)
- Necesitamos datos OHLCV de SPY, AAPL, NVDA, TSLA en timeframes 1h y 1d
- Rango: 2023-01-01 a 2025-12-31 (3 años)
- Reservar 2025-07-01 a 2025-12-31 como OUT-OF-SAMPLE (no se toca hasta el reporte final)

OBJETIVO ÚNICO: descargar, cachear y exponer datos limpios. Tests verifican que funciona.

TAREAS:
1. Crear `data/loader.py` con:
   - Función `download(ticker: str, timeframe: str, start: str, end: str) -> pd.DataFrame`
     * timeframe: '1h' o '1d'
     * Usa yfinance internamente
     * yfinance limita 1h a últimos 730 días — manejar esto con descarga incremental si hace falta
     * Cachea en `data/cache/{ticker}_{timeframe}.parquet`
     * Si ya existe el parquet, lo lee en lugar de descargar
     * Función `force=True` para forzar redescarga
   - Función `load_split(ticker, timeframe) -> (df_train, df_test)`
     * train: 2023-01-01 a 2025-06-30
     * test (out-of-sample): 2025-07-01 a 2025-12-31
   - Devuelve DataFrames con columnas: Open, High, Low, Close, Volume (capitalizadas para compatibilidad con backtesting.py)
   - Index: DatetimeIndex con timezone UTC

2. Script `scripts/download_all.py` que descarga los 4 tickers × 2 timeframes = 8 datasets y muestra resumen (filas por dataset, rango de fechas, NaNs).

3. Tests en `tests/test_loader.py`:
   - Test que descarga SPY 1d y verifica columnas correctas
   - Test que el caché funciona (segunda llamada no descarga)
   - Test que load_split devuelve fechas no solapadas
   - Test que no hay NaNs en columnas Close/Volume

4. Ejecutar el script y los tests. Muéstrame:
   - Output completo de download_all.py
   - Resultado de pytest

PRECAUCIÓN: yfinance a veces falla. Si pasa, reintentar con backoff (3 intentos, 2s entre cada uno). Loguea claramente cualquier fallo.

NO TOQUES estrategias ni backtest todavía.

Commit final: "feat: módulo de datos con caché parquet y split train/test"
```

---

## PROMPT 2 — Estrategias base

```
Vas a implementar las 5 estrategias técnicas que vamos a evaluar.

CONTEXTO:
- Repo auto_trader con módulo de datos funcionando (PROMPTS 0 y 1 completados)
- Framework de backtest: backtesting.py
- Cada estrategia debe heredar de backtesting.Strategy
- Indicadores: usar pandas-ta donde sea posible

OBJETIVO ÚNICO: 5 estrategias implementadas, cada una en su archivo, con tests unitarios que verifican que generan señales sin errores sobre datos sintéticos.

TAREAS:
1. Crear `strategies/base.py`:
   - Clase abstracta `StrategyBase(Strategy)` con:
     * Atributos comunes: `risk_per_trade = 0.02` (2% del equity)
     * Método `position_size(self, price, stop_price)` que calcula tamaño según riesgo
     * Método `log_trade(self, action, reason)` para trazabilidad
   - Esto es para no duplicar lógica de sizing en cada estrategia

2. Crear las 5 estrategias, una por archivo:

   `strategies/ema_cross.py` — EMACrossStrategy
   - Parámetros: fast=9, slow=21
   - Long cuando EMA(fast) cruza arriba EMA(slow)
   - Salida cuando EMA(fast) cruza abajo EMA(slow)
   - Stop-loss: 2 × ATR(14) bajo entrada

   `strategies/rsi_meanrev.py` — RSIMeanReversionStrategy
   - Parámetros: rsi_period=14, oversold=30, overbought=70
   - Long cuando RSI cruza arriba 30 desde abajo
   - Salida cuando RSI > 70 o stop-loss

   `strategies/bollinger_breakout.py` — BollingerBreakoutStrategy
   - Parámetros: period=20, std=2
   - Long cuando Close rompe banda superior con volumen > media volumen 20
   - Salida cuando Close cruza media móvil central

   `strategies/macd_trend.py` — MACDTrendStrategy
   - Parámetros: fast=12, slow=26, signal=9
   - Long cuando MACD cruza arriba signal Y MACD > 0
   - Salida cuando MACD cruza abajo signal

   `strategies/atr_trailing.py` — ATRTrailingStrategy
   - Long cuando Close > EMA(50) y precio hace nuevo máximo de 20 días
   - Stop trailing: max(stop_anterior, Close - 3 × ATR(14))
   - Salida solo cuando se toca el stop

3. Cada estrategia DEBE:
   - Tener su clase exportada con nombre claro
   - Aceptar parámetros vía atributos de clase (para grid search posterior)
   - NO usar leakage (lookahead bias): solo datos disponibles en la vela actual
   - Implementar siempre stop-loss

4. Tests en `tests/test_strategies.py`:
   - Generar serie sintética de 500 velas con tendencia alcista
   - Para cada estrategia: correr backtest y verificar que:
     * No lanza excepciones
     * Genera al menos 1 operación
     * Las operaciones tienen stop_loss definido
     * No hay trades con lookahead (verificar timestamps)

5. Ejecutar pytest y mostrarme el output completo. Si alguna estrategia falla los tests, FÍJALA antes de continuar y documenta el patrón aprendido en un comentario en el código.

NO ejecutes backtests sobre datos reales todavía. Eso es PROMPT 3.

Commit final: "feat: 5 estrategias técnicas base con tests unitarios"
```

---

## PROMPT 3 — Motor de backtest y walk-forward

```
Vas a implementar el motor que ejecuta backtests sistemáticos y walk-forward analysis.

CONTEXTO:
- Repo con datos y estrategias funcionando (PROMPTS 0-2 completados)
- Backtesting.py ya está en requirements
- Comisión modelada: 0% (Alpaca commission-free)
- Slippage modelado: 0.05% (configurable)
- Capital inicial backtest: $10,000

OBJETIVO ÚNICO: ejecutar las 5 estrategias × 4 activos × 2 timeframes = 40 backtests, con walk-forward analysis, y producir un DataFrame de métricas.

TAREAS:
1. Crear `backtest/engine.py`:
   - Función `run_single_backtest(strategy_class, df, params=None, cash=10000, slippage=0.0005) -> dict`
     * Devuelve dict con métricas: sharpe, max_drawdown, profit_factor, num_trades, win_rate, total_return, cagr, calmar
     * Usa backtesting.Backtest internamente
   - Función `run_walk_forward(strategy_class, df, train_months=12, test_months=3, step_months=3) -> pd.DataFrame`
     * Para cada ventana: optimiza parámetros simples (grid pequeño, máx 9 combinaciones) sobre train
     * Aplica esos parámetros sobre test (out-of-sample fold)
     * Devuelve DataFrame con métricas por fold + métricas agregadas
   - CRÍTICO: el walk-forward NO debe usar datos de 2025-07-01 en adelante. Eso es el OOS final.

2. Crear `backtest/grids.py` con grids de parámetros pequeños y razonables para cada estrategia:
   - EMA cross: fast ∈ [5, 9, 13], slow ∈ [21, 50] → 6 combos
   - RSI: oversold ∈ [25, 30, 35], overbought ∈ [65, 70, 75] → 9 combos
   - Bollinger: period ∈ [15, 20, 25], std ∈ [1.5, 2.0, 2.5] → 9 combos
   - MACD: fast ∈ [8, 12], slow ∈ [21, 26], signal ∈ [9] → 4 combos
   - ATR trailing: ema_period ∈ [20, 50], atr_mult ∈ [2, 3, 4] → 6 combos
   - Total: ~34 combos por activo × timeframe (manejable)

3. Crear `scripts/run_fase0.py`:
   - Itera sobre los 4 tickers × 2 timeframes × 5 estrategias
   - Por cada combinación: ejecuta walk-forward
   - Guarda resultados en `reports/fase0_results.parquet`
   - Muestra progreso con tqdm
   - Loguea cualquier fallo sin abortar el resto

4. Crear `backtest/metrics.py` con funciones auxiliares:
   - `compute_metrics(equity_curve, trades) -> dict` por si necesitamos algo custom
   - `passes_filters(metrics) -> bool` que aplica los 4 filtros: Sharpe>1.0, MaxDD<20%, PF>1.3, NumTrades>=30
   - Solo se evalúa filtros sobre el PERIODO TEST (out-of-sample del walk-forward), no sobre train

5. Test en `tests/test_engine.py`:
   - Verifica que run_single_backtest devuelve todas las métricas esperadas
   - Verifica que walk-forward genera al menos 3 folds para 2 años de datos
   - Verifica que train y test no se solapan en cada fold

6. Ejecutar `python scripts/run_fase0.py` y mostrarme:
   - Tiempo total de ejecución
   - Cuántas combinaciones se procesaron correctamente
   - Cuántas fallaron y por qué
   - Las 10 mejores combinaciones por Sharpe en test (no train)

ESTO PUEDE TARDAR 10-30 MIN. Lánzalo y espera el output completo.

Si tarda más de 1h, hay algo mal: cancelar, optimizar y volver.

Commit final: "feat: motor de backtest con walk-forward y grid de parámetros"
```

---

## PROMPT 4 — Análisis out-of-sample y reporte

```
Vas a generar el reporte final de Fase 0 con análisis sobre datos out-of-sample.

CONTEXTO:
- Repo con backtests walk-forward completados (PROMPT 3)
- `reports/fase0_results.parquet` contiene métricas de todos los folds
- Periodo 2025-07-01 a 2025-12-31 está RESERVADO como OOS final no tocado todavía
- Filtros de aceptación: Sharpe>1.0, MaxDD<20%, PF>1.3, NumTrades>=30 (en periodo TEST)

OBJETIVO ÚNICO: aplicar los mejores parámetros de walk-forward al OOS final, generar reporte HTML interactivo, y producir recomendación documentada.

TAREAS:
1. Crear `scripts/run_oos_final.py`:
   - Lee `reports/fase0_results.parquet`
   - Para cada combinación (estrategia × activo × timeframe): coge los parámetros con mejor Sharpe medio sobre los folds de test del walk-forward
   - Ejecuta UN backtest con esos parámetros sobre el periodo OOS (2025-07-01 a 2025-12-31)
   - Guarda resultados en `reports/fase0_oos.parquet`
   - IMPORTANTE: esta es la primera y única vez que tocamos esos datos. No iterar.

2. Crear notebook `notebooks/fase0_analisis.ipynb` con:
   - Carga de fase0_results.parquet y fase0_oos.parquet
   - Tabla resumen: para cada (estrategia × activo × timeframe) mostrar:
     * Sharpe medio walk-forward
     * Sharpe OOS final
     * MaxDD OOS
     * Profit factor OOS
     * Num trades OOS
     * ¿Pasa los 4 filtros? (✓/✗)
   - Heatmap Plotly: Sharpe OOS por estrategia (filas) × activo+timeframe (columnas)
   - Curvas de equity de las top 5 combinaciones
   - Distribución de retornos por trade de las top 5
   - Análisis de drawdowns: cuánto duran, cuándo ocurren
   - Comparación walk-forward vs OOS: ¿hay degradación significativa? (señal de overfitting)

3. Generar reporte HTML standalone:
   - `scripts/build_report.py` que convierte el notebook a HTML autocontenido
   - Guardar en `reports/fase0_reporte.html`
   - Debe poder abrirse offline en navegador

4. Crear `reports/RECOMENDACION.md` con:
   - **Veredicto claro**: cuántas combinaciones pasan los 4 filtros (puede ser 0)
   - **Top 3 combinaciones** (aunque no pasen filtros) con sus métricas
   - **Análisis de degradación**: si hay diferencia >30% entre Sharpe walk-forward y OOS, marcarlo como sospecha de overfitting
   - **Recomendación para Fase 1**:
     * Si hay ≥1 que pasa filtros: cuál y por qué
     * Si ninguna pasa pero alguna está cerca: cuál + ajustes a probar
     * Si todas fallan dramáticamente: discusión honesta de pivote (LLM como filtro, otro mercado, otro timeframe)
   - **Lo que NO funcionó y por qué**: análisis de las peores combinaciones
   - **Próximos pasos concretos**: lista numerada accionable

5. Mostrarme:
   - Tabla resumen completa
   - Top 5 por Sharpe OOS
   - Cuántas combinaciones pasan los 4 filtros
   - El contenido completo de RECOMENDACION.md

NO maquilles los resultados. Si todo falla, dilo claramente. Es información valiosa.

NO inicies Fase 1 en esta sesión. Solo análisis y reporte.

Commit final: "feat: análisis OOS final y reporte de Fase 0"
```

---

## PROMPT 5 — Limpieza, documentación y release

```
Vas a cerrar Fase 0 dejando el repo en estado profesional y reproducible.

CONTEXTO:
- Fase 0 completada con reporte y recomendación (PROMPTS 0-4)
- Repo debe quedar listo para que cualquier persona (incluido yo en 6 meses) lo reproduzca

OBJETIVO ÚNICO: documentación completa, reproducibilidad verificada, tag de versión.

TAREAS:
1. Actualizar README.md con:
   - Descripción del proyecto y fase actual (Fase 0 completada)
   - Resumen de hallazgos (3-5 bullets con los resultados clave)
   - Cómo reproducir desde cero (clone → venv → install → run)
   - Estructura del repo explicada
   - Enlace al reporte HTML
   - Sección "Próximos pasos" apuntando a Fase 1

2. Crear `docs/METODOLOGIA.md` con:
   - Definición de cada estrategia y su lógica
   - Definición de cada métrica (Sharpe, MaxDD, profit factor, etc.)
   - Explicación del walk-forward analysis
   - Por qué los filtros son los que son
   - Qué es lookahead bias y cómo lo evitamos

3. Crear `docs/DECISIONES.md` con:
   - Por qué Alpaca y no Binance (mínimos, fiscalidad)
   - Por qué acciones US y no cripto
   - Por qué estos 4 activos
   - Por qué estas 5 estrategias
   - Drawdown máximo aceptado: 20%
   - Esto debe poder revisarse en 6 meses para entender el contexto

4. Verificación de reproducibilidad:
   - Borra `data/cache/`, `reports/*.parquet`, `reports/*.html`
   - Ejecuta desde cero: `python scripts/download_all.py && python scripts/run_fase0.py && python scripts/run_oos_final.py && python scripts/build_report.py`
   - Verifica que TODO funciona sin intervención y los outputs son idénticos (o equivalentes — yfinance puede devolver datos ligeramente distintos por correcciones)

5. Tag de git:
   - `git tag -a v0.1.0-fase0 -m "Fase 0 completada: investigación de estrategias base"`
   - `git push --tags`

6. Mostrarme:
   - Output de la reproducción desde cero
   - Diff de los nuevos archivos de documentación
   - Confirmación del tag

Commit final: "docs: cierre de Fase 0 con metodología, decisiones y reproducibilidad verificada"
```

---

## Notas para el usuario

### Antes de empezar
- Asegúrate de tener Python 3.11+ instalado
- Ten el repo clonado en local
- Crea una rama `fase-0` desde main: `git checkout -b fase-0`
- Trabaja todos los prompts en esta rama; al terminar, merge a main con el tag

### Cómo usar estos prompts en Claude Code
1. Abre Claude Code en el directorio del repo
2. Copia y pega UN prompt completo en el chat
3. Espera a que termine — NO interrumpas a mitad
4. Si pide confirmación para algo crítico (borrar, push), revisa antes de confirmar
5. Cuando termine y el commit esté hecho, salta al siguiente prompt en una sesión nueva (`/clear` si es necesario)

### Si algo falla
- No pases al siguiente prompt hasta que el actual esté verde
- Lee el error con Claude Code y pide que lo arregle ("Working norm 4: fix errores autónomamente")
- Si después de 2 intentos sigue fallando, pásame el output y lo revisamos juntos

### Tiempo estimado
- PROMPT 0: 15 min
- PROMPT 1: 30 min
- PROMPT 2: 1 hora
- PROMPT 3: 1.5 horas (incluyendo ejecución de backtests)
- PROMPT 4: 1 hora
- PROMPT 5: 30 min
- **Total: ~4.5-5 horas de trabajo activo**

### Qué esperar al terminar
- Un repo limpio, testeado, reproducible
- Un reporte HTML que puedes abrir y enseñar
- Una recomendación documentada para tomar la decisión de Fase 1
- Conocimiento real sobre qué funciona y qué no en estos activos

### Realismo
Estadísticamente es probable que ninguna estrategia pase los 4 filtros sobre los 4 activos. Eso es información valiosa, no un fracaso. La decisión de Fase 1 puede ser:
1. Adelante con la mejor estrategia (si pasa)
2. Adelante con LLM como filtro de riesgo añadido (si está cerca)
3. Pivote a otro enfoque (si todo falla)

Cualquiera de las tres opciones es un resultado válido. Lo único que NO sería válido es maquillar los datos para forzar un "éxito".
