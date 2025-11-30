"""
Tests for Iron Condor Strategy.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.iron_condor import (
    IronCondorStrategy,
    IronCondorPosition,
)
from src.strategies.base_strategy import Signal, SignalType
from src.data.historical_data import HistoricalDataFetcher


class TestIronCondorPosition:
    """Tests for IronCondorPosition dataclass."""
    
    @pytest.fixture
    def sample_iron_condor(self):
        """Create sample iron condor position."""
        return IronCondorPosition(
            underlying="NIFTY",
            expiry=datetime(2023, 3, 30),
            long_put_strike=17400,
            short_put_strike=17500,
            short_call_strike=18500,
            long_call_strike=18600,
            long_put_premium=50,
            short_put_premium=100,
            short_call_premium=100,
            long_call_premium=50,
            net_credit=100,  # (100 + 100) - (50 + 50)
            entry_date=datetime(2023, 3, 15),
            quantity=2,
            long_put_current_price=50,
            short_put_current_price=100,
            short_call_current_price=100,
            long_call_current_price=50,
            entry_iv_rank=55,
            entry_spot=18000,
            wing_width=100,
        )
    
    def test_initial_cost_to_close(self, sample_iron_condor):
        """Test cost to close at entry equals net credit."""
        cost = sample_iron_condor.get_current_cost_to_close()
        # At entry: (100 + 100 - 50 - 50) * 2 = 200
        assert cost == 200
    
    def test_unrealized_pnl_at_entry(self, sample_iron_condor):
        """Test unrealized PnL at entry is zero."""
        pnl = sample_iron_condor.get_unrealized_pnl()
        # Initial credit = 100 * 2 = 200, cost to close = 200
        assert pnl == pytest.approx(0, abs=0.01)
    
    def test_unrealized_pnl_profit(self, sample_iron_condor):
        """Test unrealized PnL when in profit."""
        # Options decayed - all premiums halved
        sample_iron_condor.long_put_current_price = 25
        sample_iron_condor.short_put_current_price = 50
        sample_iron_condor.short_call_current_price = 50
        sample_iron_condor.long_call_current_price = 25
        
        pnl = sample_iron_condor.get_unrealized_pnl()
        # Initial credit = 100 * 2 = 200
        # Cost to close = (50 + 50 - 25 - 25) * 2 = 100
        # PnL = 200 - 100 = 100
        assert pnl == pytest.approx(100, abs=0.01)
    
    def test_unrealized_pnl_loss(self, sample_iron_condor):
        """Test unrealized PnL when in loss."""
        # Options increased - market moved against position
        sample_iron_condor.long_put_current_price = 100
        sample_iron_condor.short_put_current_price = 250
        sample_iron_condor.short_call_current_price = 100
        sample_iron_condor.long_call_current_price = 50
        
        pnl = sample_iron_condor.get_unrealized_pnl()
        # Initial credit = 100 * 2 = 200
        # Cost to close = (250 + 100 - 100 - 50) * 2 = 400
        # PnL = 200 - 400 = -200
        assert pnl == pytest.approx(-200, abs=0.01)
    
    def test_profit_percentage(self, sample_iron_condor):
        """Test profit percentage calculation."""
        # 50% profit scenario
        sample_iron_condor.long_put_current_price = 25
        sample_iron_condor.short_put_current_price = 50
        sample_iron_condor.short_call_current_price = 50
        sample_iron_condor.long_call_current_price = 25
        
        profit_pct = sample_iron_condor.get_profit_percentage()
        # PnL = 100, Net credit = 200
        # Profit % = 100 / 200 = 0.5 = 50%
        assert profit_pct == pytest.approx(0.5, abs=0.01)
    
    def test_max_profit(self, sample_iron_condor):
        """Test max profit calculation."""
        max_profit = sample_iron_condor.get_max_profit()
        # Max profit = net credit * quantity = 100 * 2 = 200
        assert max_profit == pytest.approx(200, abs=0.01)
    
    def test_max_loss(self, sample_iron_condor):
        """Test max loss calculation."""
        max_loss = sample_iron_condor.get_max_loss()
        # Max loss = (wing_width - net_credit) * quantity = (100 - 100) * 2 = 0
        # Note: In this sample, wing_width equals net_credit (rare case)
        assert max_loss == pytest.approx(0, abs=0.01)
    
    def test_max_loss_typical(self):
        """Test max loss with typical values."""
        ic = IronCondorPosition(
            underlying="NIFTY",
            expiry=datetime(2023, 3, 30),
            long_put_strike=17400,
            short_put_strike=17500,
            short_call_strike=18500,
            long_call_strike=18600,
            long_put_premium=50,
            short_put_premium=80,
            short_call_premium=80,
            long_call_premium=50,
            net_credit=60,  # (80 + 80) - (50 + 50)
            entry_date=datetime(2023, 3, 15),
            quantity=1,
            wing_width=100,
        )
        max_loss = ic.get_max_loss()
        # Max loss = (100 - 60) * 1 = 40
        assert max_loss == pytest.approx(40, abs=0.01)
    
    def test_breakeven_upper(self, sample_iron_condor):
        """Test upper breakeven calculation."""
        breakeven = sample_iron_condor.get_breakeven_upper()
        # Upper breakeven = short_call_strike + net_credit = 18500 + 100 = 18600
        assert breakeven == pytest.approx(18600, abs=0.01)
    
    def test_breakeven_lower(self, sample_iron_condor):
        """Test lower breakeven calculation."""
        breakeven = sample_iron_condor.get_breakeven_lower()
        # Lower breakeven = short_put_strike - net_credit = 17500 - 100 = 17400
        assert breakeven == pytest.approx(17400, abs=0.01)


class TestIronCondorStrategy:
    """Tests for IronCondorStrategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create strategy instance with default config."""
        config = {
            "iv_rank_entry_threshold": 50,
            "short_delta_range": (0.15, 0.20),
            "wing_width": {"NIFTY": 100, "BANKNIFTY": 200, "SENSEX": 200},
            "profit_target_pct": 0.50,
            "stop_loss_pct": 2.00,
            "days_before_expiry_exit": 7,
            "position_size_pct": 0.02,
            "min_days_to_expiry": 14,
            "max_days_to_expiry": 45,
            "max_positions": 3,
            "lot_sizes": {"NIFTY": 50, "BANKNIFTY": 15, "SENSEX": 10},
        }
        return IronCondorStrategy(config=config)
    
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
        assert strategy.name == "IronCondorStrategy"
        assert strategy.config["iv_rank_entry_threshold"] == 50
        assert strategy.config["profit_target_pct"] == 0.50
        assert strategy.config["stop_loss_pct"] == 2.00
    
    def test_strategy_initialize_with_data(self, strategy, sample_data):
        """Test strategy initialization with data."""
        strategy.initialize(sample_data)
        
        # Strategy should be initialized
        assert strategy._is_initialized
        assert strategy._iv_calculator is not None
    
    def test_position_size_calculation(self, strategy):
        """Test position size calculation for iron condor."""
        capital = 1_000_000
        
        signal = Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol="NIFTY_IRON_CONDOR",
            timestamp=datetime.now(),
            metadata={
                "strategy": "iron_condor",
                "underlying": "NIFTY",
                "net_credit": 50,
                "wing_width": 100,
            }
        )
        
        quantity = strategy.calculate_position_size(capital, 0, signal)
        
        # Should return at least 1
        assert quantity >= 1
        
        # Check calculation
        # max_risk = 1,000,000 * 0.02 = 20,000
        # max_loss_per_ic = (100 - 50) * 50 = 2,500
        # num_ics = 20,000 / 2,500 = 8
        expected = int(20_000 / ((100 - 50) * 50))
        assert quantity == max(1, expected)
    
    def test_open_iron_condor(self, strategy):
        """Test opening an iron condor position."""
        signal = Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol="NIFTY_IRON_CONDOR",
            timestamp=datetime(2023, 3, 15),
            metadata={
                "strategy": "iron_condor",
                "underlying": "NIFTY",
                "expiry": datetime(2023, 3, 30),
                "long_put_strike": 17400,
                "short_put_strike": 17500,
                "short_call_strike": 18500,
                "long_call_strike": 18600,
                "long_put_premium": 50,
                "short_put_premium": 100,
                "short_call_premium": 100,
                "long_call_premium": 50,
                "net_credit": 100,
                "wing_width": 100,
                "spot_price": 18000,
                "iv_rank": 55,
            }
        )
        
        ic = strategy.open_iron_condor(signal, quantity=2)
        
        assert ic.underlying == "NIFTY"
        assert ic.short_put_strike == 17500
        assert ic.short_call_strike == 18500
        assert ic.net_credit == 100
        assert ic.quantity == 2
        assert len(strategy.iron_condor_positions) == 1
    
    def test_close_iron_condor(self, strategy):
        """Test closing an iron condor position."""
        # First open a position
        entry_signal = Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol="NIFTY_IRON_CONDOR",
            timestamp=datetime(2023, 3, 15),
            metadata={
                "strategy": "iron_condor",
                "underlying": "NIFTY",
                "expiry": datetime(2023, 3, 30),
                "long_put_strike": 17400,
                "short_put_strike": 17500,
                "short_call_strike": 18500,
                "long_call_strike": 18600,
                "long_put_premium": 50,
                "short_put_premium": 100,
                "short_call_premium": 100,
                "long_call_premium": 50,
                "net_credit": 100,
                "wing_width": 100,
                "spot_price": 18000,
                "iv_rank": 55,
            }
        )
        
        ic = strategy.open_iron_condor(entry_signal, quantity=2)
        pos_id = list(strategy.iron_condor_positions.keys())[0]
        
        # Simulate profit scenario
        ic.long_put_current_price = 25
        ic.short_put_current_price = 50
        ic.short_call_current_price = 50
        ic.long_call_current_price = 25
        
        exit_signal = Signal(
            signal_type=SignalType.EXIT_SHORT,
            symbol=pos_id,
            timestamp=datetime(2023, 3, 25),
            reason="Profit target",
            metadata={"exit_type": "profit_target"}
        )
        
        trade = strategy.close_iron_condor(pos_id, exit_signal)
        
        assert trade is not None
        assert trade.direction == "SHORT"
        assert trade.exit_reason == "Profit target"
        assert len(strategy.iron_condor_positions) == 0
        assert len(strategy.trades) == 1
    
    def test_max_positions_limit(self, strategy):
        """Test that strategy respects max positions limit."""
        # Fill up positions
        for i in range(strategy.config["max_positions"]):
            signal = Signal(
                signal_type=SignalType.ENTRY_SHORT,
                symbol=f"NIFTY_IRON_CONDOR_{i}",
                timestamp=datetime(2023, 3, 15),
                metadata={
                    "strategy": "iron_condor",
                    "underlying": "NIFTY",
                    "expiry": datetime(2023, 3, 30) + timedelta(days=i*7),
                    "long_put_strike": 17400 - i*100,
                    "short_put_strike": 17500 - i*100,
                    "short_call_strike": 18500 + i*100,
                    "long_call_strike": 18600 + i*100,
                    "long_put_premium": 50,
                    "short_put_premium": 100,
                    "short_call_premium": 100,
                    "long_call_premium": 50,
                    "net_credit": 100,
                    "wing_width": 100,
                    "spot_price": 18000,
                }
            )
            strategy.open_iron_condor(signal, quantity=1)
        
        assert len(strategy.iron_condor_positions) == strategy.config["max_positions"]
    
    def test_strategy_reset(self, strategy, sample_data):
        """Test strategy reset clears all state."""
        strategy.initialize(sample_data)
        
        # Add some state
        signal = Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol="NIFTY_IRON_CONDOR",
            timestamp=datetime(2023, 3, 15),
            metadata={
                "strategy": "iron_condor",
                "underlying": "NIFTY",
                "expiry": datetime(2023, 3, 30),
                "long_put_strike": 17400,
                "short_put_strike": 17500,
                "short_call_strike": 18500,
                "long_call_strike": 18600,
                "long_put_premium": 50,
                "short_put_premium": 100,
                "short_call_premium": 100,
                "long_call_premium": 50,
                "net_credit": 100,
                "wing_width": 100,
                "spot_price": 18000,
            }
        )
        strategy.open_iron_condor(signal, quantity=1)
        
        # Reset
        strategy.reset()
        
        assert len(strategy.iron_condor_positions) == 0
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
        return IronCondorStrategy(config={
            "iv_rank_entry_threshold": 50,
            "profit_target_pct": 0.50,
            "stop_loss_pct": 2.00,
            "days_before_expiry_exit": 7,
        })
    
    def test_profit_target_exit(self, strategy):
        """Test exit at profit target."""
        # Open position
        entry_signal = Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol="NIFTY_IRON_CONDOR",
            timestamp=datetime(2023, 3, 1),
            metadata={
                "strategy": "iron_condor",
                "underlying": "NIFTY",
                "expiry": datetime(2023, 3, 30),
                "long_put_strike": 17400,
                "short_put_strike": 17500,
                "short_call_strike": 18500,
                "long_call_strike": 18600,
                "long_put_premium": 50,
                "short_put_premium": 100,
                "short_call_premium": 100,
                "long_call_premium": 50,
                "net_credit": 100,
                "wing_width": 100,
                "spot_price": 18000,
            }
        )
        ic = strategy.open_iron_condor(entry_signal, quantity=1)
        
        # Simulate 50% profit
        ic.long_put_current_price = 25
        ic.short_put_current_price = 50
        ic.short_call_current_price = 50
        ic.long_call_current_price = 25
        
        profit_pct = ic.get_profit_percentage()
        
        # Should trigger profit target
        assert profit_pct >= strategy.config["profit_target_pct"]
    
    def test_stop_loss_exit(self, strategy):
        """Test exit at stop loss."""
        # Open position
        entry_signal = Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol="NIFTY_IRON_CONDOR",
            timestamp=datetime(2023, 3, 1),
            metadata={
                "strategy": "iron_condor",
                "underlying": "NIFTY",
                "expiry": datetime(2023, 3, 30),
                "long_put_strike": 17400,
                "short_put_strike": 17500,
                "short_call_strike": 18500,
                "long_call_strike": 18600,
                "long_put_premium": 50,
                "short_put_premium": 100,
                "short_call_premium": 100,
                "long_call_premium": 50,
                "net_credit": 100,
                "wing_width": 100,
                "spot_price": 18000,
            }
        )
        ic = strategy.open_iron_condor(entry_signal, quantity=1)
        
        # Simulate 200% loss
        ic.long_put_current_price = 150
        ic.short_put_current_price = 400
        ic.short_call_current_price = 100
        ic.long_call_current_price = 50
        
        profit_pct = ic.get_profit_percentage()
        
        # Should trigger stop loss (loss >= 200%)
        assert profit_pct <= -strategy.config["stop_loss_pct"]
    
    def test_should_exit_time(self, strategy):
        """Test should_exit for time-based exit."""
        ic = IronCondorPosition(
            underlying="NIFTY",
            expiry=datetime(2023, 3, 10),  # 5 days from now
            long_put_strike=17400,
            short_put_strike=17500,
            short_call_strike=18500,
            long_call_strike=18600,
            long_put_premium=50,
            short_put_premium=100,
            short_call_premium=100,
            long_call_premium=50,
            net_credit=100,
            entry_date=datetime(2023, 2, 15),
            quantity=1,
            wing_width=100,
        )
        
        should_exit, reason = strategy.should_exit(ic, 18000, datetime(2023, 3, 5))
        
        assert should_exit
        assert "days to expiry" in reason.lower()


class TestIVRankIntegration:
    """Tests for IV Rank integration with strategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create strategy with IV calculator."""
        return IronCondorStrategy(config={
            "iv_rank_entry_threshold": 50,
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
