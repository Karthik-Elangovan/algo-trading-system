"""
Tests for Premium Selling Strategy (Short Strangle).
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.premium_selling import (
    PremiumSellingStrategy,
    StranglePosition,
)
from src.strategies.base_strategy import Signal, SignalType
from src.data.historical_data import HistoricalDataFetcher


class TestStranglePosition:
    """Tests for StranglePosition dataclass."""
    
    @pytest.fixture
    def sample_strangle(self):
        """Create sample strangle position."""
        return StranglePosition(
            underlying="NIFTY",
            expiry=datetime(2023, 3, 30),
            call_strike=18500,
            put_strike=17500,
            call_premium=100,
            put_premium=120,
            total_premium=220,
            entry_date=datetime(2023, 3, 15),
            quantity=2,
            call_current_price=100,
            put_current_price=120,
            entry_iv_rank=75,
            entry_spot=18000,
        )
    
    def test_initial_cost_to_close(self, sample_strangle):
        """Test cost to close at entry equals premium."""
        cost = sample_strangle.get_current_cost_to_close()
        
        # At entry, cost to close = (100 + 120) * 2 = 440
        assert cost == 440
    
    def test_unrealized_pnl_at_entry(self, sample_strangle):
        """Test unrealized PnL at entry is zero."""
        pnl = sample_strangle.get_unrealized_pnl()
        
        # At entry, PnL should be zero
        assert pnl == pytest.approx(0, abs=0.01)
    
    def test_unrealized_pnl_profit(self, sample_strangle):
        """Test unrealized PnL when in profit."""
        # Options decayed to half
        sample_strangle.call_current_price = 50
        sample_strangle.put_current_price = 60
        
        pnl = sample_strangle.get_unrealized_pnl()
        
        # Premium received = 220 * 2 = 440
        # Cost to close = (50 + 60) * 2 = 220
        # PnL = 440 - 220 = 220
        assert pnl == pytest.approx(220, abs=0.01)
    
    def test_unrealized_pnl_loss(self, sample_strangle):
        """Test unrealized PnL when in loss."""
        # Options increased
        sample_strangle.call_current_price = 200
        sample_strangle.put_current_price = 180
        
        pnl = sample_strangle.get_unrealized_pnl()
        
        # Premium received = 220 * 2 = 440
        # Cost to close = (200 + 180) * 2 = 760
        # PnL = 440 - 760 = -320
        assert pnl == pytest.approx(-320, abs=0.01)
    
    def test_profit_percentage(self, sample_strangle):
        """Test profit percentage calculation."""
        # 50% profit scenario
        sample_strangle.call_current_price = 50
        sample_strangle.put_current_price = 60
        
        profit_pct = sample_strangle.get_profit_percentage()
        
        # PnL = 220, Total premium = 220 * 2 = 440
        # Profit % = 220 / 440 = 0.5 = 50%
        assert profit_pct == pytest.approx(0.5, abs=0.01)


class TestPremiumSellingStrategy:
    """Tests for PremiumSellingStrategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create strategy instance with default config."""
        config = {
            "iv_rank_entry_threshold": 70,
            "delta_range": (0.15, 0.20),
            "profit_target_pct": 0.50,
            "stop_loss_pct": 1.50,
            "days_before_expiry_exit": 3,
            "position_size_pct": 0.02,
            "min_days_to_expiry": 7,
            "max_days_to_expiry": 45,
            "max_positions": 5,
            "lot_sizes": {"NIFTY": 50, "BANKNIFTY": 15, "SENSEX": 10},
        }
        return PremiumSellingStrategy(config=config)
    
    @pytest.fixture
    def sample_data(self):
        """Create sample options data."""
        fetcher = HistoricalDataFetcher()
        data = fetcher.load_nifty_options(
            start_date="2023-01-01",
            end_date="2023-03-31",
            use_mock=True
        )
        return data
    
    def test_strategy_initialization(self, strategy):
        """Test strategy initializes with correct config."""
        assert strategy.name == "PremiumSellingStrategy"
        assert strategy.config["iv_rank_entry_threshold"] == 70
        assert strategy.config["profit_target_pct"] == 0.50
        assert strategy.config["stop_loss_pct"] == 1.50
    
    def test_strategy_initialize_with_data(self, strategy, sample_data):
        """Test strategy initialization with data."""
        strategy.initialize(sample_data)
        
        # Strategy should be initialized
        assert strategy._is_initialized
        assert strategy._iv_calculator is not None
    
    def test_position_size_calculation(self, strategy):
        """Test position size calculation for strangle."""
        capital = 1_000_000
        
        signal = Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol="NIFTY_STRANGLE",
            timestamp=datetime.now(),
            metadata={
                "strategy": "short_strangle",
                "underlying": "NIFTY",
                "total_premium": 200,
            }
        )
        
        quantity = strategy.calculate_position_size(capital, 200, signal)
        
        # Should return at least 1
        assert quantity >= 1
        
        # Check calculation
        # max_risk = 1,000,000 * 0.02 = 20,000
        # risk_per_strangle = 200 * 1.50 * 50 = 15,000
        # num_strangles = 20,000 / 15,000 = 1.33 -> 1
        expected = int(20_000 / (200 * 1.50 * 50))
        assert quantity == max(1, expected)
    
    def test_open_strangle(self, strategy):
        """Test opening a strangle position."""
        signal = Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol="NIFTY_STRANGLE",
            timestamp=datetime(2023, 3, 15),
            metadata={
                "strategy": "short_strangle",
                "underlying": "NIFTY",
                "expiry": datetime(2023, 3, 30),
                "call_strike": 18500,
                "put_strike": 17500,
                "call_premium": 100,
                "put_premium": 120,
                "total_premium": 220,
                "spot_price": 18000,
                "iv_rank": 75,
            }
        )
        
        strangle = strategy.open_strangle(signal, quantity=2)
        
        assert strangle.underlying == "NIFTY"
        assert strangle.call_strike == 18500
        assert strangle.put_strike == 17500
        assert strangle.total_premium == 220
        assert strangle.quantity == 2
        assert len(strategy.strangle_positions) == 1
    
    def test_close_strangle(self, strategy):
        """Test closing a strangle position."""
        # First open a position
        entry_signal = Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol="NIFTY_STRANGLE",
            timestamp=datetime(2023, 3, 15),
            metadata={
                "strategy": "short_strangle",
                "underlying": "NIFTY",
                "expiry": datetime(2023, 3, 30),
                "call_strike": 18500,
                "put_strike": 17500,
                "call_premium": 100,
                "put_premium": 120,
                "total_premium": 220,
                "spot_price": 18000,
                "iv_rank": 75,
            }
        )
        
        strangle = strategy.open_strangle(entry_signal, quantity=2)
        pos_id = list(strategy.strangle_positions.keys())[0]
        
        # Simulate profit scenario
        strangle.call_current_price = 50
        strangle.put_current_price = 60
        
        exit_signal = Signal(
            signal_type=SignalType.EXIT_SHORT,
            symbol=pos_id,
            timestamp=datetime(2023, 3, 25),
            reason="Profit target",
            metadata={"exit_type": "profit_target"}
        )
        
        trade = strategy.close_strangle(pos_id, exit_signal)
        
        assert trade is not None
        assert trade.direction == "SHORT"
        assert trade.exit_reason == "Profit target"
        assert len(strategy.strangle_positions) == 0
        assert len(strategy.trades) == 1
    
    def test_max_positions_limit(self, strategy):
        """Test that strategy respects max positions limit."""
        # Fill up positions
        for i in range(strategy.config["max_positions"]):
            signal = Signal(
                signal_type=SignalType.ENTRY_SHORT,
                symbol=f"NIFTY_STRANGLE_{i}",
                timestamp=datetime(2023, 3, 15),
                metadata={
                    "strategy": "short_strangle",
                    "underlying": "NIFTY",
                    "expiry": datetime(2023, 3, 30) + timedelta(days=i*7),
                    "call_strike": 18500 + i*100,
                    "put_strike": 17500 - i*100,
                    "call_premium": 100,
                    "put_premium": 120,
                    "total_premium": 220,
                    "spot_price": 18000,
                    "iv_rank": 75,
                }
            )
            strategy.open_strangle(signal, quantity=1)
        
        assert len(strategy.strangle_positions) == strategy.config["max_positions"]
    
    def test_strategy_reset(self, strategy, sample_data):
        """Test strategy reset clears all state."""
        strategy.initialize(sample_data)
        
        # Add some state
        signal = Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol="NIFTY_STRANGLE",
            timestamp=datetime(2023, 3, 15),
            metadata={
                "strategy": "short_strangle",
                "underlying": "NIFTY",
                "expiry": datetime(2023, 3, 30),
                "call_strike": 18500,
                "put_strike": 17500,
                "call_premium": 100,
                "put_premium": 120,
                "total_premium": 220,
                "spot_price": 18000,
            }
        )
        strategy.open_strangle(signal, quantity=1)
        
        # Reset
        strategy.reset()
        
        assert len(strategy.strangle_positions) == 0
        assert len(strategy.trades) == 0
        assert not strategy._is_initialized
    
    def test_strategy_statistics(self, strategy):
        """Test strategy statistics generation."""
        stats = strategy.get_strategy_statistics()
        
        assert "total_trades" in stats
        assert "open_positions" in stats
        assert "config" in stats


class TestEntryExitConditions:
    """Tests for entry and exit condition logic."""
    
    @pytest.fixture
    def strategy(self):
        """Create strategy instance."""
        return PremiumSellingStrategy(config={
            "iv_rank_entry_threshold": 70,
            "profit_target_pct": 0.50,
            "stop_loss_pct": 1.50,
            "days_before_expiry_exit": 3,
        })
    
    def test_profit_target_exit(self, strategy):
        """Test exit at profit target."""
        # Open position
        entry_signal = Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol="NIFTY_STRANGLE",
            timestamp=datetime(2023, 3, 1),
            metadata={
                "strategy": "short_strangle",
                "underlying": "NIFTY",
                "expiry": datetime(2023, 3, 30),
                "call_strike": 18500,
                "put_strike": 17500,
                "call_premium": 100,
                "put_premium": 100,
                "total_premium": 200,
                "spot_price": 18000,
            }
        )
        strangle = strategy.open_strangle(entry_signal, quantity=1)
        
        # Simulate 50% profit (options at half price)
        strangle.call_current_price = 50
        strangle.put_current_price = 50
        
        profit_pct = strangle.get_profit_percentage()
        
        # Should trigger profit target
        assert profit_pct >= strategy.config["profit_target_pct"]
    
    def test_stop_loss_exit(self, strategy):
        """Test exit at stop loss."""
        # Open position
        entry_signal = Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol="NIFTY_STRANGLE",
            timestamp=datetime(2023, 3, 1),
            metadata={
                "strategy": "short_strangle",
                "underlying": "NIFTY",
                "expiry": datetime(2023, 3, 30),
                "call_strike": 18500,
                "put_strike": 17500,
                "call_premium": 100,
                "put_premium": 100,
                "total_premium": 200,
                "spot_price": 18000,
            }
        )
        strangle = strategy.open_strangle(entry_signal, quantity=1)
        
        # Simulate stop loss (options at 2.5x price = 150% loss)
        strangle.call_current_price = 250
        strangle.put_current_price = 250
        
        # Cost to close = 500, Initial credit = 200
        # This exceeds stop loss threshold
        current_cost = strangle.get_current_cost_to_close()
        initial_credit = strangle.total_premium * strangle.quantity
        stop_loss_threshold = initial_credit * (1 + strategy.config["stop_loss_pct"])
        
        assert current_cost >= stop_loss_threshold


class TestIVRankIntegration:
    """Tests for IV Rank integration with strategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create strategy with IV calculator."""
        return PremiumSellingStrategy(config={
            "iv_rank_entry_threshold": 70,
        })
    
    @pytest.fixture
    def high_iv_data(self):
        """Create data with high IV regime."""
        fetcher = HistoricalDataFetcher()
        data = fetcher.load_nifty_options(
            start_date="2023-01-01",
            end_date="2023-06-30",
            use_mock=True
        )
        
        # Artificially increase IV to simulate high IV regime
        data = data.copy()
        data["iv"] = data["iv"] * 1.5
        
        return data
    
    def test_iv_series_extraction(self, strategy, high_iv_data):
        """Test ATM IV series extraction."""
        iv_series = strategy._extract_atm_iv_series(high_iv_data)
        
        # Should have IV values
        assert len(iv_series) > 0
        
        # IV should be positive
        assert (iv_series > 0).all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
