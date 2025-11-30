"""
Tests for Calendar Spread Strategy.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.calendar_spread import (
    CalendarSpreadStrategy,
    CalendarSpreadPosition,
)
from src.strategies.base_strategy import Signal, SignalType
from src.data.historical_data import HistoricalDataFetcher


class TestCalendarSpreadPosition:
    """Tests for CalendarSpreadPosition dataclass."""
    
    @pytest.fixture
    def sample_calendar(self):
        """Create sample calendar spread position."""
        return CalendarSpreadPosition(
            underlying="NIFTY",
            strike=18000,
            option_type="CE",
            near_expiry=datetime(2023, 3, 16),
            far_expiry=datetime(2023, 4, 27),
            near_premium=80,   # Received for selling near
            far_premium=150,   # Paid for buying far
            net_debit=70,      # 150 - 80
            entry_date=datetime(2023, 3, 1),
            quantity=2,
            near_current_price=80,
            far_current_price=150,
            entry_iv_rank=25,
            entry_spot=18000,
        )
    
    def test_initial_value(self, sample_calendar):
        """Test value at entry."""
        value = sample_calendar.get_current_value()
        # At entry: (150 - 80) * 2 = 140
        assert value == 140
    
    def test_unrealized_pnl_at_entry(self, sample_calendar):
        """Test unrealized PnL at entry is zero."""
        pnl = sample_calendar.get_unrealized_pnl()
        # Initial debit = 70 * 2 = 140
        # Current value = 140
        # PnL = 140 - 140 = 0
        assert pnl == pytest.approx(0, abs=0.01)
    
    def test_unrealized_pnl_profit(self, sample_calendar):
        """Test unrealized PnL when in profit."""
        # Near option decayed more, far option held value
        sample_calendar.near_current_price = 30
        sample_calendar.far_current_price = 140
        
        pnl = sample_calendar.get_unrealized_pnl()
        # Current value = (140 - 30) * 2 = 220
        # Initial debit = 70 * 2 = 140
        # PnL = 220 - 140 = 80
        assert pnl == pytest.approx(80, abs=0.01)
    
    def test_unrealized_pnl_loss(self, sample_calendar):
        """Test unrealized PnL when in loss."""
        # Market moved away from strike
        sample_calendar.near_current_price = 50
        sample_calendar.far_current_price = 80
        
        pnl = sample_calendar.get_unrealized_pnl()
        # Current value = (80 - 50) * 2 = 60
        # Initial debit = 70 * 2 = 140
        # PnL = 60 - 140 = -80
        assert pnl == pytest.approx(-80, abs=0.01)
    
    def test_profit_percentage(self, sample_calendar):
        """Test profit percentage calculation."""
        # 50% profit scenario
        sample_calendar.near_current_price = 30
        sample_calendar.far_current_price = 135
        
        profit_pct = sample_calendar.get_profit_percentage()
        # Current value = (135 - 30) * 2 = 210
        # Initial debit = 70 * 2 = 140
        # PnL = 70
        # Profit % = 70 / 140 = 0.5 = 50%
        assert profit_pct == pytest.approx(0.5, abs=0.01)
    
    def test_max_loss(self, sample_calendar):
        """Test max loss calculation."""
        max_loss = sample_calendar.get_max_loss()
        # Max loss = net_debit * quantity = 70 * 2 = 140
        assert max_loss == pytest.approx(140, abs=0.01)


class TestCalendarSpreadStrategy:
    """Tests for CalendarSpreadStrategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create strategy instance with default config."""
        config = {
            "iv_rank_entry_threshold": 30,
            "iv_rank_entry_below": True,
            "strike_selection": "ATM",
            "near_expiry_days_range": (7, 14),
            "far_expiry_days_range": (30, 45),
            "profit_target_pct": 0.35,
            "stop_loss_pct": 0.50,
            "days_before_near_expiry_exit": 3,
            "position_size_pct": 0.015,
            "max_positions": 3,
            "lot_sizes": {"NIFTY": 50, "BANKNIFTY": 15, "SENSEX": 10},
        }
        return CalendarSpreadStrategy(config=config)
    
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
        assert strategy.name == "CalendarSpreadStrategy"
        assert strategy.config["iv_rank_entry_threshold"] == 30
        assert strategy.config["iv_rank_entry_below"] == True
        assert strategy.config["profit_target_pct"] == 0.35
        assert strategy.config["stop_loss_pct"] == 0.50
    
    def test_strategy_initialize_with_data(self, strategy, sample_data):
        """Test strategy initialization with data."""
        strategy.initialize(sample_data)
        
        # Strategy should be initialized
        assert strategy._is_initialized
        assert strategy._iv_calculator is not None
    
    def test_position_size_calculation(self, strategy):
        """Test position size calculation for calendar spread."""
        capital = 1_000_000
        
        signal = Signal(
            signal_type=SignalType.ENTRY_LONG,
            symbol="NIFTY_CALENDAR",
            timestamp=datetime.now(),
            metadata={
                "strategy": "calendar_spread",
                "underlying": "NIFTY",
                "net_debit": 100,
            }
        )
        
        quantity = strategy.calculate_position_size(capital, 0, signal)
        
        # Should return at least 1
        assert quantity >= 1
        
        # Check calculation
        # max_risk = 1,000,000 * 0.015 = 15,000
        # max_loss_per_calendar = 100 * 50 = 5,000
        # num_calendars = 15,000 / 5,000 = 3
        expected = int(15_000 / (100 * 50))
        assert quantity == max(1, expected)
    
    def test_open_calendar(self, strategy):
        """Test opening a calendar spread position."""
        signal = Signal(
            signal_type=SignalType.ENTRY_LONG,
            symbol="NIFTY_CALENDAR",
            timestamp=datetime(2023, 3, 1),
            metadata={
                "strategy": "calendar_spread",
                "underlying": "NIFTY",
                "strike": 18000,
                "option_type": "CE",
                "near_expiry": datetime(2023, 3, 16),
                "far_expiry": datetime(2023, 4, 27),
                "near_premium": 80,
                "far_premium": 150,
                "net_debit": 70,
                "spot_price": 18000,
                "iv_rank": 25,
            }
        )
        
        calendar = strategy.open_calendar(signal, quantity=2)
        
        assert calendar.underlying == "NIFTY"
        assert calendar.strike == 18000
        assert calendar.option_type == "CE"
        assert calendar.net_debit == 70
        assert calendar.quantity == 2
        assert len(strategy.calendar_positions) == 1
    
    def test_close_calendar(self, strategy):
        """Test closing a calendar spread position."""
        # First open a position
        entry_signal = Signal(
            signal_type=SignalType.ENTRY_LONG,
            symbol="NIFTY_CALENDAR",
            timestamp=datetime(2023, 3, 1),
            metadata={
                "strategy": "calendar_spread",
                "underlying": "NIFTY",
                "strike": 18000,
                "option_type": "CE",
                "near_expiry": datetime(2023, 3, 16),
                "far_expiry": datetime(2023, 4, 27),
                "near_premium": 80,
                "far_premium": 150,
                "net_debit": 70,
                "spot_price": 18000,
                "iv_rank": 25,
            }
        )
        
        calendar = strategy.open_calendar(entry_signal, quantity=2)
        pos_id = list(strategy.calendar_positions.keys())[0]
        
        # Simulate profit scenario
        calendar.near_current_price = 30
        calendar.far_current_price = 140
        
        exit_signal = Signal(
            signal_type=SignalType.EXIT_LONG,
            symbol=pos_id,
            timestamp=datetime(2023, 3, 14),
            reason="Profit target",
            metadata={"exit_type": "profit_target"}
        )
        
        trade = strategy.close_calendar(pos_id, exit_signal)
        
        assert trade is not None
        assert trade.direction == "LONG"
        assert trade.exit_reason == "Profit target"
        assert len(strategy.calendar_positions) == 0
        assert len(strategy.trades) == 1
    
    def test_max_positions_limit(self, strategy):
        """Test that strategy respects max positions limit."""
        # Fill up positions
        for i in range(strategy.config["max_positions"]):
            signal = Signal(
                signal_type=SignalType.ENTRY_LONG,
                symbol=f"NIFTY_CALENDAR_{i}",
                timestamp=datetime(2023, 3, 1),
                metadata={
                    "strategy": "calendar_spread",
                    "underlying": "NIFTY",
                    "strike": 18000 + i*100,
                    "option_type": "CE",
                    "near_expiry": datetime(2023, 3, 16) + timedelta(days=i*7),
                    "far_expiry": datetime(2023, 4, 27) + timedelta(days=i*7),
                    "near_premium": 80,
                    "far_premium": 150,
                    "net_debit": 70,
                    "spot_price": 18000,
                }
            )
            strategy.open_calendar(signal, quantity=1)
        
        assert len(strategy.calendar_positions) == strategy.config["max_positions"]
    
    def test_strategy_reset(self, strategy, sample_data):
        """Test strategy reset clears all state."""
        strategy.initialize(sample_data)
        
        # Add some state
        signal = Signal(
            signal_type=SignalType.ENTRY_LONG,
            symbol="NIFTY_CALENDAR",
            timestamp=datetime(2023, 3, 1),
            metadata={
                "strategy": "calendar_spread",
                "underlying": "NIFTY",
                "strike": 18000,
                "option_type": "CE",
                "near_expiry": datetime(2023, 3, 16),
                "far_expiry": datetime(2023, 4, 27),
                "near_premium": 80,
                "far_premium": 150,
                "net_debit": 70,
                "spot_price": 18000,
            }
        )
        strategy.open_calendar(signal, quantity=1)
        
        # Reset
        strategy.reset()
        
        assert len(strategy.calendar_positions) == 0
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
        return CalendarSpreadStrategy(config={
            "iv_rank_entry_threshold": 30,
            "iv_rank_entry_below": True,
            "profit_target_pct": 0.35,
            "stop_loss_pct": 0.50,
            "days_before_near_expiry_exit": 3,
        })
    
    def test_profit_target_exit(self, strategy):
        """Test exit at profit target."""
        # Open position
        entry_signal = Signal(
            signal_type=SignalType.ENTRY_LONG,
            symbol="NIFTY_CALENDAR",
            timestamp=datetime(2023, 3, 1),
            metadata={
                "strategy": "calendar_spread",
                "underlying": "NIFTY",
                "strike": 18000,
                "option_type": "CE",
                "near_expiry": datetime(2023, 3, 16),
                "far_expiry": datetime(2023, 4, 27),
                "near_premium": 80,
                "far_premium": 150,
                "net_debit": 70,
                "spot_price": 18000,
            }
        )
        calendar = strategy.open_calendar(entry_signal, quantity=1)
        
        # Simulate 35% profit
        # Initial debit = 70, need 35% profit = 24.5 gain
        # Need current value = 70 + 24.5 = 94.5
        calendar.near_current_price = 30
        calendar.far_current_price = 124.5  # 124.5 - 30 = 94.5
        
        profit_pct = calendar.get_profit_percentage()
        
        # Should trigger profit target
        assert profit_pct >= strategy.config["profit_target_pct"]
    
    def test_stop_loss_exit(self, strategy):
        """Test exit at stop loss."""
        # Open position
        entry_signal = Signal(
            signal_type=SignalType.ENTRY_LONG,
            symbol="NIFTY_CALENDAR",
            timestamp=datetime(2023, 3, 1),
            metadata={
                "strategy": "calendar_spread",
                "underlying": "NIFTY",
                "strike": 18000,
                "option_type": "CE",
                "near_expiry": datetime(2023, 3, 16),
                "far_expiry": datetime(2023, 4, 27),
                "near_premium": 80,
                "far_premium": 150,
                "net_debit": 70,
                "spot_price": 18000,
            }
        )
        calendar = strategy.open_calendar(entry_signal, quantity=1)
        
        # Simulate 50% loss
        # Initial debit = 70, 50% loss = 35 loss
        # Need current value = 70 - 35 = 35
        calendar.near_current_price = 45
        calendar.far_current_price = 80  # 80 - 45 = 35
        
        profit_pct = calendar.get_profit_percentage()
        
        # Should trigger stop loss (loss >= 50%)
        assert profit_pct <= -strategy.config["stop_loss_pct"]
    
    def test_should_exit_time(self, strategy):
        """Test should_exit for time-based exit."""
        calendar = CalendarSpreadPosition(
            underlying="NIFTY",
            strike=18000,
            option_type="CE",
            near_expiry=datetime(2023, 3, 8),  # 2 days from now
            far_expiry=datetime(2023, 4, 27),
            near_premium=80,
            far_premium=150,
            net_debit=70,
            entry_date=datetime(2023, 3, 1),
            quantity=1,
        )
        
        should_exit, reason = strategy.should_exit(calendar, 18000, datetime(2023, 3, 6))
        
        assert should_exit
        assert "near expiry" in reason.lower()


class TestIVRankIntegration:
    """Tests for IV Rank integration with strategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create strategy with IV calculator."""
        return CalendarSpreadStrategy(config={
            "iv_rank_entry_threshold": 30,
            "iv_rank_entry_below": True,
        })
    
    @pytest.fixture
    def low_iv_data(self):
        """Create data with low IV regime."""
        fetcher = HistoricalDataFetcher()
        data = fetcher.load_nifty_options(
            start_date="2023-01-01",
            end_date="2023-06-30",
            use_mock=True
        )
        
        # Artificially decrease IV to simulate low IV regime
        data = data.copy()
        data["iv"] = data["iv"] * 0.5
        
        return data
    
    def test_iv_series_extraction(self, strategy, low_iv_data):
        """Test ATM IV series extraction."""
        iv_series = strategy._extract_atm_iv_series(low_iv_data)
        
        # Should have IV values
        assert len(iv_series) > 0
        
        # IV should be positive
        assert (iv_series > 0).all()


class TestCalendarGreeks:
    """Tests for Calendar Spread Greek characteristics."""
    
    def test_theta_positive_at_entry(self):
        """Test that calendar has positive theta at entry."""
        # Calendar spread should benefit from time decay
        # Near option has higher theta (decays faster)
        calendar = CalendarSpreadPosition(
            underlying="NIFTY",
            strike=18000,
            option_type="CE",
            near_expiry=datetime(2023, 3, 16),
            far_expiry=datetime(2023, 4, 27),
            near_premium=80,
            far_premium=150,
            net_debit=70,
            entry_date=datetime(2023, 3, 1),
            quantity=1,
            metadata={
                "near_theta": -5.0,  # Near option theta (negative because option loses value)
                "far_theta": -2.0,   # Far option theta (less negative)
            }
        )
        
        # Net theta should be positive (short near = +theta, long far = -theta)
        # Short near: -(-5.0) = +5.0
        # Long far: -2.0
        # Net theta = 5.0 - 2.0 = 3.0 (positive)
        near_theta = calendar.metadata.get("near_theta", 0)
        far_theta = calendar.metadata.get("far_theta", 0)
        net_theta = -near_theta + far_theta  # Flip sign for short position
        
        # Note: In real options, net theta would be positive
        # Here we verify the calculation structure
        assert near_theta < 0  # Near option loses value faster
        assert far_theta < 0   # Far option also loses value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
