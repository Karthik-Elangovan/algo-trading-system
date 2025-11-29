"""
Premium Selling Strategy Module

Implements a Short Strangle strategy for high implied volatility environments.

Strategy Overview:
- Entry: When IV Rank > 70 (high implied volatility)
- Position: Short Strangle (sell OTM call + sell OTM put) at 15-20 delta strikes
- Exit Conditions:
  1. Take profit at 50% of premium collected
  2. Stop loss at 150% of premium (2.5x initial credit)
  3. Time-based exit: Close 2-3 days before expiry

Risk Management:
- Position size: 1-2% of capital per trade
- Maximum positions: Configurable (default 5)
- Only enter when IV Rank threshold is met

Note: Short strangles have unlimited risk potential. This strategy
should only be used with proper risk management and position sizing.
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
class StranglePosition:
    """
    Data class representing a short strangle position.
    
    A strangle consists of:
    - Short OTM Call (above spot)
    - Short OTM Put (below spot)
    
    Attributes:
        underlying: Name of underlying
        expiry: Expiry date
        call_strike: Strike price of short call
        put_strike: Strike price of short put
        call_premium: Premium received for call
        put_premium: Premium received for put
        total_premium: Total premium collected
        entry_date: Date position was opened
        quantity: Number of strangles (lot multiplier)
        call_current_price: Current price of call
        put_current_price: Current price of put
        entry_iv_rank: IV Rank at entry
        entry_spot: Spot price at entry
    """
    underlying: str
    expiry: datetime
    call_strike: float
    put_strike: float
    call_premium: float
    put_premium: float
    total_premium: float
    entry_date: datetime
    quantity: int = 1
    call_current_price: float = 0.0
    put_current_price: float = 0.0
    entry_iv_rank: float = 0.0
    entry_spot: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_current_cost_to_close(self) -> float:
        """Calculate current cost to close the position."""
        return (self.call_current_price + self.put_current_price) * self.quantity
    
    def get_unrealized_pnl(self) -> float:
        """Calculate unrealized P&L."""
        return (self.total_premium * self.quantity) - self.get_current_cost_to_close()
    
    def get_profit_percentage(self) -> float:
        """Calculate profit as percentage of premium collected."""
        if self.total_premium > 0:
            return self.get_unrealized_pnl() / (self.total_premium * self.quantity)
        return 0.0


class PremiumSellingStrategy(BaseStrategy):
    """
    Premium Selling Strategy using Short Strangles.
    
    This strategy sells options premium when implied volatility is high,
    expecting IV to mean-revert and option prices to decay.
    
    Entry Criteria:
    - IV Rank > 70 (configurable)
    - Select strikes at 15-20 delta
    - Minimum days to expiry for entry
    
    Exit Criteria:
    - Profit target: 50% of premium collected
    - Stop loss: 150% of premium (position worth 2.5x credit)
    - Time exit: 2-3 days before expiry
    
    Position Management:
    - Maximum concurrent positions
    - Position sizing based on capital percentage
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Premium Selling Strategy.
        
        Args:
            config: Strategy configuration dictionary with:
                - iv_rank_entry_threshold: Minimum IV Rank for entry (default: 70)
                - delta_range: Target delta range for strikes (default: (0.15, 0.20))
                - profit_target_pct: Profit target as % of premium (default: 0.50)
                - stop_loss_pct: Stop loss as % of premium (default: 1.50)
                - days_before_expiry_exit: Days before expiry to close (default: 3)
                - position_size_pct: Capital % per trade (default: 0.02)
                - min_days_to_expiry: Minimum DTE for entry (default: 7)
                - max_days_to_expiry: Maximum DTE for entry (default: 45)
                - max_positions: Maximum concurrent positions (default: 5)
        """
        default_config = {
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
        
        # Merge with provided config
        if config:
            default_config.update(config)
        
        super().__init__(name="PremiumSellingStrategy", config=default_config)
        
        # Strategy-specific state
        self.strangle_positions: Dict[str, StranglePosition] = {}
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
        1. Check if IV Rank > threshold
        2. Check if we have capacity for new positions
        3. Find appropriate expiry and strikes
        
        Exit logic (checked separately in check_exit_conditions):
        1. Profit target reached
        2. Stop loss hit
        3. Time-based exit
        
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
        if len(self.strangle_positions) >= self.config["max_positions"]:
            return None
        
        # Get current IV Rank
        current_iv_rank = self._get_current_iv_rank(data, timestamp)
        if current_iv_rank is None:
            return None
        
        # Check entry condition
        if current_iv_rank < self.config["iv_rank_entry_threshold"]:
            return None
        
        # Find suitable expiry and strikes
        underlying = current_data["underlying"].iloc[0]
        entry_setup = self._find_entry_setup(current_data, timestamp)
        
        if entry_setup is None:
            return None
        
        # Generate entry signal
        return Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol=f"{underlying}_STRANGLE",
            timestamp=timestamp,
            reason=f"IV Rank {current_iv_rank:.1f} > {self.config['iv_rank_entry_threshold']}",
            metadata={
                "strategy": "short_strangle",
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
        Find suitable strangle entry setup.
        
        Selects:
        - Expiry within target DTE range
        - Call strike at target delta (OTM)
        - Put strike at target delta (OTM)
        
        Args:
            current_data: Current day's options data
            timestamp: Current timestamp
        
        Returns:
            Dictionary with entry setup details or None
        """
        spot_price = current_data["spot_price"].iloc[0]
        underlying = current_data["underlying"].iloc[0]
        
        # Get target delta range
        delta_low, delta_high = self.config["delta_range"]
        
        # Find suitable expiries
        expiries = pd.to_datetime(current_data["expiry"]).unique()
        
        for expiry in sorted(expiries):
            dte = (expiry - pd.to_datetime(timestamp)).days
            
            # Check DTE constraints
            if dte < self.config["min_days_to_expiry"]:
                continue
            if dte > self.config["max_days_to_expiry"]:
                continue
            
            expiry_data = current_data[pd.to_datetime(current_data["expiry"]) == expiry]
            
            # Find call strike at target delta
            calls = expiry_data[expiry_data["option_type"] == "CE"].copy()
            puts = expiry_data[expiry_data["option_type"] == "PE"].copy()
            
            if calls.empty or puts.empty:
                continue
            
            # Select OTM call (delta between delta_low and delta_high)
            otm_calls = calls[
                (calls["strike"] > spot_price) &
                (calls["delta"] >= delta_low) &
                (calls["delta"] <= delta_high)
            ]
            
            # Select OTM put (delta between -delta_high and -delta_low)
            otm_puts = puts[
                (puts["strike"] < spot_price) &
                (puts["delta"] <= -delta_low) &
                (puts["delta"] >= -delta_high)
            ]
            
            if otm_calls.empty or otm_puts.empty:
                # Fallback: Select closest to target delta
                otm_calls = calls[calls["strike"] > spot_price]
                otm_puts = puts[puts["strike"] < spot_price]
                
                if otm_calls.empty or otm_puts.empty:
                    continue
                
                # Sort by delta distance from target
                target_delta = (delta_low + delta_high) / 2
                otm_calls = otm_calls.copy()
                otm_calls.loc[:, "delta_dist"] = abs(otm_calls["delta"] - target_delta)
                otm_puts = otm_puts.copy()
                otm_puts.loc[:, "delta_dist"] = abs(abs(otm_puts["delta"]) - target_delta)
                
                otm_calls = otm_calls.nsmallest(1, "delta_dist")
                otm_puts = otm_puts.nsmallest(1, "delta_dist")
            else:
                # Select strike with delta closest to middle of range
                target_delta = (delta_low + delta_high) / 2
                otm_calls = otm_calls.copy()
                otm_calls.loc[:, "delta_dist"] = abs(otm_calls["delta"] - target_delta)
                otm_puts = otm_puts.copy()
                otm_puts.loc[:, "delta_dist"] = abs(abs(otm_puts["delta"]) - target_delta)
                
                otm_calls = otm_calls.nsmallest(1, "delta_dist")
                otm_puts = otm_puts.nsmallest(1, "delta_dist")
            
            call = otm_calls.iloc[0]
            put = otm_puts.iloc[0]
            
            return {
                "underlying": underlying,
                "expiry": expiry,
                "dte": dte,
                "spot_price": spot_price,
                "call_strike": call["strike"],
                "put_strike": put["strike"],
                "call_premium": call["ltp"],
                "put_premium": put["ltp"],
                "total_premium": call["ltp"] + put["ltp"],
                "call_delta": call["delta"],
                "put_delta": put["delta"],
                "call_iv": call["iv"],
                "put_iv": put["iv"],
            }
        
        return None
    
    def _check_exit_conditions(
        self,
        current_data: pd.DataFrame,
        timestamp: datetime
    ) -> Optional[Signal]:
        """
        Check exit conditions for all open strangle positions.
        
        Exit conditions:
        1. Profit target: 50% of premium collected
        2. Stop loss: Position worth 250% of credit (150% loss)
        3. Time exit: 2-3 days before expiry
        
        Args:
            current_data: Current day's options data
            timestamp: Current timestamp
        
        Returns:
            Exit Signal or None
        """
        for pos_id, strangle in list(self.strangle_positions.items()):
            # Update current prices
            call_data = current_data[
                (current_data["strike"] == strangle.call_strike) &
                (current_data["option_type"] == "CE") &
                (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(strangle.expiry))
            ]
            put_data = current_data[
                (current_data["strike"] == strangle.put_strike) &
                (current_data["option_type"] == "PE") &
                (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(strangle.expiry))
            ]
            
            if call_data.empty or put_data.empty:
                continue
            
            strangle.call_current_price = call_data["ltp"].iloc[0]
            strangle.put_current_price = put_data["ltp"].iloc[0]
            
            current_cost = strangle.get_current_cost_to_close()
            initial_credit = strangle.total_premium * strangle.quantity
            profit_pct = strangle.get_profit_percentage()
            
            # Check time-based exit
            days_to_expiry = (strangle.expiry - pd.to_datetime(timestamp)).days
            if days_to_expiry <= self.config["days_before_expiry_exit"]:
                return Signal(
                    signal_type=SignalType.EXIT_SHORT,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Time exit: {days_to_expiry} days to expiry",
                    metadata={
                        "exit_type": "time",
                        "profit_pct": profit_pct,
                        "current_cost": current_cost,
                        "initial_credit": initial_credit,
                    }
                )
            
            # Check profit target (50% of premium captured)
            if profit_pct >= self.config["profit_target_pct"]:
                return Signal(
                    signal_type=SignalType.EXIT_SHORT,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Profit target: {profit_pct:.1%} >= {self.config['profit_target_pct']:.1%}",
                    metadata={
                        "exit_type": "profit_target",
                        "profit_pct": profit_pct,
                        "current_cost": current_cost,
                        "initial_credit": initial_credit,
                    }
                )
            
            # Check stop loss (position worth 250% of credit = 150% loss)
            stop_loss_threshold = initial_credit * (1 + self.config["stop_loss_pct"])
            if current_cost >= stop_loss_threshold:
                return Signal(
                    signal_type=SignalType.EXIT_SHORT,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Stop loss: current cost {current_cost:.2f} >= {stop_loss_threshold:.2f}",
                    metadata={
                        "exit_type": "stop_loss",
                        "profit_pct": profit_pct,
                        "current_cost": current_cost,
                        "initial_credit": initial_credit,
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
        Calculate position size for a strangle trade.
        
        Position sizing based on:
        - Maximum risk per trade (% of capital)
        - Lot size of underlying
        - Premium collected
        
        Args:
            capital: Available capital
            price: Not used for strangles (use premium from signal metadata)
            signal: Trading signal with metadata
        
        Returns:
            Number of strangles (lots) to trade
        """
        if signal.metadata.get("strategy") != "short_strangle":
            return 0
        
        underlying = signal.metadata.get("underlying", "NIFTY")
        lot_size = self.config["lot_sizes"].get(underlying, 50)
        total_premium = signal.metadata.get("total_premium", 0)
        
        if total_premium <= 0:
            return 0
        
        # Maximum risk per trade
        max_risk = capital * self.config["position_size_pct"]
        
        # Risk per strangle = stop loss amount
        # Stop loss at 150% of premium means max loss = 150% of premium
        risk_per_strangle = total_premium * self.config["stop_loss_pct"] * lot_size
        
        if risk_per_strangle <= 0:
            return 0
        
        # Calculate number of strangles
        num_strangles = int(max_risk / risk_per_strangle)
        
        return max(1, num_strangles)  # At least 1 strangle
    
    def open_strangle(
        self,
        signal: Signal,
        quantity: int
    ) -> StranglePosition:
        """
        Open a new strangle position.
        
        Args:
            signal: Entry signal with strangle details
            quantity: Number of strangles to open
        
        Returns:
            StranglePosition object
        """
        metadata = signal.metadata
        
        strangle = StranglePosition(
            underlying=metadata["underlying"],
            expiry=metadata["expiry"],
            call_strike=metadata["call_strike"],
            put_strike=metadata["put_strike"],
            call_premium=metadata["call_premium"],
            put_premium=metadata["put_premium"],
            total_premium=metadata["total_premium"],
            entry_date=signal.timestamp,
            quantity=quantity,
            call_current_price=metadata["call_premium"],
            put_current_price=metadata["put_premium"],
            entry_iv_rank=metadata.get("iv_rank", 0),
            entry_spot=metadata["spot_price"],
            metadata=metadata
        )
        
        # Generate unique position ID
        pos_id = f"{metadata['underlying']}_{metadata['expiry'].strftime('%Y%m%d')}_{metadata['call_strike']}_{metadata['put_strike']}"
        self.strangle_positions[pos_id] = strangle
        
        logger.info(
            f"Opened strangle: {pos_id}, "
            f"Call={metadata['call_strike']}@{metadata['call_premium']:.2f}, "
            f"Put={metadata['put_strike']}@{metadata['put_premium']:.2f}, "
            f"Total Premium={metadata['total_premium']:.2f}"
        )
        
        return strangle
    
    def close_strangle(
        self,
        pos_id: str,
        signal: Signal
    ) -> Trade:
        """
        Close a strangle position.
        
        Args:
            pos_id: Position identifier
            signal: Exit signal
        
        Returns:
            Trade object representing the closed position
        """
        strangle = self.strangle_positions[pos_id]
        
        initial_credit = strangle.total_premium * strangle.quantity
        exit_cost = strangle.get_current_cost_to_close()
        pnl = initial_credit - exit_cost
        
        lot_size = self.config["lot_sizes"].get(strangle.underlying, 50)
        
        trade = Trade(
            symbol=pos_id,
            direction="SHORT",
            quantity=strangle.quantity * lot_size,
            entry_price=strangle.total_premium,
            exit_price=(strangle.call_current_price + strangle.put_current_price),
            entry_date=strangle.entry_date,
            exit_date=signal.timestamp,
            pnl=pnl * lot_size,  # Scale by lot size
            exit_reason=signal.reason,
            metadata={
                "strategy": "short_strangle",
                "call_strike": strangle.call_strike,
                "put_strike": strangle.put_strike,
                "entry_iv_rank": strangle.entry_iv_rank,
                "exit_type": signal.metadata.get("exit_type", "unknown"),
            }
        )
        
        # Calculate return percentage
        trade.return_pct = pnl / initial_credit if initial_credit > 0 else 0
        
        self.trades.append(trade)
        del self.strangle_positions[pos_id]
        
        logger.info(
            f"Closed strangle: {pos_id}, "
            f"PnL={pnl:.2f}, Return={trade.return_pct:.2%}, "
            f"Reason={signal.reason}"
        )
        
        return trade
    
    def get_strategy_statistics(self) -> Dict[str, Any]:
        """
        Get detailed strategy statistics.
        
        Returns:
            Dictionary with strategy-specific statistics
        """
        base_stats = self.get_trade_statistics()
        
        # Add strangle-specific stats
        if self.trades:
            exit_types = {}
            for trade in self.trades:
                exit_type = trade.metadata.get("exit_type", "unknown")
                exit_types[exit_type] = exit_types.get(exit_type, 0) + 1
            
            base_stats["exit_type_breakdown"] = exit_types
            base_stats["avg_holding_period"] = sum(t.holding_period for t in self.trades) / len(self.trades)
        
        base_stats["open_positions"] = len(self.strangle_positions)
        base_stats["config"] = self.config
        
        return base_stats
    
    def reset(self) -> None:
        """Reset strategy state."""
        super().reset()
        self.strangle_positions.clear()
        self.iv_rank_history = pd.Series(dtype=float)
