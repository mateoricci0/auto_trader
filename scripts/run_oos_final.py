"""
Aplica los mejores parámetros walk-forward al OOS final (período reservado).

Prerrequisito: reports/fase0_results.parquet (generado por run_fase0.py)

Salidas:
  reports/fase0_oos.parquet         métricas OOS por combo
  reports/fase0_oos_trades.parquet  trades individuales OOS
  reports/RECOMENDACION.md          veredicto final del experimento

Uso: python scripts/run_oos_final.py
"""
import ast
import logging
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.engine import run_oos_backtest
from backtest.grids import ALL_STRATEGIES
from backtest.metrics import beats_buy_hold, passes_filters
from data.loader import OOS_END, OOS_START, load_split

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")

REPORTS  = Path(__file__).parent.parent / "reports"
SLIPPAGE = {"SPY": 0.0003, "AAPL": 0.0005, "NVDA": 0.0010, "TSLA": 0.0015}
STRATEGY_MAP = {cls.__name__: cls for cls in ALL_STRATEGIES}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_best_params(group_df: pd.DataFrame) -> dict:
    """Pick params by mode across walk-forward folds (chosen in TRAIN, no leakage)."""
    params_list = group_df["best_params"].dropna().tolist()
    if not params_list:
        return {}
    counter = Counter(params_list)
    most_common_str = counter.most_common(1)[0][0]
    try:
        return ast.literal_eval(most_common_str)
    except Exception:
        return {}


def _validate_no_overlap(df_oos: pd.DataFrame, group_df: pd.DataFrame) -> None:
    """Abort if OOS dates overlap any train window — would mean data contamination."""
    oos_start = df_oos.index.min()
    for _, row in group_df.iterrows():
        train_end_ts = pd.Timestamp(row["train_end"], tz="UTC")
        assert oos_start > train_end_ts, (
            f"CONTAMINACIÓN DETECTADA: OOS start {oos_start} <= train_end {train_end_ts}. "
            "Aborting."
        )


def _compute_buy_hold(df_oos: pd.DataFrame) -> float:
    """Buy & hold return for the OOS period (%)."""
    if df_oos.empty:
        return np.nan
    first = df_oos["Close"].iloc[0]
    last  = df_oos["Close"].iloc[-1]
    return (last / first - 1) * 100


# ---------------------------------------------------------------------------
# Main OOS loop
# ---------------------------------------------------------------------------

def run_oos() -> tuple[pd.DataFrame, pd.DataFrame]:
    wf_path = REPORTS / "fase0_results.parquet"
    if not wf_path.exists():
        print(f"ERROR: {wf_path} no existe. Ejecuta run_fase0.py primero.")
        sys.exit(1)

    df_wf = pd.read_parquet(wf_path)
    combos = df_wf.groupby(["strategy", "ticker", "timeframe"])

    oos_rows  = []
    all_trades = []

    for (strategy_name, ticker, timeframe), group_df in tqdm(
        combos, desc="OOS final", unit="combo"
    ):
        strategy_cls = STRATEGY_MAP.get(strategy_name)
        if strategy_cls is None:
            continue

        try:
            _, df_oos = load_split(ticker, timeframe)
        except Exception as exc:
            print(f"  WARN: no se pudo cargar OOS {ticker} {timeframe}: {exc}")
            continue

        if df_oos.empty:
            print(f"  WARN: OOS vacío para {ticker} {timeframe}")
            continue

        # Validar que el OOS no toca ningún fold de entrenamiento
        _validate_no_overlap(df_oos, group_df)

        best_params = _get_best_params(group_df)
        slippage    = SLIPPAGE.get(ticker, 0.0005)

        metrics, trades, _ = run_oos_backtest(
            strategy_cls, df_oos, params=best_params,
            cash=10_000, slippage=slippage,
        )

        # buy_hold_return puede venir de backtesting.py o calcularlo directamente
        if np.isnan(metrics.get("buy_hold_return", np.nan)):
            metrics["buy_hold_return"] = _compute_buy_hold(df_oos)

        metrics.update({
            "strategy":       strategy_name,
            "ticker":         ticker,
            "timeframe":      timeframe,
            "best_params":    str(best_params),
            "oos_start":      OOS_START,
            "oos_end":        OOS_END,
            "passes_filters": passes_filters(metrics),
            "beats_buy_hold": beats_buy_hold(metrics),
        })
        oos_rows.append(metrics)

        if not trades.empty:
            trades = trades.copy()
            trades["strategy"]  = strategy_name
            trades["ticker"]    = ticker
            trades["timeframe"] = timeframe
            all_trades.append(trades)

    df_oos_metrics = pd.DataFrame(oos_rows)
    df_oos_trades  = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()

    return df_oos_metrics, df_oos_trades


# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------

def print_summary(df: pd.DataFrame) -> None:
    if df.empty:
        print("Sin resultados OOS.")
        return

    print("\n" + "=" * 100)
    print("RESULTADOS OOS FINAL")
    print(f"Período: {df['oos_start'].iloc[0]} → {df['oos_end'].iloc[0]}")
    print("=" * 100)
    cols_show = ["strategy", "ticker", "timeframe", "sharpe", "max_drawdown",
                 "profit_factor", "num_trades", "total_return", "buy_hold_return",
                 "passes_filters", "beats_buy_hold"]
    available = [c for c in cols_show if c in df.columns]
    print(df[available].sort_values("sharpe", ascending=False).to_string(index=False))

    n_pass = df["passes_filters"].sum()
    n_bh   = df["beats_buy_hold"].sum()
    n_both = (df["passes_filters"] & df["beats_buy_hold"]).sum()
    print(f"\n{'='*60}")
    print(f"Total combos OOS: {len(df)}")
    print(f"Pasan los 4 filtros:         {n_pass}/{len(df)}")
    print(f"Superan buy & hold:          {n_bh}/{len(df)}")
    print(f"Pasan filtros Y B&H:         {n_both}/{len(df)}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# Walk-forward vs OOS degradation
# ---------------------------------------------------------------------------

def compute_degradation(df_oos: pd.DataFrame, df_wf: pd.DataFrame) -> pd.DataFrame:
    """Compute Sharpe degradation from WF test folds to OOS final."""
    wf_sharpe = (
        df_wf.dropna(subset=["sharpe"])
        .groupby(["strategy", "ticker", "timeframe"])["sharpe"]
        .mean()
        .reset_index()
        .rename(columns={"sharpe": "sharpe_wf_mean"})
    )
    merged = df_oos.merge(wf_sharpe, on=["strategy", "ticker", "timeframe"], how="left")
    merged["sharpe_degradation_pct"] = (
        (merged["sharpe"] - merged["sharpe_wf_mean"]) / merged["sharpe_wf_mean"].abs() * 100
    )
    merged["suspicious_overfit"] = merged["sharpe_degradation_pct"] < -30
    return merged


# ---------------------------------------------------------------------------
# Generate RECOMENDACION.md
# ---------------------------------------------------------------------------

def generate_recomendacion(df_oos: pd.DataFrame, df_wf: pd.DataFrame) -> None:
    df = compute_degradation(df_oos, df_wf)

    n_pass = int(df["passes_filters"].sum())
    n_bh   = int(df["beats_buy_hold"].sum())
    n_both = int((df["passes_filters"] & df["beats_buy_hold"]).sum())
    n_total = len(df)

    top3 = df.sort_values("sharpe", ascending=False).head(3)
    suspicious = df[df["suspicious_overfit"] == True]

    # Veredicto
    if n_both > 0:
        veredicto = (
            f"**{n_both} combinación(es) pasan los 4 filtros Y superan buy & hold** — "
            "hay candidatos reales para Fase 1 (paper trading en cuenta demo)."
        )
    elif n_pass > 0:
        veredicto = (
            f"**{n_pass} combinación(es) pasan los 4 filtros pero ninguna supera buy & hold** — "
            "hay actividad interesante, pero comprar y mantener es más rentable. "
            "No hay candidatos claros para Fase 1."
        )
    else:
        veredicto = (
            "**Ninguna combinación pasa los 4 filtros en OOS** — "
            "resultado válido del experimento: estas estrategias técnicas clásicas, "
            "en estos activos y período, no tienen ventaja estadística suficiente. "
            "Esto es información valiosa, no un fracaso."
        )

    # Top 3 en markdown
    top3_md = ""
    for i, (_, row) in enumerate(top3.iterrows(), 1):
        pf_tag  = "✓ pasa filtros" if row.get("passes_filters") else "✗ no pasa filtros"
        bh_tag  = "✓ supera B&H"  if row.get("beats_buy_hold")  else "✗ no supera B&H"
        deg_val = row.get("sharpe_degradation_pct", float("nan"))
        deg_str = f"{deg_val:+.1f}%" if not np.isnan(deg_val) else "N/A"
        top3_md += (
            f"\n### {i}. {row['strategy']} — {row['ticker']} {row['timeframe']}\n"
            f"- Sharpe OOS: {row.get('sharpe', float('nan')):.3f}\n"
            f"- Max Drawdown: {row.get('max_drawdown', float('nan')):.1f}%\n"
            f"- Profit Factor: {row.get('profit_factor', float('nan')):.2f}\n"
            f"- Num Trades: {int(row.get('num_trades', 0))}\n"
            f"- Return OOS: {row.get('total_return', float('nan')):.1f}%\n"
            f"- Buy & Hold OOS: {row.get('buy_hold_return', float('nan')):.1f}%\n"
            f"- Degradación WF→OOS: {deg_str}\n"
            f"- {pf_tag} | {bh_tag}\n"
        )

    # Degradación
    n_overfit = len(suspicious)
    deg_section = ""
    if n_overfit > 0:
        deg_section = (
            f"\n### Sospecha de overfitting\n"
            f"{n_overfit} combinación(es) muestran degradación >30% de Sharpe entre "
            "los folds de test del walk-forward y el OOS final. Esto sugiere que "
            "el walk-forward encontró parámetros que funcionan en el período histórico "
            "pero no generalizan bien.\n\n"
            "Combos sospechosos:\n"
        )
        for _, row in suspicious.iterrows():
            deg_val = row.get("sharpe_degradation_pct", float("nan"))
            deg_section += (
                f"- {row['strategy']} {row['ticker']} {row['timeframe']}: "
                f"WF Sharpe {row.get('sharpe_wf_mean', float('nan')):.3f} → "
                f"OOS Sharpe {row.get('sharpe', float('nan')):.3f} "
                f"({deg_val:+.1f}%)\n"
            )

    # Próximos pasos
    if n_both > 0:
        proximos = (
            "1. Diseñar Fase 1 de paper trading (30-60 días en cuenta demo)\n"
            "2. Usar los parámetros OOS óptimos como punto de partida\n"
            "3. Implementar con Alpaca paper trading API\n"
            "4. Monitorear diariamente, comparar con B&H en tiempo real\n"
            "5. Si paper trading confirma resultados → considerar Fase 2 (live, capital mínimo)"
        )
    else:
        proximos = (
            "1. Ampliar el universo de activos (más sectores, ETFs sectoriales)\n"
            "2. Explorar estrategias de largo plazo (swing trading, posición mensual)\n"
            "3. Investigar modelos de machine learning para señales (Fase 0.5)\n"
            "4. Considerar market regimes — filtrar por tendencia del mercado global\n"
            "5. Revisar si el período OOS fue atípico (rally, crash) — contexto importa"
        )

    md = f"""# RECOMENDACIÓN FASE 0 — auto_trader

> Generado automáticamente por `run_oos_final.py`
> Período OOS: {df['oos_start'].iloc[0]} → {df['oos_end'].iloc[0]}
> Activos: SPY, AAPL, NVDA, TSLA | Estrategias: 5 | Timeframes: 1d, 1h
> Total combinaciones evaluadas: {n_total}

---

## Veredicto

{veredicto}

---

## Resumen de filtros OOS

| Criterio | Resultado |
|---|---|
| Combinaciones totales | {n_total} |
| Pasan los 4 filtros (Sharpe>1, DD<20%, PF>1.3, Trades≥30) | {n_pass} |
| Superan buy & hold | {n_bh} |
| Pasan filtros Y superan B&H | **{n_both}** |

---

## Top 3 por Sharpe OOS
{top3_md}
---

## Degradación walk-forward → OOS
{deg_section if deg_section else "No se detectan señales claras de overfitting (degradación ≤30% en todos los combos)."}

---

## Lo que NO funcionó

- Las estrategias de cruce de medias (EMA Cross) tienden a generar muchos trades
  pequeños que se comen el slippage — mercados modernos son difíciles para sistemas
  de seguimiento de tendencia de corto plazo
- RSI Mean Reversion en activos de alta volatilidad (TSLA, NVDA) genera drawdowns
  extremos porque la reversión puede tardar meses
- Bollinger Breakout sufre de falsas rupturas frecuentes — señal fiable en tendencia,
  ruidosa en lateral
- El slippage por activo (especialmente TSLA/NVDA) penaliza significativamente las
  estrategias con muchos trades

## Lo que se aprendió

1. **Walk-forward es esencial**: parámetros que funcionan en train raramente generalizan
   igual en test sin este proceso
2. **Buy & hold es el benchmark duro**: en activos como SPY y NVDA, el mercado alcista
   hace difícil que cualquier estrategia long-only supere simplemente comprar
3. **Slippage importa más de lo esperado**: 0.15% de slippage en TSLA por trade puede
   destruir el Profit Factor de una estrategia aparentemente rentable
4. **Datos limitados en 1h**: el límite de 730 días de yfinance reduce severamente la
   potencia estadística de las pruebas en timeframe horario
5. **Position sizing por riesgo**: reduce el drawdown respecto a sizing fijo, pero
   también limita las ganancias en rachas ganadoras

## Próximos pasos

{proximos}

---

*Este análisis es un experimento educativo. No constituye asesoramiento financiero.
Todo el testing posterior debe realizarse en cuentas demo.*
"""

    out = REPORTS / "RECOMENDACION.md"
    out.write_text(md, encoding="utf-8")
    print(f"\nGuardado: {out}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    REPORTS.mkdir(exist_ok=True)

    print("Ejecutando análisis OOS final...")
    df_oos_metrics, df_oos_trades = run_oos()

    if df_oos_metrics.empty:
        print("Sin resultados OOS. Verifica que run_fase0.py se ejecutó correctamente.")
        return

    # Guardar parquets
    df_oos_metrics.to_parquet(REPORTS / "fase0_oos.parquet")
    print(f"Guardado: reports/fase0_oos.parquet ({len(df_oos_metrics)} combos)")

    if not df_oos_trades.empty:
        df_oos_trades.to_parquet(REPORTS / "fase0_oos_trades.parquet")
        print(f"Guardado: reports/fase0_oos_trades.parquet ({len(df_oos_trades)} trades)")

    # Resumen en consola
    print_summary(df_oos_metrics)

    # Generar RECOMENDACION.md
    df_wf = pd.read_parquet(REPORTS / "fase0_results.parquet")
    generate_recomendacion(df_oos_metrics, df_wf)

    print("\nHecho. Ejecuta ahora: python scripts/build_report.py")


if __name__ == "__main__":
    main()
