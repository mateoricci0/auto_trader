import numpy as np


def compute_metrics(equity_curve, trades) -> dict:
    """Placeholder — backtesting.py already computes all needed metrics via stats."""
    return {}


def passes_filters(metrics: dict) -> bool:
    """
    Apply 4 acceptance filters on out-of-sample test metrics.
    Evaluated on the TEST period of each walk-forward fold, not on train.
    """
    sharpe     = metrics.get("sharpe",       np.nan)
    max_dd     = metrics.get("max_drawdown", np.nan)  # positive value, e.g. 15.3 = 15.3%
    pf         = metrics.get("profit_factor", np.nan)
    num_trades = metrics.get("num_trades",   0)

    if any(np.isnan(x) for x in [sharpe, max_dd, pf]):
        return False

    return (
        sharpe     > 1.0
        and max_dd  < 20.0
        and pf      > 1.3
        and num_trades >= 30
    )
