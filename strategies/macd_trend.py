import pandas as pd
from backtesting.lib import crossover

from .base import StrategyBase
from .indicators import macd, atr


class MACDTrendStrategy(StrategyBase):
    """
    Long-only MACD trend-following.
    Enter: MACD line crosses above signal AND MACD > 0.
    Exit:  MACD line crosses below signal.
    Stop:  1.5 × ATR14 below entry.
    """

    fast: int   = 12
    slow: int   = 26
    signal: int = 9
    atr_mult: float = 1.5

    def init(self):
        close = pd.Series(self.data.Close)
        high  = pd.Series(self.data.High)
        low   = pd.Series(self.data.Low)

        macd_line, macd_sig = macd(close, self.fast, self.slow, self.signal)
        self.macd_line = self.I(lambda: macd_line.values, name="MACD")
        self.macd_sig  = self.I(lambda: macd_sig.values,  name="MACD_signal")
        self.atr       = self.I(lambda: atr(high, low, close, 14).values, name="ATR14")

    def next(self):
        if not self.position:
            if (crossover(self.macd_line, self.macd_sig)
                    and self.macd_line[-1] > 0):
                entry = self.data.Close[-1]
                stop  = entry - self.atr_mult * self.atr[-1]
                size  = self.position_size(entry, stop)
                if size > 0:
                    self.buy(size=size, sl=stop)
        elif self.position.is_long:
            if crossover(self.macd_sig, self.macd_line):
                self.position.close()
