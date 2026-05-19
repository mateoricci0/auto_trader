"""
Parameter grids for walk-forward optimization.
Each entry: {'grid': dict[str, list], 'constraint': callable | None}
Grid sizes: EMA=6, RSI=9, Bollinger=9, MACD=4, ATR=6 — total ~34 combos.
"""
from strategies import (
    ATRTrailingStrategy,
    BollingerBreakoutStrategy,
    EMACrossStrategy,
    MACDTrendStrategy,
    RSIMeanReversionStrategy,
)

GRIDS = {
    EMACrossStrategy: {
        "grid": {
            "fast": [5, 9, 13],
            "slow": [21, 50],
        },
        "constraint": lambda p: p.fast < p.slow,
    },
    RSIMeanReversionStrategy: {
        "grid": {
            "oversold":   [25, 30, 35],
            "overbought": [65, 70, 75],
        },
        "constraint": lambda p: p.oversold < p.overbought,
    },
    BollingerBreakoutStrategy: {
        "grid": {
            "bb_period": [15, 20, 25],
            "bb_std":    [1.5, 2.0, 2.5],
        },
        "constraint": None,
    },
    MACDTrendStrategy: {
        "grid": {
            "fast":   [8, 12],
            "slow":   [21, 26],
            "signal": [9],
        },
        "constraint": lambda p: p.fast < p.slow,
    },
    ATRTrailingStrategy: {
        "grid": {
            "ema_period": [20, 50],
            "atr_mult":   [2.0, 3.0, 4.0],
        },
        "constraint": None,
    },
}

ALL_STRATEGIES = list(GRIDS.keys())
