"""
Tests for Ratio Spread Strategy.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.ratio_spread import (
    RatioSpreadStrategy,
    RatioSpreadPosition,
)
from src.strategies.base_strategy import Signal, SignalType
from src.data.historical_data import HistoricalDataFetcher


class TestRatioSpreadPosition:
    """Tests for RatioSpreadPosition dataclass."""
    
    @pytest.fixture
    def sample_put_ratio(self):
        """Create sample put ratio spread position (bullish)."""
        return RatioSpreadPosition(
            underlying="NIFTY",
            expiry=datetime(2023, 3, 30),
            spread_type="PUT_RATIO",
            long_strike=18000,  # ATM Put
            short_strike=17500,  # OTM Put
            long_quantity=1,
            short_quantity=2,
            long_premium=150,    # Paid for 1 ATM put
            short_premium=60,    # Received per OTM put
            net_credit_debit=-30,  # 2*60 - 150 = -30 (debit)
            entry_date=datetime(2023, 3, 15),
            quantity=1,
            long_current_price=150,
            short_current_price=60,
            entry_iv_rank=65,
            entry_spot=18000,
        )
    
    @pytest.fixture
    def sample_call_ratio(self):
        """Create sample call ratio spread position (bearish)."""
        return RatioSpreadPosition(
            underlying="NIFTY",
            expiry=datetime(2023, 3, 30),
            spread_type="CALL_RATIO",
            long_strike=18000,  # ATM Call
            short_strike=18500,  # OTM Call
            long_quantity=1,
            short_quantity=2,
            long_premium=150,    # Paid for 1 ATM call
            short_premium=60,    # Received per OTM call
            net_credit_debit=-30,  # 2*60 - 150 = -30 (debit)
            entry_date=datetime(2023, 3, 15),
            quantity=1,
            long_current_price=150,
            short_current_price=60,
            entry_iv_rank=65,
            entry_spot=18000,
        )
    
    def test_initial_value_put_ratio(self, sample_put_ratio):
        """Test value at entry for put ratio."""
        value = sample_put_ratio.get_current_value()
        # At entry: (150 * 1 - 60 * 2) * 1 = 30
        assert value == 30
    
    def test_unrealized_pnl_at_entry(self, sample_put_ratio):
        """Test unrealized PnL at entry is zero."""
        pnl = sample_put_ratio.get_unrealized_pnl()
        # Initial cost = -(-30) * 1 = 30 (positive because debit paid)
        # Current value = 30
        # PnL = 30 - 30 = 0
        assert pnl == pytest.approx(0, abs=0.01)
    
    def test_unrealized_pnl_profit(self, sample_put_ratio):
        """Test unrealized PnL when in profit."""
        # Market moved toward short strike - ideal scenario
        sample_put_ratio.long_current_price = 400  # ATM put gained value
        sample_put_ratio.short_current_price = 80  # OTM puts also gained but less
        
        pnl = sample_put_ratio.get_unrealized_pnl()
        # Current value = (400 * 1 - 80 * 2) * 1 = 240
        # Initial cost = 30
        # PnL = 240 - 30 = 210
        assert pnl == pytest.approx(210, abs=0.01)
    
    def test_unrealized_pnl_loss(self, sample_put_ratio):
        """Test unrealized PnL when in loss (market crashed below short strike)."""
        # Market crashed - both puts ITM
        sample_put_ratio.long_current_price = 600  # ATM put deep ITM
        sample_put_ratio.short_current_price = 350  # OTM puts also ITM
        
        pnl = sample_put_ratio.get_unrealized_pnl()
        # Current value = (600 * 1 - 350 * 2) * 1 = -100
        # Initial cost = 30
        # PnL = -100 - 30 = -130
        assert pnl == pytest.approx(-130, abs=0.01)
    
    def test_max_profit_at_short_strike_put_ratio(self, sample_put_ratio):
        """Test max profit calculation for put ratio."""
        max_profit = sample_put_ratio.get_max_profit_at_short_strike()
        # For PUT_RATIO: (long_strike - short_strike) + net_credit_debit
        # = (18000 - 17500) + (-30) = 470
        assert max_profit == pytest.approx(470, abs=0.01)
    
    def test_max_profit_at_short_strike_call_ratio(self, sample_call_ratio):
        """Test max profit calculation for call ratio."""
        max_profit = sample_call_ratio.get_max_profit_at_short_strike()
        # For CALL_RATIO: (short_strike - long_strike) + net_credit_debit
        # = (18500 - 18000) + (-30) = 470
        assert max_profit == pytest.approx(470, abs=0.01)
    
    def test_breakeven_put_ratio(self, sample_put_ratio):
        """Test breakeven calculation for put ratio."""
        breakeven = sample_put_ratio.get_breakeven_point()
        # For PUT_RATIO: short_strike - max_profit
        # max_profit = 470
        # breakeven = 17500 - 470 = 17030
        assert breakeven == pytest.approx(17030, abs=1)
    
    def test_breakeven_call_ratio(self, sample_call_ratio):
        """Test breakeven calculation for call ratio."""
        breakeven = sample_call_ratio.get_breakeven_point()
        # For CALL_RATIO: short_strike + max_profit
        # max_profit = 470
        # breakeven = 18500 + 470 = 18970
        assert breakeven == pytest.approx(18970, abs=1)


class TestRatioSpreadStrategy:
    """Tests for RatioSpreadStrategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create strategy instance with default config."""
        config = {
            "iv_rank_entry_threshold": 60,
            "ratio": (1, 2),
            "long_delta": 0.50,
            "short_delta_range": (0.20, 0.25),
            "profit_target_pct": 0.75,
            "stop_loss_breach_pct": 0.02,
            "days_before_expiry_exit": 7,
            "min_days_to_expiry": 21,
            "max_days_to_expiry": 45,
            "position_size_pct": 0.01,
            "max_positions": 2,
            "lot_sizes": {"NIFTY": 50, "BANKNIFTY": 15, "SENSEX": 10},
            "spread_type": "PUT_RATIO",
        }
        return RatioSpreadStrategy(config=config)
    
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
        assert strategy.name == "RatioSpreadStrategy"
        assert strategy.config["iv_rank_entry_threshold"] == 60
        assert strategy.config["ratio"] == (1, 2)
        assert strategy.config["profit_target_pct"] == 0.75
        assert strategy.config["spread_type"] == "PUT_RATIO"
    
    def test_strategy_initialize_with_data(self, strategy, sample_data):
        """Test strategy initialization with data."""
        strategy.initialize(sample_data)
        
        # Strategy should be initialized
        assert strategy._is_initialized
        assert strategy._iv_calculator is not None
    
    def test_position_size_calculation(self, strategy):
        """Test position size calculation for ratio spread."""
        capital = 1_000_000
        
        signal = Signal(
            signal_type=SignalType.ENTRY_LONG,
            symbol="NIFTY_RATIO_SPREAD",
            timestamp=datetime.now(),
            metadata={
                "strategy": "ratio_spread",
                "underlying": "NIFTY",
                "long_strike": 18000,
                "short_strike": 17500,
                "net_credit_debit": -30,
            }
        )
        
        quantity = strategy.calculate_position_size(capital, 0, signal)
        
        # Should return at least 1, max 2
        assert quantity >= 1
        assert quantity <= 2
    
    def test_open_ratio_spread(self, strategy):
        """Test opening a ratio spread position."""
        signal = Signal(
            signal_type=SignalType.ENTRY_LONG,
            symbol="NIFTY_RATIO_SPREAD",
            timestamp=datetime(2023, 3, 15),
            metadata={
                "strategy": "ratio_spread",
                "underlying": "NIFTY",
                "expiry": datetime(2023, 3, 30),
                "spread_type": "PUT_RATIO",
                "option_type": "PE",
                "long_strike": 18000,
                "short_strike": 17500,
                "long_quantity": 1,
                "short_quantity": 2,
                "long_premium": 150,
                "short_premium": 60,
                "net_credit_debit": -30,
                "spot_price": 18000,
                "iv_rank": 65,
            }
        )
        
        ratio = strategy.open_ratio_spread(signal, quantity=1)
        
        assert ratio.underlying == "NIFTY"
        assert ratio.spread_type == "PUT_RATIO"
        assert ratio.long_strike == 18000
        assert ratio.short_strike == 17500
        assert ratio.long_quantity == 1
        assert ratio.short_quantity == 2
        assert len(strategy.ratio_positions) == 1
    
    def test_close_ratio_spread(self, strategy):
        """Test closing a ratio spread position."""
        # First open a position
        entry_signal = Signal(
            signal_type=SignalType.ENTRY_LONG,
            symbol="NIFTY_RATIO_SPREAD",
            timestamp=datetime(2023, 3, 15),
            metadata={
                "strategy": "ratio_spread",
                "underlying": "NIFTY",
                "expiry": datetime(2023, 3, 30),
                "spread_type": "PUT_RATIO",
                "option_type": "PE",
                "long_strike": 18000,
                "short_strike": 17500,
                "long_quantity": 1,
                "short_quantity": 2,
                "long_premium": 150,
                "short_premium": 60,
                "net_credit_debit": -30,
                "spot_price": 18000,
                "iv_rank": 65,
            }
        )
        
        ratio = strategy.open_ratio_spread(entry_signal, quantity=1)
        pos_id = list(strategy.ratio_positions.keys())[0]
        
        # Simulate profit scenario (market at short strike)
        ratio.long_current_price = 500
        ratio.short_current_price = 50
        
        exit_signal = Signal(
            signal_type=SignalType.EXIT_LONG,
            symbol=pos_id,
            timestamp=datetime(2023, 3, 28),
            reason="Profit target",
            metadata={"exit_type": "profit_target"}
        )
        
        trade = strategy.close_ratio_spread(pos_id, exit_signal)
        
        assert trade is not None
        assert trade.direction == "LONG"
        assert trade.exit_reason == "Profit target"
        assert len(strategy.ratio_positions) == 0
        assert len(strategy.trades) == 1
    
    def test_max_positions_limit(self, strategy):
        """Test that strategy respects max positions limit."""
        # Fill up positions
        for i in range(strategy.config["max_positions"]):
            signal = Signal(
                signal_type=SignalType.ENTRY_LONG,
                symbol=f"NIFTY_RATIO_SPREAD_{i}",
                timestamp=datetime(2023, 3, 15),
                metadata={
                    "strategy": "ratio_spread",
                    "underlying": "NIFTY",
                    "expiry": datetime(2023, 3, 30) + timedelta(days=i*7),
                    "spread_type": "PUT_RATIO",
                    "option_type": "PE",
                    "long_strike": 18000 + i*100,
                    "short_strike": 17500 + i*100,
                    "long_quantity": 1,
                    "short_quantity": 2,
                    "long_premium": 150,
                    "short_premium": 60,
                    "net_credit_debit": -30,
                    "spot_price": 18000,
                }
            )
            strategy.open_ratio_spread(signal, quantity=1)
        
        assert len(strategy.ratio_positions) == strategy.config["max_positions"]
    
    def test_strategy_reset(self, strategy, sample_data):
        """Test strategy reset clears all state."""
        strategy.initialize(sample_data)
        
        # Add some state
        signal = Signal(
            signal_type=SignalType.ENTRY_LONG,
            symbol="NIFTY_RATIO_SPREAD",
            timestamp=datetime(2023, 3, 15),
            metadata={
                "strategy": "ratio_spread",
                "underlying": "NIFTY",
                "expiry": datetime(2023, 3, 30),
                "spread_type": "PUT_RATIO",
                "option_type": "PE",
                "long_strike": 18000,
                "short_strike": 17500,
                "long_quantity": 1,
                "short_quantity": 2,
                "long_premium": 150,
                "short_premium": 60,
                "net_credit_debit": -30,
                "spot_price": 18000,
            }
        )
        strategy.open_ratio_spread(signal, quantity=1)
        
        # Reset
        strategy.reset()
        
        assert len(strategy.ratio_positions) == 0
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
        return RatioSpreadStrategy(config={
            "iv_rank_entry_threshold": 60,
            "ratio": (1, 2),
            "profit_target_pct": 0.75,
            "stop_loss_breach_pct": 0.02,
            "days_before_expiry_exit": 7,
            "spread_type": "PUT_RATIO",
        })
    
    def test_profit_target_exit(self, strategy):
        """Test exit at profit target."""
        # Open position
        entry_signal = Signal(
            signal_type=SignalType.ENTRY_LONG,
            symbol="NIFTY_RATIO_SPREAD",
            timestamp=datetime(2023, 3, 1),
            metadata={
                "strategy": "ratio_spread",
                "underlying": "NIFTY",
                "expiry": datetime(2023, 3, 30),
                "spread_type": "PUT_RATIO",
                "option_type": "PE",
                "long_strike": 18000,
                "short_strike": 17500,
                "long_quantity": 1,
                "short_quantity": 2,
                "long_premium": 150,
                "short_premium": 60,
                "net_credit_debit": -30,
                "spot_price": 18000,
            }
        )
        ratio = strategy.open_ratio_spread(entry_signal, quantity=1)
        
        # Max profit = (18000 - 17500) + (-30) = 470
        # 75% of max profit = 352.5
        # Need unrealized PnL = 352.5
        # Initial cost = 30
        # Need current value = 30 + 352.5 = 382.5
        # If short_current = 20, then long_current = 382.5 + 40 = 422.5
        ratio.long_current_price = 422.5
        ratio.short_current_price = 20
        
        profit_pct = ratio.get_profit_percentage()
        
        # Should trigger profit target
        assert profit_pct >= strategy.config["profit_target_pct"]
    
    def test_stop_loss_breach_put_ratio(self, strategy):
        """Test stop loss when short strike is breached for put ratio."""
        ratio = RatioSpreadPosition(
            underlying="NIFTY",
            expiry=datetime(2023, 3, 30),
            spread_type="PUT_RATIO",
            long_strike=18000,
            short_strike=17500,
            long_quantity=1,
            short_quantity=2,
            long_premium=150,
            short_premium=60,
            net_credit_debit=-30,
            entry_date=datetime(2023, 3, 15),
            quantity=1,
            entry_spot=18000,
        )
        
        # Current spot below breach threshold
        # Breach threshold = 17500 * (1 - 0.02) = 17150
        current_spot = 17100
        
        should_exit, reason = strategy.should_exit(ratio, current_spot, datetime(2023, 3, 20))
        
        assert should_exit
        assert "breached" in reason.lower()
    
    def test_stop_loss_breach_call_ratio(self):
        """Test stop loss when short strike is breached for call ratio."""
        strategy = RatioSpreadStrategy(config={
            "iv_rank_entry_threshold": 60,
            "profit_target_pct": 0.75,
            "stop_loss_breach_pct": 0.02,
            "days_before_expiry_exit": 7,
            "spread_type": "CALL_RATIO",
        })
        
        ratio = RatioSpreadPosition(
            underlying="NIFTY",
            expiry=datetime(2023, 3, 30),
            spread_type="CALL_RATIO",
            long_strike=18000,
            short_strike=18500,
            long_quantity=1,
            short_quantity=2,
            long_premium=150,
            short_premium=60,
            net_credit_debit=-30,
            entry_date=datetime(2023, 3, 15),
            quantity=1,
            entry_spot=18000,
        )
        
        # Current spot above breach threshold
        # Breach threshold = 18500 * (1 + 0.02) = 18870
        current_spot = 18900
        
        should_exit, reason = strategy.should_exit(ratio, current_spot, datetime(2023, 3, 20))
        
        assert should_exit
        assert "breached" in reason.lower()
    
    def test_should_exit_time(self, strategy):
        """Test should_exit for time-based exit."""
        ratio = RatioSpreadPosition(
            underlying="NIFTY",
            expiry=datetime(2023, 3, 10),  # 5 days from now
            spread_type="PUT_RATIO",
            long_strike=18000,
            short_strike=17500,
            long_quantity=1,
            short_quantity=2,
            long_premium=150,
            short_premium=60,
            net_credit_debit=-30,
            entry_date=datetime(2023, 2, 15),
            quantity=1,
        )
        
        should_exit, reason = strategy.should_exit(ratio, 18000, datetime(2023, 3, 5))
        
        assert should_exit
        assert "days to expiry" in reason.lower()


class TestIVRankIntegration:
    """Tests for IV Rank integration with strategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create strategy with IV calculator."""
        return RatioSpreadStrategy(config={
            "iv_rank_entry_threshold": 60,
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


class TestRatioSpreadTypes:
    """Tests for different ratio spread types."""
    
    def test_put_ratio_is_bullish(self):
        """Test that put ratio spread is bullish."""
        strategy = RatioSpreadStrategy(config={
            "spread_type": "PUT_RATIO",
        })
        
        # Put ratio benefits when market stays above short put strike
        assert strategy.config["spread_type"] == "PUT_RATIO"
    
    def test_call_ratio_is_bearish(self):
        """Test that call ratio spread is bearish."""
        strategy = RatioSpreadStrategy(config={
            "spread_type": "CALL_RATIO",
        })
        
        # Call ratio benefits when market stays below short call strike
        assert strategy.config["spread_type"] == "CALL_RATIO"
    
    def test_different_ratios(self):
        """Test strategy with different ratios."""
        # 1:3 ratio (more aggressive)
        strategy = RatioSpreadStrategy(config={
            "ratio": (1, 3),
        })
        
        assert strategy.config["ratio"] == (1, 3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
