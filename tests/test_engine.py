"""Tests del motor de backtest y walk-forward."""
import numpy as np
import pandas as pd
import pytest

from strategies import EMACrossStrategy
from backtest.engine import run_single_backtest, run_walk_forward, _METRIC_KEYS
from backtest.grids import GRIDS
from backtest.metrics import passes_filters
from data.loader import TRAIN_END

N = 700  # ~2.7 years of daily bars


def _make_data(n: int = N, seed: int = 0) -> pd.DataFrame:
    rng   = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0.05, 1.0, n))
    close = np.maximum(close, 10.0)
    noise = rng.uniform(0.5, 1.5, n)
    high  = close + noise
    low   = close - noise
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    volume = rng.integers(100_000, 1_000_000, n).astype(float)
    idx = pd.date_range("2023-01-01", periods=n, freq="B", tz="UTC")
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


DATA = _make_data()


class TestRunSingleBacktest:
    def test_returns_all_metric_keys(self):
        result = run_single_backtest(EMACrossStrategy, DATA)
        assert set(_METRIC_KEYS).issubset(result.keys())

    def test_returns_dict(self):
        result = run_single_backtest(EMACrossStrategy, DATA)
        assert isinstance(result, dict)

    def test_num_trades_non_negative(self):
        result = run_single_backtest(EMACrossStrategy, DATA)
        n = result.get("num_trades", 0)
        assert not np.isnan(n) and n >= 0

    def test_empty_df_returns_nan_metrics(self):
        result = run_single_backtest(EMACrossStrategy, pd.DataFrame())
        assert all(np.isnan(v) for v in result.values())

    def test_custom_params_accepted(self):
        result = run_single_backtest(EMACrossStrategy, DATA, params={"fast": 5, "slow": 15})
        assert isinstance(result, dict)
        assert set(_METRIC_KEYS).issubset(result.keys())


class TestWalkForward:
    def test_at_least_3_folds_for_2_years(self):
        """700 business-day bars (~2.7 years) must produce >= 3 folds."""
        wf = run_walk_forward(
            EMACrossStrategy, DATA,
            train_months=12, test_months=3, step_months=3,
        )
        assert len(wf) >= 3, f"Expected >= 3 folds, got {len(wf)}"

    def test_train_test_do_not_overlap(self):
        wf = run_walk_forward(
            EMACrossStrategy, DATA,
            train_months=12, test_months=3, step_months=3,
        )
        assert not wf.empty
        for _, row in wf.iterrows():
            assert row["train_end"] <= row["test_start"], (
                f"Overlap in fold {row['fold']}: "
                f"train_end={row['train_end']} >= test_start={row['test_start']}"
            )

    def test_has_all_metric_columns(self):
        wf = run_walk_forward(
            EMACrossStrategy, DATA,
            train_months=12, test_months=3, step_months=3,
        )
        assert not wf.empty
        for col in _METRIC_KEYS:
            assert col in wf.columns, f"Missing column: {col}"

    def test_with_param_grid(self):
        grid_info = GRIDS[EMACrossStrategy]
        wf = run_walk_forward(
            EMACrossStrategy, DATA,
            param_grid=grid_info["grid"],
            constraint=grid_info["constraint"],
            train_months=12, test_months=3, step_months=3,
        )
        assert len(wf) >= 3

    def test_does_not_exceed_train_end(self):
        """No fold's test window should start at or after the OOS boundary."""
        wf = run_walk_forward(
            EMACrossStrategy, DATA,
            train_months=12, test_months=3, step_months=3,
        )
        if wf.empty:
            return
        for _, row in wf.iterrows():
            assert pd.Timestamp(row["test_start"]) <= pd.Timestamp(TRAIN_END), (
                f"Fold {row['fold']} test_start={row['test_start']} exceeds TRAIN_END={TRAIN_END}"
            )

    def test_empty_df_returns_empty_dataframe(self):
        result = run_walk_forward(EMACrossStrategy, pd.DataFrame())
        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestPassesFilters:
    def _m(self, **kw):
        base = {"sharpe": 1.5, "max_drawdown": 15.0, "profit_factor": 1.5, "num_trades": 50}
        base.update(kw)
        return base

    def test_all_pass(self):
        assert passes_filters(self._m())

    def test_fails_sharpe(self):
        assert not passes_filters(self._m(sharpe=0.9))

    def test_fails_drawdown(self):
        assert not passes_filters(self._m(max_drawdown=25.0))

    def test_fails_profit_factor(self):
        assert not passes_filters(self._m(profit_factor=1.2))

    def test_fails_num_trades(self):
        assert not passes_filters(self._m(num_trades=29))

    def test_nan_sharpe_fails(self):
        assert not passes_filters(self._m(sharpe=np.nan))

    def test_nan_drawdown_fails(self):
        assert not passes_filters(self._m(max_drawdown=np.nan))

    def test_exact_boundary_sharpe(self):
        assert not passes_filters(self._m(sharpe=1.0))  # strictly > 1.0

    def test_exact_boundary_trades(self):
        assert passes_filters(self._m(num_trades=30))   # >= 30
