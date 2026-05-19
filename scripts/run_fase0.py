"""
Ejecuta walk-forward analysis para las 5 estrategias x 4 tickers x 2 timeframes.
Guarda resultados en reports/fase0_results.parquet.

Uso: python scripts/run_fase0.py
"""
import logging
import sys
import time
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.engine import run_walk_forward
from backtest.grids import ALL_STRATEGIES, GRIDS
from backtest.metrics import passes_filters
from data.loader import load_split

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s %(message)s",
)

TICKERS    = ["SPY", "AAPL", "NVDA", "TSLA"]
TIMEFRAMES = ["1d", "1h"]
REPORTS    = Path(__file__).parent.parent / "reports"


def main():
    REPORTS.mkdir(exist_ok=True)

    combos = [
        (ticker, tf, strategy_cls)
        for ticker    in TICKERS
        for tf        in TIMEFRAMES
        for strategy_cls in ALL_STRATEGIES
    ]

    all_rows = []
    errors   = []
    t0       = time.time()

    for ticker, tf, strategy_cls in tqdm(combos, desc="Walk-forward", unit="combo"):
        try:
            df_train, _ = load_split(ticker, tf)
            grid_info   = GRIDS[strategy_cls]

            wf = run_walk_forward(
                strategy_cls, df_train,
                param_grid=grid_info["grid"],
                constraint=grid_info["constraint"],
                train_months=12, test_months=3, step_months=3,
            )

            if not wf.empty:
                wf["ticker"]    = ticker
                wf["timeframe"] = tf
                wf["strategy"]  = strategy_cls.__name__
                all_rows.append(wf)

        except Exception as exc:
            errors.append(f"{ticker} {tf} {strategy_cls.__name__}: {exc}")

    elapsed = time.time() - t0
    print(f"\nTiempo total: {elapsed:.1f}s")

    ok  = len(combos) - len(errors)
    print(f"Combinaciones OK: {ok}/{len(combos)}")

    if errors:
        print(f"\nERRORES ({len(errors)}):")
        for e in errors:
            print(f"  ERROR {e}")

    if not all_rows:
        print("Sin resultados para guardar.")
        return

    df_all = pd.concat(all_rows, ignore_index=True)
    out = REPORTS / "fase0_results.parquet"
    df_all.to_parquet(out)
    print(f"\nGuardado: {out}  ({len(df_all)} filas, {len(df_all.columns)} cols)")

    # --- Top 10 por Sharpe medio en test ---
    grp = (
        df_all.dropna(subset=["sharpe"])
        .groupby(["strategy", "ticker", "timeframe"])
        .agg(
            sharpe_mean=("sharpe",       "mean"),
            max_dd_mean=("max_drawdown", "mean"),
            pf_mean    =("profit_factor","mean"),
            trades_sum =("num_trades",   "sum"),
            n_folds    =("fold",         "count"),
        )
        .reset_index()
        .sort_values("sharpe_mean", ascending=False)
    )

    print("\nTop 10 combinaciones por Sharpe medio (test folds):")
    print("-" * 80)
    header = f"{'Estrategia':<30} {'Ticker':<6} {'TF':<4} {'Sharpe':>7} {'MaxDD':>7} {'PF':>6} {'Trades':>7} {'Folds':>5}"
    print(header)
    print("-" * 80)
    for _, row in grp.head(10).iterrows():
        print(
            f"{row['strategy']:<30} {row['ticker']:<6} {row['timeframe']:<4}"
            f" {row['sharpe_mean']:>7.3f} {row['max_dd_mean']:>7.1f}"
            f" {row['pf_mean']:>6.2f} {int(row['trades_sum']):>7} {int(row['n_folds']):>5}"
        )

    # --- Cuantas pasan los filtros ---
    # Evaluar sobre Sharpe medio >= 1.0, MaxDD medio < 20, PF medio > 1.3, trades_sum >= 30
    passing = grp[
        (grp["sharpe_mean"]  > 1.0)
        & (grp["max_dd_mean"] < 20.0)
        & (grp["pf_mean"]     > 1.3)
        & (grp["trades_sum"]  >= 30)
    ]
    print(f"\nCombinaciones que pasan los 4 filtros (media folds): {len(passing)}/{len(grp)}")
    if not passing.empty:
        for _, row in passing.iterrows():
            print(f"  OK  {row['strategy']} {row['ticker']} {row['timeframe']}")


if __name__ == "__main__":
    main()
