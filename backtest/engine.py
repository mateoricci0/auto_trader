import contextlib
import io
import logging

import numpy as np
import pandas as pd
from backtesting import Backtest

from data.loader import TRAIN_END

logger = logging.getLogger(__name__)

_METRIC_KEYS = (
    "sharpe", "max_drawdown", "profit_factor", "num_trades",
    "win_rate", "total_return", "cagr", "calmar", "buy_hold_return",
)


def _empty_metrics() -> dict:
    return {k: np.nan for k in _METRIC_KEYS}


def _extract_metrics(stats) -> dict:
    def _get(key, default=np.nan):
        try:
            v = stats[key]
        except (KeyError, TypeError):
            return default
        return v if v is not None and not (isinstance(v, float) and np.isnan(v)) else default

    max_dd = _get("Max. Drawdown [%]")
    if not np.isnan(max_dd):
        max_dd = abs(max_dd)

    # CAGR key varies by backtesting.py version
    cagr = _get("CAGR [%]")
    if np.isnan(cagr):
        cagr = _get("Return (Ann.) [%]")

    return {
        "sharpe":          _get("Sharpe Ratio"),
        "max_drawdown":    max_dd,
        "profit_factor":   _get("Profit Factor"),
        "num_trades":      _get("# Trades", 0),
        "win_rate":        _get("Win Rate [%]"),
        "total_return":    _get("Return [%]"),
        "cagr":            cagr,
        "calmar":          _get("Calmar Ratio"),
        "buy_hold_return": _get("Buy & Hold Return [%]"),
    }


def _run_bt(bt: Backtest, **kwargs) -> object:
    """Run a Backtest silently (suppresses backtesting.py's tqdm progress bar)."""
    with contextlib.redirect_stderr(io.StringIO()):
        return bt.run(**kwargs)


def run_single_backtest(
    strategy_class,
    df: pd.DataFrame,
    params: dict | None = None,
    cash: float = 10_000,
    slippage: float = 0.0005,
) -> dict:
    """
    Run one backtest and return a metrics dict.
    slippage is applied as commission (per-side fraction of trade value).
    """
    if df is None or df.empty or len(df) < 10:
        return _empty_metrics()

    try:
        bt = Backtest(
            df,
            strategy_class,
            cash=cash,
            commission=slippage,
            exclusive_orders=True,
            finalize_trades=True,
        )
        stats = _run_bt(bt, **(params or {}))
        return _extract_metrics(stats)
    except Exception as exc:
        logger.warning("run_single_backtest failed (%s): %s", strategy_class.__name__, exc)
        return _empty_metrics()


def run_oos_backtest(
    strategy_class,
    df: pd.DataFrame,
    params: dict | None = None,
    cash: float = 10_000,
    slippage: float = 0.0005,
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """
    Run a backtest and return (metrics, trades_df, equity_df).
    Used for OOS final analysis — returns full detail, not just scalars.
    """
    _empty_df = pd.DataFrame()

    if df is None or df.empty or len(df) < 10:
        return _empty_metrics(), _empty_df, _empty_df

    try:
        bt = Backtest(
            df,
            strategy_class,
            cash=cash,
            commission=slippage,
            exclusive_orders=True,
            finalize_trades=True,
        )
        stats = _run_bt(bt, **(params or {}))
        metrics = _extract_metrics(stats)

        try:
            trades = stats["_trades"].copy()
        except (KeyError, TypeError):
            trades = _empty_df

        try:
            equity = stats["_equity_curve"].copy()
        except (KeyError, TypeError):
            equity = _empty_df

        return metrics, trades, equity
    except Exception as exc:
        logger.warning("run_oos_backtest failed (%s): %s", strategy_class.__name__, exc)
        return _empty_metrics(), _empty_df, _empty_df


def run_walk_forward(
    strategy_class,
    df: pd.DataFrame,
    param_grid: dict | None = None,
    constraint=None,
    train_months: int = 12,
    test_months: int = 3,
    step_months: int = 3,
    cash: float = 10_000,
    slippage: float = 0.0005,
) -> pd.DataFrame:
    """
    Walk-forward analysis: optimize on train window, evaluate on test window.

    The function caps the data at TRAIN_END — OOS final data is never touched here.
    Params are chosen by best Sharpe on TRAIN (no leakage into test).
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Hard cap: never use OOS final data
    oos_boundary = pd.Timestamp(TRAIN_END, tz="UTC") + pd.Timedelta(days=1)
    df = df[df.index < oos_boundary].copy()

    if df.empty:
        return pd.DataFrame()

    first_bar = df.index[0]
    fold_start = first_bar.normalize().replace(day=1)

    folds = []

    while True:
        train_end  = fold_start + pd.DateOffset(months=train_months)
        test_start = train_end
        test_end   = test_start + pd.DateOffset(months=test_months)

        if test_start >= df.index[-1]:
            break

        df_train = df[(df.index >= fold_start) & (df.index < train_end)]
        df_test  = df[(df.index >= test_start) & (df.index < test_end)]

        if len(df_train) < 30 or len(df_test) < 5:
            fold_start += pd.DateOffset(months=step_months)
            continue

        # Optimize on TRAIN — pick best Sharpe in TRAIN (no leakage)
        best_params: dict = {}
        if param_grid:
            try:
                bt_train = Backtest(
                    df_train, strategy_class,
                    cash=cash, commission=slippage,
                    exclusive_orders=True, finalize_trades=True,
                )
                opt_kwargs = dict(**param_grid)
                opt_kwargs["maximize"] = _maximize_sharpe
                if constraint is not None:
                    opt_kwargs["constraint"] = constraint

                with contextlib.redirect_stderr(io.StringIO()):
                    opt_stats = bt_train.optimize(**opt_kwargs)

                best_params = {k: getattr(opt_stats._strategy, k) for k in param_grid}
            except Exception as exc:
                logger.warning(
                    "Optimization failed (fold %d, %s): %s",
                    len(folds) + 1, strategy_class.__name__, exc,
                )

        # Evaluate test fold with best params from TRAIN
        test_metrics = run_single_backtest(
            strategy_class, df_test, params=best_params,
            cash=cash, slippage=slippage,
        )
        test_metrics.update({
            "fold":         len(folds) + 1,
            "train_start":  str(fold_start.date()),
            "train_end":    str(train_end.date()),
            "test_start":   str(test_start.date()),
            "test_end":     str(test_end.date()),
            "n_train_bars": len(df_train),
            "n_test_bars":  len(df_test),
            "best_params":  str(best_params),
        })
        folds.append(test_metrics)

        fold_start += pd.DateOffset(months=step_months)

    return pd.DataFrame(folds)


def _maximize_sharpe(stats) -> float:
    """Maximize function for bt.optimize(): returns Sharpe or -inf on NaN."""
    try:
        s = stats["Sharpe Ratio"]
    except (KeyError, TypeError):
        return -np.inf
    return float(s) if not pd.isna(s) else -np.inf
