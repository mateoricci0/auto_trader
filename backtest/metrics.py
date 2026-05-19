import numpy as np


def passes_filters(metrics: dict) -> bool:
    """
    Aplica los 4 filtros de aceptación sobre métricas OOS finales.

    IMPORTANTE: evaluar SOLO sobre el OOS final completo (6 meses para 1d,
    3 meses para 1h), NO sobre folds individuales del walk-forward.
    Filtros: Sharpe > 1.0, MaxDD < 20%, PF > 1.3, NumTrades >= 30.
    """
    sharpe     = metrics.get("sharpe",        np.nan)
    max_dd     = metrics.get("max_drawdown",   np.nan)
    pf         = metrics.get("profit_factor",  np.nan)
    num_trades = metrics.get("num_trades",     0)

    if any(np.isnan(x) for x in [sharpe, max_dd, pf]):
        return False

    return (
        sharpe     > 1.0
        and max_dd  < 20.0
        and pf      > 1.3
        and num_trades >= 30
    )


def beats_buy_hold(metrics: dict) -> bool:
    """
    Retorna True si la estrategia supera el buy & hold en el mismo período.

    Una estrategia que pasa los 4 filtros pero no supera B&H no tiene ventaja
    real sobre simplemente comprar y mantener el activo.
    """
    total_return    = metrics.get("total_return",    np.nan)
    buy_hold_return = metrics.get("buy_hold_return", np.nan)

    if np.isnan(total_return) or np.isnan(buy_hold_return):
        return False

    return total_return > buy_hold_return
