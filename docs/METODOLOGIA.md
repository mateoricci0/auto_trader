# Metodología — Fase 0

## 1. Estrategias implementadas

### EMA Cross (`ema_cross.py`)
Cruce de dos medias exponenciales (EMA rápida y lenta). Señal de compra cuando la EMA rápida cruza por encima de la lenta; señal de venta al cruce inverso. Stop-loss inicial a 2×ATR14 por debajo del precio de entrada.

**Parámetros por defecto:** fast=9, slow=21, atr_mult=2.0

### RSI Mean Reversion (`rsi_meanrev.py`)
Compra cuando el RSI cae por debajo del umbral de sobreventa (entrada en zona de pánico); cierre cuando el RSI supera el umbral de sobrecompra. Stop-loss a 1.5×ATR14.

**Parámetros por defecto:** rsi_period=14, oversold=30, overbought=70, atr_mult=1.5

### Bollinger Breakout (`bollinger_breakout.py`)
Compra cuando el precio rompe la banda superior de Bollinger con confirmación de volumen (volumen > 1.5×media). Stop en la banda inferior. Cierre cuando el precio cae por debajo de la banda media.

**Parámetros por defecto:** bb_period=20, bb_std=2.0, vol_mult=1.5

### MACD Trend (`macd_trend.py`)
Compra cuando la línea MACD cruza la señal desde abajo y el MACD es positivo (tendencia confirmada). Cierre al cruce inverso. Stop-loss a 1.5×ATR14.

**Parámetros por defecto:** fast=12, slow=26, signal=9, atr_mult=1.5

### ATR Trailing Stop (`atr_trailing.py`)
Entradas filtradas por EMA50 (solo en tendencia alcista). Stop-loss trailing que sube pero nunca baja — se actualiza como max(stop_anterior, close - atr_mult×ATR14). Al activarse el stop se cierra la posición.

**Parámetros por defecto:** ema_period=50, atr_period=14, atr_mult=3.0

---

## 2. Métricas calculadas

| Métrica | Descripción |
|---|---|
| **Sharpe Ratio** | Retorno anualizado / volatilidad anualizada. Mide eficiencia ajustada por riesgo |
| **Max Drawdown** | Máxima caída desde un pico de equity. Indica el peor escenario de pérdida |
| **Profit Factor** | Ganancia bruta / pérdida bruta. PF > 1 = sistema rentable; PF > 1.3 = margen útil |
| **Num Trades** | Número de operaciones en el período. Demasiado pocas → sin significancia estadística |
| **Win Rate** | Porcentaje de trades ganadores |
| **Total Return** | Retorno total del período (%) |
| **CAGR** | Tasa de crecimiento anual compuesta |
| **Calmar Ratio** | CAGR / Max Drawdown. Mide retorno por unidad de drawdown |
| **Buy & Hold Return** | Retorno de comprar el activo al inicio y mantener hasta el final del período |

---

## 3. Filtros de aceptación

Los filtros se aplican **únicamente sobre el OOS final completo** (6 meses para `1d`, 3 meses para `1h`), nunca sobre folds individuales del walk-forward.

| Filtro | Umbral | Razón |
|---|---|---|
| Sharpe > 1.0 | 1.0 | Referencia estándar de estrategias institucionales |
| Max Drawdown < 20% | 20% | Pérdida psicológicamente y prácticamente tolerable |
| Profit Factor > 1.3 | 1.3 | Margen suficiente sobre break-even (1.0) |
| Num Trades ≥ 30 | 30 | Mínimo para tener significancia estadística básica |

**Criterio adicional:** la estrategia debe superar el buy & hold en el mismo período. Una estrategia que pasa los 4 filtros pero gana menos que comprar y esperar no añade valor real.

---

## 4. Walk-forward validation

El walk-forward es una técnica de validación que simula cómo se comportaría la estrategia en tiempo real: se optimiza sobre datos históricos (ventana de entrenamiento) y se evalúa sobre datos futuros (ventana de test), avanzando la ventana de forma deslizante.

```
|-- train_1 --|-- test_1 --|
              |-- train_2 --|-- test_2 --|
                            |-- train_3 --|-- test_3 --|
                                          ...
                                          |-- OOS FINAL (nunca tocado) --|
```

