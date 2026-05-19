import pandas as pd
from backtesting.lib import crossover

from .base import StrategyBase
from .indicators import rsi, atr


class RSIMeanReversionStrategy(StrategyBase):
    """
    Long-only RSI mean-reversion.
    Enter: RSI crosses below oversold threshold.
    Exit:  RSI crosses above overbought threshold.
    Stop:  1.5 × ATR14 below entry.
    """

    rsi_period: int   = 14
    oversold: float   = 30.0
    overbought: float = 70.0
    atr_mult: float   = 1.5

    def init(self):
        close = pd.Series(self.data.Close)
        high  = pd.Series(self.data.High)
        low   = pd.Series(self.data.Low)

        self.rsi = self.I(lambda: rsi(close, self.rsi_period).values, name="RSI")
        self.atr = self.I(lambda: atr(high, low, close, 14).values, name="ATR14")

    def next(self):
        if not self.position:
            if self.rsi[-1] < self.oversold and self.rsi[-2] >= self.oversold:
                entry = self.data.Close[-1]
                stop  = entry - self.atr_mult * self.atr[-1]
                size  = self.position_size(entry, stop)
                if size > 0:
                    self.buy(size=size, sl=stop)
        elif self.position.is_long:
            if self.rsi[-1] > self.overbought:
                self.position.close()
