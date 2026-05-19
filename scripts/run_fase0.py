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
from data.loader import load_split

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s %(message)s",
)

TICKERS    = ["SPY", "AAPL", "NVDA", "TSLA"]
TIMEFRAMES = ["1d", "1h"]
REPORTS    = Path(__file__).parent.parent / "reports"

# Slippage conservador por activo — aproximaciones, no medidas (FIX auditoría)
SLIPPAGE = {
    "SPY":  0.0003,
    "AAPL": 0.0005,
    "NVDA": 0.0010,
    "TSLA": 0.0015,
}

# Tamaño de ventanas según timeframe (FIX: 1h usa ventanas más cortas)
FOLD_PARAMS = {
    "1d": dict(train_months=12, test_months=3, step_months=3),
    "1h": dict(train_months=4,  test_months=1, step_months=1),
}


def main():
    REPORTS.mkdir(exist_ok=True)

    combos = [
        (ticker, tf, strategy_cls)
        for ticker       in TICKERS
        for tf           in TIMEFRAMES
        for strategy_cls in ALL_STRATEGIES
    ]

    all_rows = []
    errors   = []
    t0       = time.time()

    for ticker, tf, strategy_cls in tqdm(combos, desc="Walk-forward", unit="combo"):
        try:
            df_train, _ = load_split(ticker, tf)
            grid_info   = GRIDS[strategy_cls]
            slippage    = SLIPPAGE.get(ticker, 0.0005)

            wf = run_walk_forward(
                strategy_cls, df_train,
                param_grid=grid_info["grid"],
                constraint=grid_info["constraint"],
                slippage=slippage,
                **FOLD_PARAMS[tf],
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

    ok = len(combos) - len(errors)
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

    # Top 10 por Sharpe medio en folds de test
    grp = (
        df_all.dropna(subset=["sharpe"])
        .groupby(["strategy", "ticker", "timeframe"])
        .agg(
            sharpe_mean=("sharpe",        "mean"),
            max_dd_mean=("max_drawdown",  "mean"),
            pf_mean    =("profit_factor", "mean"),
            trades_sum =("num_trades",    "sum"),
            n_folds    =("fold",          "count"),
        )
        .reset_index()
        .sort_values("sharpe_mean", ascending=False)
    )

    print("\nTop 10 combinaciones por Sharpe medio (folds de test):")
    print("-" * 84)
    header = (
        f"{'Estrategia':<28} {'Ticker':<6} {'TF':<4}"
        f" {'Sharpe':>7} {'MaxDD':>7} {'PF':>6} {'Trades':>7} {'Folds':>5}"
    )
    print(header)
    print("-" * 84)
    for _, row in grp.head(10).iterrows():
        print(
            f"{row['strategy']:<28} {row['ticker']:<6} {row['timeframe']:<4}"
            f" {row['sharpe_mean']:>7.3f} {row['max_dd_mean']:>7.1f}"
            f" {row['pf_mean']:>6.2f} {int(row['trades_sum']):>7} {int(row['n_folds']):>5}"
        )

    # Filtros sobre agregación de folds (orientativo — el criterio final es OOS)
    passing = grp[
        (grp["sharpe_mean"]  > 1.0)
        & (grp["max_dd_mean"] < 20.0)
        & (grp["pf_mean"]     > 1.3)
        & (grp["trades_sum"]  >= 30)
    ]
    print(
        f"\nCombinaciones orientativamente dentro de filtros (media folds): "
        f"{len(passing)}/{len(grp)}"
    )
    print("(El veredicto real es sobre OOS final — ejecuta run_oos_final.py)")
    if not passing.empty:
        for _, row in passing.iterrows():
            print(f"  -> {row['strategy']} {row['ticker']} {row['timeframe']}")


if __name__ == "__main__":
    main()
