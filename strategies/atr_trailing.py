import numpy as np
import pandas as pd
import ta

from .base import StrategyBase


class ATRTrailingStrategy(StrategyBase):
    """
    Long-only ATR trailing stop.
    Enter: Close > EMA50 (trend filter).
    Stop:  max(prev_stop, Close - atr_mult × ATR14) — ratchets up, never down.
    """

    ema_period: int   = 50
    atr_period: int   = 14
    atr_mult: float   = 3.0

    def init(self):
        close = pd.Series(self.data.Close)
        high  = pd.Series(self.data.High)
        low   = pd.Series(self.data.Low)

        self.ema = self.I(
            lambda: ta.trend.ema_indicator(close, window=self.ema_period).values,
            name="EMA50",
        )
        self.atr = self.I(
            lambda: ta.volatility.average_true_range(high, low, close, window=self.atr_period).values,
            name="ATR14",
        )
        self._trailing_stop: float = np.nan

    def next(self):
        close = self.data.Close[-1]
        trail = close - self.atr_mult * self.atr[-1]

        if not self.position:
            if close > self.ema[-1]:
                self._trailing_stop = trail
                size = self.position_size(close, self._trailing_stop)
                if size > 0:
                    self.buy(size=size)
        elif self.position.is_long:
            self._trailing_stop = max(self._trailing_stop, trail)
            if close < self._trailing_stop:
                self.position.close()
                self._trailing_stop = np.nan
