import numpy as np
import pandas as pd
from backtesting.lib import crossover

from .base import StrategyBase
from .indicators import ema, atr


class EMACrossStrategy(StrategyBase):
    """
    Long-only EMA crossover.
    Enter: fast EMA crosses above slow EMA.
    Exit:  fast EMA crosses below slow EMA.
    Stop:  2 × ATR14 below entry price (set at order time).
    """

    fast: int = 9
    slow: int = 21
    atr_mult: float = 2.0

    def init(self):
        close = pd.Series(self.data.Close)
        high  = pd.Series(self.data.High)
        low   = pd.Series(self.data.Low)

        self.ema_fast = self.I(lambda: ema(close, self.fast).values, name="EMA_fast")
        self.ema_slow = self.I(lambda: ema(close, self.slow).values, name="EMA_slow")
        self.atr      = self.I(lambda: atr(high, low, close, 14).values, name="ATR14")

    def next(self):
        if crossover(self.ema_fast, self.ema_slow):
            if not self.position:
                entry = self.data.Close[-1]
                atr   = self.atr[-1]
                stop  = entry - self.atr_mult * atr
                size  = self.position_size(entry, stop)
                if size > 0:
                    self.buy(size=size, sl=stop)

        elif crossover(self.ema_slow, self.ema_fast):
            if self.position.is_long:
                self.position.close()