**Parámetros de ventana:**
- Timeframe `1d`: train=12m, test=3m, step=3m
- Timeframe `1h`: train=4m, test=1m, step=1m

### Por qué se eligen parámetros en TRAIN, no en TEST

Si eligiéramos los parámetros mirando los resultados en test, estaríamos usando información futura — **data leakage**. En walk-forward riguroso:
1. Se optimizan parámetros buscando el mejor Sharpe en el período de TRAIN
2. Los parámetros elegidos se aplican al TEST sin modificación
3. El TEST solo **mide**, nunca **elige**

### Por qué NumTrades se evalúa solo en OOS final

Los folds de test del walk-forward son ventanas de 1-3 meses — muy cortas para exigir 30 trades. Ese umbral tiene sentido estadístico solo sobre el período OOS completo (6 meses), donde hay tiempo suficiente para generar señales.

---

## 5. Buy & Hold como benchmark

Sin una línea de referencia, cualquier estrategia que gane dinero parece exitosa. El benchmark correcto para estrategias long-only sobre acciones es **comprar el activo al inicio del período y mantenerlo hasta el final**. Si la estrategia gana menos que esto, no añade valor — el inversor habría hecho mejor simplemente comprando y esperando, sin ningún sistema.

---

## 6. Lookahead bias — qué es y cómo se evitó

**Lookahead bias:** usar en la decisión de hoy información que solo estará disponible mañana. Es el error más común en backtesting y genera resultados artificialmente positivos.

Medidas adoptadas:
- Todos los indicadores usan `close.shift(1)` donde es necesario (e.g., ATR usa el cierre previo en el true range)
- `backtesting.py` garantiza que `self.data.Close[-1]` es el cierre de la vela actual (ya cerrada), no de la siguiente
- Las señales se generan al cierre de la vela y se ejecutan a precio de apertura de la siguiente (simulando ejecución real)
- El OOS final (2025-07-01 → 2025-12-31) está completamente separado del proceso de entrenamiento y optimización

---

## 7. Position sizing por riesgo

Cada estrategia calcula el tamaño de posición basándose en el riesgo monetario definido:

```
riesgo_€     = equity_actual × 0.02          # 2% del capital
riesgo_unit  = |precio_entrada - stop_loss|
size         = floor(riesgo_€ / riesgo_unit)
```

Si el stop está muy cerca de la entrada → size grande (poco riesgo por unidad).  
Si el stop está lejos → size pequeño (mucho riesgo por unidad).

Esto es fundamental para que el drawdown y el Sharpe reflejen la realidad, no estén artificialmente inflados o deflados por un sizing fijo.

---

## 8. Slippage por activo

El slippage modela el coste de ejecución real (spread bid-ask + impacto de mercado). Se aplica como comisión por lado de cada trade.

| Activo | Slippage aplicado | Justificación |
|---|---|---|
| SPY | 0.03% | ETF altamente líquido, spread típico muy estrecho |
| AAPL | 0.05% | Acción de alta capitalización, muy líquida |
| NVDA | 0.10% | Alta volatilidad, spread más variable |
| TSLA | 0.15% | Alta volatilidad y movimientos bruscos intradía |

**Nota:** son aproximaciones conservadoras basadas en conocimiento general del mercado, no mediciones empíricas del spread real.

---

## 9. Limitaciones conocidas

1. **Datos 1h limitados a ~730 días** — yfinance no permite histórico más largo en timeframe horario. La potencia estadística de los tests en 1h es reducida.
2. **Solo largos (long-only)** — no se testean estrategias de venta en corto. En mercados bajistas, la desventaja es obvia.
3. **Solo 4 activos** — el universo es muy pequeño. Los resultados no generalizan a otros activos sin validación adicional.
4. **Slippage estimado** — no se midió el spread real; las estimaciones son conservadoras pero pueden diferir en ejecución real.
5. **Sin costes de financiación overnight** — Alpaca no cobra por posiciones en acciones, pero en CFDs esto sería un coste real.
6. **Período OOS puede ser atípico** — 2025-07-01 a 2025-12-31 puede coincidir con un régimen de mercado específico (bullish, bajista, lateral) que no se repita.
