import pandas as pd
import ta

from .base import StrategyBase


class BollingerBreakoutStrategy(StrategyBase):
    """
    Long-only Bollinger Band breakout with volume confirmation.
    Enter: Close breaks above upper band AND volume > 1.5 × SMA20(volume).
    Exit:  Close falls below middle band (SMA20).
    Stop:  lower band at entry bar.
    """

    bb_period: int     = 20
    bb_std: float      = 2.0
    vol_mult: float    = 1.5

    def init(self):
        close  = pd.Series(self.data.Close)
        volume = pd.Series(self.data.Volume)

        self.bb_upper = self.I(
            lambda: ta.volatility.bollinger_hband(close, window=self.bb_period, window_dev=self.bb_std).values,
            name="BB_upper",
        )
        self.bb_mid = self.I(
            lambda: ta.volatility.bollinger_mavg(close, window=self.bb_period).values,
            name="BB_mid",
        )
        self.bb_lower = self.I(
            lambda: ta.volatility.bollinger_lband(close, window=self.bb_period, window_dev=self.bb_std).values,
            name="BB_lower",
        )
        self.vol_avg = self.I(
            lambda: volume.rolling(self.bb_period).mean().values,
            name="Vol_avg",
        )

    def next(self):
        close  = self.data.Close[-1]
        volume = self.data.Volume[-1]

        if not self.position:
            if (close > self.bb_upper[-1]
                    and volume > self.vol_mult * self.vol_avg[-1]):
                stop = self.bb_lower[-1]
                size = self.position_size(close, stop)
                if size > 0:
                    self.buy(size=size, sl=stop)
        elif self.position.is_long:
            if close < self.bb_mid[-1]:
                self.position.close()
