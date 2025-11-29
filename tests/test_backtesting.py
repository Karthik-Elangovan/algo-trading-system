"""
Tests for Backtesting Engine and Performance Metrics.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtesting.engine import BacktestEngine, BacktestConfig
from src.backtesting.metrics import (
    PerformanceMetrics,
    calculate_rolling_sharpe,
    calculate_var,
    calculate_cvar,
)
from src.strategies.base_strategy import Trade


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics calculations."""
    
    @pytest.fixture
    def sample_returns(self):
        """Create sample daily returns."""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.015, 500))
        return returns
    
    @pytest.fixture
    def sample_equity_curve(self):
        """Create sample equity curve."""
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.015, 500)
        equity = 1_000_000 * np.exp(np.cumsum(returns))
        dates = pd.date_range(start="2022-01-01", periods=500, freq="D")
        return pd.Series(equity, index=dates)
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trades."""
        trades = [
            Trade(
                symbol="TEST",
                direction="SHORT",
                quantity=50,
                entry_price=100,
                exit_price=80,
                entry_date=datetime(2023, 1, 1),
                exit_date=datetime(2023, 1, 15),
                pnl=1000,
                exit_reason="Profit target"
            ),
            Trade(
                symbol="TEST",
                direction="SHORT",
                quantity=50,
                entry_price=100,
                exit_price=120,
                entry_date=datetime(2023, 2, 1),
                exit_date=datetime(2023, 2, 15),
                pnl=-1000,
                exit_reason="Stop loss"
            ),
            Trade(
                symbol="TEST",
                direction="SHORT",
                quantity=50,
                entry_price=100,
                exit_price=70,
                entry_date=datetime(2023, 3, 1),
                exit_date=datetime(2023, 3, 15),
                pnl=1500,
                exit_reason="Profit target"
            ),
        ]
        return trades
    
    def test_total_return_calculation(self, sample_equity_curve):
        """Test total return calculation."""
        initial = sample_equity_curve.iloc[0]
        final = sample_equity_curve.iloc[-1]
        expected_return = (final - initial) / initial
        
        calculated = PerformanceMetrics._calculate_total_return(sample_equity_curve)
        
        assert calculated == pytest.approx(expected_return, rel=0.001)
    
    def test_cagr_calculation(self, sample_equity_curve):
        """Test CAGR calculation."""
        cagr = PerformanceMetrics._calculate_cagr(sample_equity_curve, trading_days=252)
        
        # CAGR should be reasonable (between -50% and +100% for test data)
        assert cagr > -0.5
        assert cagr < 1.0
        
        # Verify formula: (Final/Initial)^(1/years) - 1
        initial = sample_equity_curve.iloc[0]
        final = sample_equity_curve.iloc[-1]
        years = len(sample_equity_curve) / 252
        expected_cagr = (final / initial) ** (1 / years) - 1
        
        assert cagr == pytest.approx(expected_cagr, rel=0.001)
    
    def test_sharpe_ratio_calculation(self, sample_returns):
        """Test Sharpe Ratio calculation."""
        sharpe = PerformanceMetrics._calculate_sharpe_ratio(
            sample_returns, risk_free_rate=0.07, trading_days=252
        )
        
        # Sharpe should be a finite number
        assert np.isfinite(sharpe)
        
        # For random data, Sharpe should be close to 0 or slightly positive
        # given the small positive drift
        assert sharpe > -5 and sharpe < 5
    
    def test_sharpe_ratio_zero_volatility(self):
        """Test Sharpe Ratio with zero volatility."""
        # Constant returns
        returns = pd.Series([0.001] * 100)
        
        sharpe = PerformanceMetrics._calculate_sharpe_ratio(
            returns, risk_free_rate=0.07, trading_days=252
        )
        
        # Should handle zero volatility gracefully
        assert sharpe == 0.0
    
    def test_sortino_ratio_calculation(self, sample_returns):
        """Test Sortino Ratio calculation."""
        sortino = PerformanceMetrics._calculate_sortino_ratio(
            sample_returns, risk_free_rate=0.07, trading_days=252
        )
        
        # Sortino should be finite
        assert np.isfinite(sortino)
    
    def test_drawdown_series(self, sample_equity_curve):
        """Test drawdown series calculation."""
        dd_series = PerformanceMetrics._calculate_drawdown_series(sample_equity_curve)
        
        # Drawdowns should be <= 0
        assert dd_series.max() <= 0.0001  # Allow small floating point error
        
        # Should have same length as equity curve
        assert len(dd_series) == len(sample_equity_curve)
    
    def test_max_drawdown(self, sample_equity_curve):
        """Test maximum drawdown calculation."""
        dd_series = PerformanceMetrics._calculate_drawdown_series(sample_equity_curve)
        max_dd = abs(dd_series.min())
        
        # Max drawdown should be positive
        assert max_dd >= 0
        
        # Max drawdown should be less than 100%
        assert max_dd < 1.0
    
    def test_trade_statistics(self, sample_trades):
        """Test trade statistics calculation."""
        metrics = PerformanceMetrics()
        metrics._calculate_trade_statistics(sample_trades)
        
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
        assert metrics.win_rate == pytest.approx(2/3, rel=0.01)
        
        # Profit factor = gross profit / gross loss = 2500 / 1000 = 2.5
        assert metrics.profit_factor == pytest.approx(2.5, rel=0.01)
    
    def test_consecutive_wins_losses(self, sample_trades):
        """Test consecutive wins/losses calculation."""
        # Arrange trades: win, loss, win
        max_wins, max_losses = PerformanceMetrics._calculate_consecutive_trades(sample_trades)
        
        assert max_wins == 1  # No consecutive wins
        assert max_losses == 1  # No consecutive losses
    
    def test_from_returns_factory(self, sample_returns, sample_equity_curve, sample_trades):
        """Test factory method creates complete metrics."""
        metrics = PerformanceMetrics.from_returns(
            returns=sample_returns,
            equity_curve=sample_equity_curve,
            trades=sample_trades,
            risk_free_rate=0.07
        )
        
        # Should have all metrics calculated
        assert metrics.total_return != 0
        assert metrics.sharpe_ratio != 0 or metrics.volatility == 0
        assert metrics.total_trades == 3
    
    def test_metrics_to_dict(self, sample_returns, sample_equity_curve, sample_trades):
        """Test conversion to dictionary."""
        metrics = PerformanceMetrics.from_returns(
            returns=sample_returns,
            equity_curve=sample_equity_curve,
            trades=sample_trades,
            risk_free_rate=0.07
        )
        
        metrics_dict = metrics.to_dict()
        
        assert "total_return" in metrics_dict
        assert "sharpe_ratio" in metrics_dict
        assert "max_drawdown" in metrics_dict
        assert "win_rate" in metrics_dict


class TestVaRCalculations:
    """Tests for VaR and CVaR calculations."""
    
    @pytest.fixture
    def sample_returns(self):
        """Create sample returns with known distribution."""
        np.random.seed(42)
        return pd.Series(np.random.normal(0, 0.01, 1000))
    
    def test_historical_var(self, sample_returns):
        """Test historical VaR calculation."""
        var_95 = calculate_var(sample_returns, confidence=0.95, method="historical")
        
        # VaR should be positive
        assert var_95 > 0
        
        # 95% VaR should be approximately 1.65 * std for normal distribution
        expected_var = 1.645 * sample_returns.std()
        assert var_95 == pytest.approx(expected_var, rel=0.15)
    
    def test_cvar(self, sample_returns):
        """Test CVaR (Expected Shortfall) calculation."""
        cvar_95 = calculate_cvar(sample_returns, confidence=0.95)
        var_95 = calculate_var(sample_returns, confidence=0.95)
        
        # CVaR should be >= VaR
        assert cvar_95 >= var_95 * 0.95  # Allow small tolerance
    
    def test_rolling_sharpe(self, sample_returns):
        """Test rolling Sharpe calculation."""
        rolling_sharpe = calculate_rolling_sharpe(
            sample_returns, window=60, risk_free_rate=0.07
        )
        
        # Should have same length as input
        assert len(rolling_sharpe) == len(sample_returns)
        
        # First 60-1 values should be NaN
        assert rolling_sharpe.iloc[:59].isna().all()


class TestBacktestEngine:
    """Tests for BacktestEngine."""
    
    @pytest.fixture
    def engine(self):
        """Create backtest engine."""
        return BacktestEngine(
            initial_capital=1_000_000,
            config={
                "slippage_pct": 0.005,
                "brokerage_per_order": 20,
                "stt_rate": 0.0005,
            }
        )
    
    @pytest.fixture
    def sample_data(self):
        """Create sample options data."""
        from src.data.historical_data import HistoricalDataFetcher
        
        fetcher = HistoricalDataFetcher()
        data = fetcher.load_nifty_options(
            start_date="2023-01-01",
            end_date="2023-03-31",
            use_mock=True
        )
        return data
    
    def test_engine_initialization(self, engine):
        """Test engine initializes correctly."""
        assert engine.config.initial_capital == 1_000_000
        assert engine.config.slippage_pct == 0.005
        assert engine.config.brokerage_per_order == 20
    
    def test_transaction_cost_calculation(self, engine):
        """Test transaction cost calculation."""
        # Test sell transaction (includes STT)
        cost_sell = engine._calculate_transaction_cost(100_000, is_sell=True)
        
        # Should include: brokerage + STT + exchange + GST + SEBI
        assert cost_sell > 0
        
        # Test buy transaction (no STT)
        cost_buy = engine._calculate_transaction_cost(100_000, is_sell=False)
        
        # Buy should be less than sell (no STT)
        assert cost_buy < cost_sell
    
    def test_transaction_cost_components(self, engine):
        """Test individual transaction cost components."""
        value = 100_000
        
        # Calculate expected components
        brokerage = engine.config.brokerage_per_order * 2  # 2 legs
        stt = value * engine.config.stt_rate
        exchange = value * engine.config.exchange_charges_rate
        gst = (brokerage + exchange) * engine.config.gst_rate
        
        total_sell = engine._calculate_transaction_cost(value, is_sell=True)
        
        # Total should be sum of components (approximately)
        expected_min = brokerage + stt + exchange + gst
        assert total_sell >= expected_min * 0.9  # Allow 10% tolerance


class TestBacktestConfig:
    """Tests for BacktestConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = BacktestConfig()
        
        assert config.initial_capital == 1_000_000
        assert config.slippage_pct == 0.005
        assert config.risk_free_rate == 0.07
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = BacktestConfig(
            initial_capital=500_000,
            slippage_pct=0.01,
            brokerage_per_order=25
        )
        
        assert config.initial_capital == 500_000
        assert config.slippage_pct == 0.01
        assert config.brokerage_per_order == 25


class TestDrawdownCalculations:
    """Tests for drawdown-related calculations."""
    
    def test_simple_drawdown(self):
        """Test simple drawdown scenario."""
        # Equity: 100, 110, 100, 105, 90, 100
        equity = pd.Series([100, 110, 100, 105, 90, 100])
        
        dd = PerformanceMetrics._calculate_drawdown_series(equity)
        
        # At peak (110), drawdown = 0
        assert dd.iloc[1] == pytest.approx(0, abs=0.001)
        
        # At 100 after peak of 110, drawdown = (100-110)/110 = -9.09%
        assert dd.iloc[2] == pytest.approx(-0.0909, abs=0.01)
        
        # At 90 (lowest), drawdown from peak of 110 = (90-110)/110 = -18.18%
        assert dd.iloc[4] == pytest.approx(-0.1818, abs=0.01)
    
    def test_max_drawdown_duration(self):
        """Test max drawdown duration calculation."""
        # Create drawdown series with known duration
        dd = pd.Series([0, -0.05, -0.10, -0.15, -0.10, 0, 0])
        
        duration = PerformanceMetrics._calculate_max_drawdown_duration(dd)
        
        # Duration from index 1 to 4 = 4 days in drawdown
        assert duration == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
