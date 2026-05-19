from backtesting import Strategy


class StrategyBase(Strategy):
    """Base class with risk-based position sizing."""

    risk_per_trade: float = 0.02  # fraction of equity risked per trade

    def position_size(self, entry_price: float, stop_price: float) -> float:
        """Return fraction of equity to use (0–0.95) given entry and stop prices."""
        stop_distance = abs(entry_price - stop_price)
        if stop_distance <= 0:
            return 0.0
        risk_amount = self.equity * self.risk_per_trade
        shares = risk_amount / stop_distance
        fraction = shares * entry_price / self.equity
        return min(max(fraction, 0.0), 0.95)

    def log_trade(self, action: str, price: float, **kwargs) -> None:
        pass  # backtesting.py records all trade info in its stats output
