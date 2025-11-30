"""
Calendar Spread Strategy Module

Implements a Calendar Spread (Time Spread) options strategy.

Strategy Overview:
A Calendar Spread profits from time decay differential between near-term
and far-term options. It benefits when the underlying stays near the
strike price and/or implied volatility increases.

Structure:
- Sell near-term ATM/OTM option
- Buy same-strike far-term option

Entry Conditions:
- IV Rank < 30 (low IV environment - expecting IV expansion)
- OR significant term structure difference (front month IV > back month IV)
- ATM or slightly OTM strikes preferred
- Near expiry: 7-14 days
- Far expiry: 30-45 days

Exit Conditions:
- Profit target: 25-50% of debit paid
- Stop loss: 50% of debit paid
- Time exit: Close when near-term option has 2-3 days to expiry
- Roll: Can roll near-term option to next expiry if position is profitable

Greeks Focus:
- Positive Theta (from short near-term)
- Positive Vega (benefits from IV increase)
- Near Delta-neutral at entry

Mathematical Formulas:
- Max Profit = Achieved when underlying at strike at near expiry
- Max Loss = Net Debit Paid
- Theta Benefit = Near Theta - Far Theta (positive)

Note: Calendar spreads work best in low volatility environments
with expectation of volatility expansion or range-bound markets.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
import logging

from .base_strategy import (
    BaseStrategy, Signal, SignalType, Position, Trade
)

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class CalendarSpreadPosition:
    """
    Data class representing a Calendar Spread position.
    
    A Calendar Spread consists of:
    - Short near-term option (sells time decay)
    - Long far-term option at same strike (holds longer-dated option)
    
    Attributes:
        underlying: Name of underlying
        strike: Strike price (same for both options)
        option_type: "CE" for call calendar, "PE" for put calendar
        near_expiry: Near-term expiry date
        far_expiry: Far-term expiry date
        near_premium: Premium received for short near-term option
        far_premium: Premium paid for long far-term option
        net_debit: Net debit paid (far_premium - near_premium)
        entry_date: Date position was opened
        quantity: Number of calendars (lot multiplier)
        near_current_price: Current price of near-term option
        far_current_price: Current price of far-term option
        entry_iv_rank: IV Rank at entry
        entry_spot: Spot price at entry
    """
    underlying: str
    strike: float
    option_type: str  # "CE" or "PE"
    near_expiry: datetime
    far_expiry: datetime
    near_premium: float
    far_premium: float
    net_debit: float
    entry_date: datetime
    quantity: int = 1
    near_current_price: float = 0.0
    far_current_price: float = 0.0
    entry_iv_rank: float = 0.0
    entry_spot: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_current_value(self) -> float:
        """Calculate current value of the calendar spread."""
        # Value = Long option - Short option
        return (self.far_current_price - self.near_current_price) * self.quantity
    
    def get_unrealized_pnl(self) -> float:
        """Calculate unrealized P&L."""
        return self.get_current_value() - (self.net_debit * self.quantity)
    
    def get_profit_percentage(self) -> float:
        """Calculate profit as percentage of debit paid."""
        if self.net_debit > 0:
            return self.get_unrealized_pnl() / (self.net_debit * self.quantity)
        return 0.0
    
    def get_max_loss(self) -> float:
        """Calculate maximum loss (net debit paid)."""
        return self.net_debit * self.quantity


class CalendarSpreadStrategy(BaseStrategy):
    """
    Calendar Spread Strategy for low volatility environments.
    
    This strategy profits from the differential time decay between
    near-term and far-term options, and benefits from IV expansion.
    
    Entry Criteria:
    - IV Rank < 30 (low IV - expecting expansion)
    - ATM or slightly OTM strikes
    - Near expiry: 7-14 days
    - Far expiry: 30-45 days
    
    Exit Criteria:
    - Profit target: 35% of debit paid
    - Stop loss: 50% of debit lost
    - Time exit: 2-3 days before near expiry
    
    Position Management:
    - Maximum concurrent positions
    - Position sizing based on debit paid
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Calendar Spread Strategy.
        
        Args:
            config: Strategy configuration dictionary with:
                - iv_rank_entry_threshold: Maximum IV Rank for entry (default: 30)
                - iv_rank_entry_below: Enter when IV Rank < threshold (default: True)
                - strike_selection: "ATM" or "OTM" (default: "ATM")
                - near_expiry_days_range: Range for near expiry (default: (7, 14))
                - far_expiry_days_range: Range for far expiry (default: (30, 45))
                - profit_target_pct: Profit target as % of debit (default: 0.35)
                - stop_loss_pct: Stop loss as % of debit (default: 0.50)
                - days_before_near_expiry_exit: Days before near expiry to close (default: 3)
                - position_size_pct: Capital % per trade (default: 0.015)
                - max_positions: Maximum concurrent positions (default: 3)
        """
        default_config = {
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
        
        # Merge with provided config
        if config:
            default_config.update(config)
        
        super().__init__(name="CalendarSpreadStrategy", config=default_config)
        
        # Strategy-specific state
        self.calendar_positions: Dict[str, CalendarSpreadPosition] = {}
        self.iv_rank_history: pd.Series = pd.Series(dtype=float)
        self._iv_calculator = None
    
    def initialize(self, data: pd.DataFrame) -> None:
        """
        Initialize strategy with historical data.
        
        Pre-computes IV Rank time series for the dataset.
        
        Args:
            data: Historical options data
        """
        super().initialize(data)
        
        # Import IV calculator
        from ..indicators.volatility import IVRankCalculator
        self._iv_calculator = IVRankCalculator()
        
        # Pre-compute IV Rank if IV data available
        if "iv" in data.columns:
            # Get daily ATM IV
            iv_series = self._extract_atm_iv_series(data)
            if len(iv_series) > 0:
                self.iv_rank_history = self._iv_calculator.calculate_iv_rank(
                    iv_series, lookback_days=252
                )
        
        logger.info(f"Strategy initialized with {len(self.iv_rank_history)} IV Rank values")
    
    def _extract_atm_iv_series(self, data: pd.DataFrame) -> pd.Series:
        """
        Extract ATM IV time series from options data.
        
        Args:
            data: Options data DataFrame
        
        Returns:
            Series of ATM IV values indexed by date
        """
        iv_values = []
        
        for date in data["date"].unique():
            date_data = data[data["date"] == date]
            if date_data.empty:
                continue
            
            spot = date_data["spot_price"].iloc[0]
            
            # Find ATM options
            date_data = date_data.copy()
            date_data.loc[:, "distance"] = abs(date_data["strike"] - spot)
            atm_data = date_data[date_data["distance"] == date_data["distance"].min()]
            
            if not atm_data.empty and "iv" in atm_data.columns:
                iv_values.append({
                    "date": pd.to_datetime(date),
                    "iv": atm_data["iv"].mean()
                })
        
        if iv_values:
            iv_df = pd.DataFrame(iv_values).set_index("date")
            return iv_df["iv"]
        
        return pd.Series(dtype=float)
    
    def generate_signal(
        self,
        data: pd.DataFrame,
        timestamp: datetime
    ) -> Optional[Signal]:
        """
        Generate trading signal based on market data and IV Rank.
        
        Entry logic:
        1. Check if IV Rank < threshold (low IV environment)
        2. Check if we have capacity for new positions
        3. Find appropriate near and far expiries and strike
        
        Exit logic (checked separately in check_exit_conditions):
        1. Profit target reached
        2. Stop loss hit
        3. Time-based exit (near expiry approaching)
        
        Args:
            data: Market data up to current timestamp
            timestamp: Current timestamp
        
        Returns:
            Signal object or None
        """
        # Get current date data
        current_data = data[data["date"] == timestamp]
        if current_data.empty:
            return None
        
        # Check for exit signals first
        exit_signal = self._check_exit_conditions(current_data, timestamp)
        if exit_signal:
            return exit_signal
        
        # Check if we can take new positions
        if len(self.calendar_positions) >= self.config["max_positions"]:
            return None
        
        # Get current IV Rank
        current_iv_rank = self._get_current_iv_rank(data, timestamp)
        if current_iv_rank is None:
            return None
        
        # Check entry condition (IV Rank below threshold for calendars)
        if self.config["iv_rank_entry_below"]:
            if current_iv_rank >= self.config["iv_rank_entry_threshold"]:
                return None
        else:
            if current_iv_rank < self.config["iv_rank_entry_threshold"]:
                return None
        
        # Find suitable expiries and strike
        underlying = current_data["underlying"].iloc[0]
        entry_setup = self._find_entry_setup(current_data, timestamp)
        
        if entry_setup is None:
            return None
        
        # Generate entry signal
        return Signal(
            signal_type=SignalType.ENTRY_LONG,  # Calendar is a debit trade (long)
            symbol=f"{underlying}_CALENDAR",
            timestamp=timestamp,
            reason=f"IV Rank {current_iv_rank:.1f} < {self.config['iv_rank_entry_threshold']}",
            metadata={
                "strategy": "calendar_spread",
                "iv_rank": current_iv_rank,
                **entry_setup
            }
        )
    
    def _get_current_iv_rank(
        self,
        data: pd.DataFrame,
        timestamp: datetime
    ) -> Optional[float]:
        """
        Get current IV Rank from pre-computed history or calculate.
        
        Args:
            data: Market data
            timestamp: Current timestamp
        
        Returns:
            Current IV Rank or None
        """
        ts = pd.to_datetime(timestamp)
        
        # Try to get from pre-computed history
        if len(self.iv_rank_history) > 0 and ts in self.iv_rank_history.index:
            return self.iv_rank_history[ts]
        
        # Calculate from current data
        iv_series = self._extract_atm_iv_series(data[data["date"] <= timestamp])
        
        if len(iv_series) < 30:  # Need minimum history
            return None
        
        iv_rank = self._iv_calculator.calculate_iv_rank(iv_series)
        return iv_rank.iloc[-1] if len(iv_rank) > 0 else None
    
    def _find_entry_setup(
        self,
        current_data: pd.DataFrame,
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Find suitable calendar spread entry setup.
        
        Selects:
        - Near expiry within 7-14 days
        - Far expiry within 30-45 days
        - ATM strike (same for both)
        
        Args:
            current_data: Current day's options data
            timestamp: Current timestamp
        
        Returns:
            Dictionary with entry setup details or None
        """
        spot_price = current_data["spot_price"].iloc[0]
        underlying = current_data["underlying"].iloc[0]
        
        # Get expiry ranges
        near_min, near_max = self.config["near_expiry_days_range"]
        far_min, far_max = self.config["far_expiry_days_range"]
        
        # Find suitable expiries
        expiries = pd.to_datetime(current_data["expiry"]).unique()
        expiries_sorted = sorted(expiries)
        
        near_expiry = None
        far_expiry = None
        
        for expiry in expiries_sorted:
            dte = (expiry - pd.to_datetime(timestamp)).days
            
            if near_min <= dte <= near_max and near_expiry is None:
                near_expiry = expiry
            elif far_min <= dte <= far_max and far_expiry is None:
                far_expiry = expiry
        
        if near_expiry is None or far_expiry is None:
            return None
        
        # Find ATM strike
        strikes = current_data["strike"].unique()
        atm_strike = min(strikes, key=lambda x: abs(x - spot_price))
        
        # Get options at ATM strike for both expiries
        near_calls = current_data[
            (current_data["strike"] == atm_strike) &
            (current_data["option_type"] == "CE") &
            (pd.to_datetime(current_data["expiry"]) == near_expiry)
        ]
        far_calls = current_data[
            (current_data["strike"] == atm_strike) &
            (current_data["option_type"] == "CE") &
            (pd.to_datetime(current_data["expiry"]) == far_expiry)
        ]
        
        if near_calls.empty or far_calls.empty:
            return None
        
        near_call = near_calls.iloc[0]
        far_call = far_calls.iloc[0]
        
        # Calculate net debit (pay for far, receive for near)
        net_debit = far_call["ltp"] - near_call["ltp"]
        
        if net_debit <= 0:
            return None  # Should be a debit trade
        
        near_dte = (near_expiry - pd.to_datetime(timestamp)).days
        far_dte = (far_expiry - pd.to_datetime(timestamp)).days
        
        return {
            "underlying": underlying,
            "strike": atm_strike,
            "option_type": "CE",
            "near_expiry": near_expiry,
            "far_expiry": far_expiry,
            "near_dte": near_dte,
            "far_dte": far_dte,
            "spot_price": spot_price,
            "near_premium": near_call["ltp"],
            "far_premium": far_call["ltp"],
            "net_debit": net_debit,
            "near_iv": near_call.get("iv", 0),
            "far_iv": far_call.get("iv", 0),
            "near_theta": near_call.get("theta", 0),
            "far_theta": far_call.get("theta", 0),
        }
    
    def _check_exit_conditions(
        self,
        current_data: pd.DataFrame,
        timestamp: datetime
    ) -> Optional[Signal]:
        """
        Check exit conditions for all open calendar positions.
        
        Exit conditions:
        1. Profit target: 35% of debit paid
        2. Stop loss: 50% of debit lost
        3. Time exit: 2-3 days before near expiry
        
        Args:
            current_data: Current day's options data
            timestamp: Current timestamp
        
        Returns:
            Exit Signal or None
        """
        for pos_id, calendar in list(self.calendar_positions.items()):
            # Update current prices
            near_data = current_data[
                (current_data["strike"] == calendar.strike) &
                (current_data["option_type"] == calendar.option_type) &
                (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(calendar.near_expiry))
            ]
            far_data = current_data[
                (current_data["strike"] == calendar.strike) &
                (current_data["option_type"] == calendar.option_type) &
                (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(calendar.far_expiry))
            ]
            
            if near_data.empty or far_data.empty:
                continue
            
            calendar.near_current_price = near_data["ltp"].iloc[0]
            calendar.far_current_price = far_data["ltp"].iloc[0]
            
            profit_pct = calendar.get_profit_percentage()
            
            # Check time-based exit (near expiry approaching)
            days_to_near_expiry = (calendar.near_expiry - pd.to_datetime(timestamp)).days
            if days_to_near_expiry <= self.config["days_before_near_expiry_exit"]:
                return Signal(
                    signal_type=SignalType.EXIT_LONG,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Time exit: {days_to_near_expiry} days to near expiry",
                    metadata={
                        "exit_type": "time",
                        "profit_pct": profit_pct,
                        "current_value": calendar.get_current_value(),
                        "initial_debit": calendar.net_debit,
                    }
                )
            
            # Check profit target
            if profit_pct >= self.config["profit_target_pct"]:
                return Signal(
                    signal_type=SignalType.EXIT_LONG,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Profit target: {profit_pct:.1%} >= {self.config['profit_target_pct']:.1%}",
                    metadata={
                        "exit_type": "profit_target",
                        "profit_pct": profit_pct,
                        "current_value": calendar.get_current_value(),
                        "initial_debit": calendar.net_debit,
                    }
                )
            
            # Check stop loss (loss >= 50% of debit)
            if profit_pct <= -self.config["stop_loss_pct"]:
                return Signal(
                    signal_type=SignalType.EXIT_LONG,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Stop loss: {profit_pct:.1%} <= -{self.config['stop_loss_pct']:.1%}",
                    metadata={
                        "exit_type": "stop_loss",
                        "profit_pct": profit_pct,
                        "current_value": calendar.get_current_value(),
                        "initial_debit": calendar.net_debit,
                    }
                )
        
        return None
    
    def calculate_position_size(
        self,
        capital: float,
        price: float,
        signal: Signal
    ) -> int:
        """
        Calculate position size for a calendar spread trade.
        
        Position sizing based on:
        - Maximum risk per trade (% of capital)
        - Max loss = Net Debit Paid
        - Lot size of underlying
        
        Args:
            capital: Available capital
            price: Not used for calendars (use metadata from signal)
            signal: Trading signal with metadata
        
        Returns:
            Number of calendar spreads (lots) to trade
        """
        if signal.metadata.get("strategy") != "calendar_spread":
            return 0
        
        underlying = signal.metadata.get("underlying", "NIFTY")
        lot_size = self.config["lot_sizes"].get(underlying, 50)
        net_debit = signal.metadata.get("net_debit", 0)
        
        if net_debit <= 0:
            return 0
        
        # Maximum risk per trade
        max_risk = capital * self.config["position_size_pct"]
        
        # Max loss per calendar = net_debit * lot_size
        max_loss_per_calendar = net_debit * lot_size
        
        if max_loss_per_calendar <= 0:
            return 0
        
        # Calculate number of calendars
        num_calendars = int(max_risk / max_loss_per_calendar)
        
        return max(1, num_calendars)  # At least 1 calendar
    
    def open_calendar(
        self,
        signal: Signal,
        quantity: int
    ) -> CalendarSpreadPosition:
        """
        Open a new calendar spread position.
        
        Args:
            signal: Entry signal with calendar details
            quantity: Number of calendars to open
        
        Returns:
            CalendarSpreadPosition object
        """
        metadata = signal.metadata
        
        calendar = CalendarSpreadPosition(
            underlying=metadata["underlying"],
            strike=metadata["strike"],
            option_type=metadata["option_type"],
            near_expiry=metadata["near_expiry"],
            far_expiry=metadata["far_expiry"],
            near_premium=metadata["near_premium"],
            far_premium=metadata["far_premium"],
            net_debit=metadata["net_debit"],
            entry_date=signal.timestamp,
            quantity=quantity,
            near_current_price=metadata["near_premium"],
            far_current_price=metadata["far_premium"],
            entry_iv_rank=metadata.get("iv_rank", 0),
            entry_spot=metadata["spot_price"],
            metadata=metadata
        )
        
        # Generate unique position ID
        pos_id = (
            f"{metadata['underlying']}_{metadata['near_expiry'].strftime('%Y%m%d')}_"
            f"{metadata['far_expiry'].strftime('%Y%m%d')}_{metadata['strike']}_{metadata['option_type']}"
        )
        self.calendar_positions[pos_id] = calendar
        
        logger.info(
            f"Opened Calendar: {pos_id}, "
            f"Strike={metadata['strike']}, "
            f"Near={metadata['near_expiry'].strftime('%Y-%m-%d')} @ {metadata['near_premium']:.2f}, "
            f"Far={metadata['far_expiry'].strftime('%Y-%m-%d')} @ {metadata['far_premium']:.2f}, "
            f"Net Debit={metadata['net_debit']:.2f}"
        )
        
        return calendar
    
    def close_calendar(
        self,
        pos_id: str,
        signal: Signal
    ) -> Trade:
        """
        Close a calendar spread position.
        
        Args:
            pos_id: Position identifier
            signal: Exit signal
        
        Returns:
            Trade object representing the closed position
        """
        calendar = self.calendar_positions[pos_id]
        
        initial_debit = calendar.net_debit * calendar.quantity
        exit_value = calendar.get_current_value()
        pnl = exit_value - initial_debit
        
        lot_size = self.config["lot_sizes"].get(calendar.underlying, 50)
        
        trade = Trade(
            symbol=pos_id,
            direction="LONG",
            quantity=calendar.quantity * lot_size,
            entry_price=calendar.net_debit,
            exit_price=exit_value / calendar.quantity if calendar.quantity > 0 else 0,
            entry_date=calendar.entry_date,
            exit_date=signal.timestamp,
            pnl=pnl * lot_size,  # Scale by lot size
            exit_reason=signal.reason,
            metadata={
                "strategy": "calendar_spread",
                "strike": calendar.strike,
                "option_type": calendar.option_type,
                "near_expiry": calendar.near_expiry,
                "far_expiry": calendar.far_expiry,
                "entry_iv_rank": calendar.entry_iv_rank,
                "exit_type": signal.metadata.get("exit_type", "unknown"),
            }
        )
        
        # Calculate return percentage
        trade.return_pct = pnl / initial_debit if initial_debit > 0 else 0
        
        self.trades.append(trade)
        del self.calendar_positions[pos_id]
        
        logger.info(
            f"Closed Calendar: {pos_id}, "
            f"PnL={pnl:.2f}, Return={trade.return_pct:.2%}, "
            f"Reason={signal.reason}"
        )
        
        return trade
    
    def should_exit(
        self,
        position: CalendarSpreadPosition,
        current_spot: float,
        current_timestamp: datetime
    ) -> Tuple[bool, str]:
        """
        Determine if a calendar spread position should be exited.
        
        Args:
            position: The calendar spread position to check
            current_spot: Current spot price
            current_timestamp: Current timestamp
        
        Returns:
            Tuple of (should_exit, reason)
        """
        # Time-based exit (near expiry approaching)
        days_to_near_expiry = (position.near_expiry - pd.to_datetime(current_timestamp)).days
        if days_to_near_expiry <= self.config["days_before_near_expiry_exit"]:
            return True, f"Time exit: {days_to_near_expiry} days to near expiry"
        
        # Profit target
        profit_pct = position.get_profit_percentage()
        if profit_pct >= self.config["profit_target_pct"]:
            return True, f"Profit target reached: {profit_pct:.1%}"
        
        # Stop loss
        if profit_pct <= -self.config["stop_loss_pct"]:
            return True, f"Stop loss triggered: {profit_pct:.1%}"
        
        return False, ""
    
    def get_strategy_statistics(self) -> Dict[str, Any]:
        """
        Get detailed strategy statistics.
        
        Returns:
            Dictionary with strategy-specific statistics
        """
        base_stats = self.get_trade_statistics()
        
        # Add calendar-specific stats
        if self.trades:
            exit_types = {}
            for trade in self.trades:
                exit_type = trade.metadata.get("exit_type", "unknown")
                exit_types[exit_type] = exit_types.get(exit_type, 0) + 1
            
            base_stats["exit_type_breakdown"] = exit_types
            base_stats["avg_holding_period"] = sum(t.holding_period for t in self.trades) / len(self.trades)
        
        base_stats["open_positions"] = len(self.calendar_positions)
        base_stats["config"] = self.config
        
        return base_stats
    
    def reset(self) -> None:
        """Reset strategy state."""
        super().reset()
        self.calendar_positions.clear()
        self.iv_rank_history = pd.Series(dtype=float)
