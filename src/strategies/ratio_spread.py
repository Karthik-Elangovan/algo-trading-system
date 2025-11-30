"""
Ratio Spread Strategy Module

Implements a Ratio Spread options strategy for directional trades with premium collection.

Strategy Overview:
A Ratio Spread involves buying and selling options at different strikes
in unequal quantities. It combines directional exposure with premium selling.

Structure (Put Ratio Spread - Bullish):
- Buy 1 ATM Put
- Sell 2 OTM Puts

Structure (Call Ratio Spread - Bearish):
- Buy 1 ATM Call
- Sell 2 OTM Calls

Entry Conditions:
- IV Rank > 60 (high IV for selling extra options)
- Directional bias required (bullish for put ratio, bearish for call ratio)
- Ratio: 1:2 (can adjust to 1:3 in very high IV)
- Short strikes at 20-25 delta
- 21-45 days to expiry

Exit Conditions:
- Profit target: 75% of max profit
- Stop loss: If underlying breaches short strike significantly
- Time exit: Close 7 days before expiry
- Max profit at short strike at expiry

Risk Profile:
- Limited risk on one side (direction of long option)
- Unlimited/high risk on other side (naked short exposure)
- Credit or small debit entry typically

Mathematical Formulas (1:2 Put Ratio Spread):
- Max Profit = (Long Strike - Short Strike) + Net Credit (at short strike)
- Downside Risk = Unlimited below (Short Strike - Max Profit)
- Upside Risk = Net Debit (if any)

Note: Ratio spreads have asymmetric risk profiles. The extra sold options
create additional risk but generate premium to offset the cost of protection.
Best suited for high IV environments with a directional view.
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
class RatioSpreadPosition:
    """
    Data class representing a Ratio Spread position.
    
    A Ratio Spread consists of:
    - Long option at one strike (ATM)
    - Short options at another strike (OTM) in greater quantity
    
    Attributes:
        underlying: Name of underlying
        expiry: Expiry date
        spread_type: "PUT_RATIO" (bullish) or "CALL_RATIO" (bearish)
        long_strike: Strike of long option (ATM)
        short_strike: Strike of short options (OTM)
        long_quantity: Number of long options (typically 1)
        short_quantity: Number of short options (typically 2)
        long_premium: Premium paid for long option
        short_premium: Premium received per short option
        net_credit_debit: Net credit (+) or debit (-) at entry
        entry_date: Date position was opened
        quantity: Multiplier for the ratio spread (lot multiplier)
        long_current_price: Current price of long option
        short_current_price: Current price of short options
        entry_iv_rank: IV Rank at entry
        entry_spot: Spot price at entry
    """
    underlying: str
    expiry: datetime
    spread_type: str  # "PUT_RATIO" or "CALL_RATIO"
    long_strike: float
    short_strike: float
    long_quantity: int
    short_quantity: int
    long_premium: float
    short_premium: float
    net_credit_debit: float  # Positive = credit, Negative = debit
    entry_date: datetime
    quantity: int = 1  # Multiplier for entire spread
    long_current_price: float = 0.0
    short_current_price: float = 0.0
    entry_iv_rank: float = 0.0
    entry_spot: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_current_value(self) -> float:
        """Calculate current value/cost to close the position."""
        # Value = Long options - Short options
        long_value = self.long_current_price * self.long_quantity
        short_value = self.short_current_price * self.short_quantity
        return (long_value - short_value) * self.quantity
    
    def get_unrealized_pnl(self) -> float:
        """Calculate unrealized P&L."""
        initial_cost = -self.net_credit_debit * self.quantity  # Negative if credit received
        current_value = self.get_current_value()
        return current_value - initial_cost
    
    def get_profit_percentage(self) -> float:
        """Calculate profit as percentage of max profit at entry."""
        max_profit = self.get_max_profit_at_short_strike()
        if max_profit > 0:
            return self.get_unrealized_pnl() / max_profit
        return 0.0
    
    def get_max_profit_at_short_strike(self) -> float:
        """
        Calculate maximum profit achieved if underlying is at short strike at expiry.
        
        For Put Ratio: Max profit = (Long Strike - Short Strike) + Net Credit
        For Call Ratio: Max profit = (Short Strike - Long Strike) + Net Credit
        """
        if self.spread_type == "PUT_RATIO":
            intrinsic = self.long_strike - self.short_strike
        else:  # CALL_RATIO
            intrinsic = self.short_strike - self.long_strike
        
        return (intrinsic + self.net_credit_debit) * self.quantity
    
    def get_breakeven_point(self) -> float:
        """
        Calculate the breakeven point on the risk side.
        
        For Put Ratio: Below short strike
        For Call Ratio: Above short strike
        """
        max_profit = self.get_max_profit_at_short_strike()
        
        if self.spread_type == "PUT_RATIO":
            # Breakeven = Short Strike - Max Profit
            return self.short_strike - max_profit / self.quantity
        else:  # CALL_RATIO
            # Breakeven = Short Strike + Max Profit
            return self.short_strike + max_profit / self.quantity


class RatioSpreadStrategy(BaseStrategy):
    """
    Ratio Spread Strategy for directional trades with premium collection.
    
    This strategy combines directional exposure with premium selling
    by buying one option and selling multiple options at a different strike.
    
    Entry Criteria:
    - IV Rank > 60 (high IV for selling extra options)
    - Short strikes at 20-25 delta
    - 21-45 days to expiry
    
    Exit Criteria:
    - Profit target: 75% of max profit
    - Stop loss: Underlying breaches short strike significantly
    - Time exit: 7 days before expiry
    
    Position Management:
    - Maximum concurrent positions
    - Lower position sizing due to higher risk profile
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Ratio Spread Strategy.
        
        Args:
            config: Strategy configuration dictionary with:
                - iv_rank_entry_threshold: Minimum IV Rank for entry (default: 60)
                - ratio: Tuple of (buy, sell) quantities (default: (1, 2))
                - long_delta: Delta for long option (default: 0.50 for ATM)
                - short_delta_range: Delta range for short strikes (default: (0.20, 0.25))
                - profit_target_pct: Profit target as % of max profit (default: 0.75)
                - stop_loss_breach_pct: Exit if underlying moves this % beyond short strike (default: 0.02)
                - days_before_expiry_exit: Days before expiry to close (default: 7)
                - min_days_to_expiry: Minimum DTE for entry (default: 21)
                - max_days_to_expiry: Maximum DTE for entry (default: 45)
                - position_size_pct: Capital % per trade (default: 0.01)
                - max_positions: Maximum concurrent positions (default: 2)
        """
        default_config = {
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
            "spread_type": "PUT_RATIO",  # Default to bullish put ratio
        }
        
        # Merge with provided config
        if config:
            default_config.update(config)
        
        super().__init__(name="RatioSpreadStrategy", config=default_config)
        
        # Strategy-specific state
        self.ratio_positions: Dict[str, RatioSpreadPosition] = {}
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
        1. Check if IV Rank > threshold (high IV)
        2. Check if we have capacity for new positions
        3. Find appropriate expiry and strikes for ratio spread
        
        Exit logic (checked separately in check_exit_conditions):
        1. Profit target reached
        2. Short strike breached significantly
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
        if len(self.ratio_positions) >= self.config["max_positions"]:
            return None
        
        # Get current IV Rank
        current_iv_rank = self._get_current_iv_rank(data, timestamp)
        if current_iv_rank is None:
            return None
        
        # Check entry condition (high IV for ratio spreads)
        if current_iv_rank < self.config["iv_rank_entry_threshold"]:
            return None
        
        # Find suitable expiry and strikes
        underlying = current_data["underlying"].iloc[0]
        entry_setup = self._find_entry_setup(current_data, timestamp)
        
        if entry_setup is None:
            return None
        
        # Determine signal type based on spread type
        spread_type = self.config["spread_type"]
        if spread_type == "PUT_RATIO":
            signal_type = SignalType.ENTRY_LONG  # Bullish bias
        else:
            signal_type = SignalType.ENTRY_SHORT  # Bearish bias
        
        # Generate entry signal
        return Signal(
            signal_type=signal_type,
            symbol=f"{underlying}_RATIO_SPREAD",
            timestamp=timestamp,
            reason=f"IV Rank {current_iv_rank:.1f} > {self.config['iv_rank_entry_threshold']}",
            metadata={
                "strategy": "ratio_spread",
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
        Find suitable ratio spread entry setup.
        
        Selects:
        - Expiry within target DTE range
        - Long option at ATM (0.50 delta)
        - Short options at OTM (20-25 delta)
        
        Args:
            current_data: Current day's options data
            timestamp: Current timestamp
        
        Returns:
            Dictionary with entry setup details or None
        """
        spot_price = current_data["spot_price"].iloc[0]
        underlying = current_data["underlying"].iloc[0]
        
        # Get ratio and delta parameters
        long_qty, short_qty = self.config["ratio"]
        short_delta_low, short_delta_high = self.config["short_delta_range"]
        spread_type = self.config["spread_type"]
        
        # Determine option type based on spread type
        option_type = "PE" if spread_type == "PUT_RATIO" else "CE"
        
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
            
            # Get options of the appropriate type
            options = expiry_data[expiry_data["option_type"] == option_type].copy()
            
            if options.empty:
                continue
            
            # Find ATM option for long position (closest to spot)
            options.loc[:, "distance"] = abs(options["strike"] - spot_price)
            atm_options = options.nsmallest(1, "distance")
            
            if atm_options.empty:
                continue
            
            long_option = atm_options.iloc[0]
            long_strike = long_option["strike"]
            
            # Find OTM option for short positions
            if spread_type == "PUT_RATIO":
                # For put ratio, short puts are below long put (further OTM)
                otm_options = options[
                    (options["strike"] < long_strike) &
                    (abs(options["delta"]) >= short_delta_low) &
                    (abs(options["delta"]) <= short_delta_high)
                ]
                
                if otm_options.empty:
                    # Fallback: find any OTM put
                    otm_options = options[options["strike"] < long_strike]
                    if otm_options.empty:
                        continue
                    
                    # Select closest to target delta
                    target_delta = (short_delta_low + short_delta_high) / 2
                    otm_options = otm_options.copy()
                    otm_options.loc[:, "delta_dist"] = abs(abs(otm_options["delta"]) - target_delta)
                    otm_options = otm_options.nsmallest(1, "delta_dist")
            else:
                # For call ratio, short calls are above long call (further OTM)
                otm_options = options[
                    (options["strike"] > long_strike) &
                    (options["delta"] >= short_delta_low) &
                    (options["delta"] <= short_delta_high)
                ]
                
                if otm_options.empty:
                    # Fallback: find any OTM call
                    otm_options = options[options["strike"] > long_strike]
                    if otm_options.empty:
                        continue
                    
                    # Select closest to target delta
                    target_delta = (short_delta_low + short_delta_high) / 2
                    otm_options = otm_options.copy()
                    otm_options.loc[:, "delta_dist"] = abs(otm_options["delta"] - target_delta)
                    otm_options = otm_options.nsmallest(1, "delta_dist")
            
            short_option = otm_options.iloc[0]
            short_strike = short_option["strike"]
            
            # Calculate net credit/debit
            long_cost = long_option["ltp"] * long_qty
            short_received = short_option["ltp"] * short_qty
            net_credit_debit = short_received - long_cost  # Positive = credit
            
            return {
                "underlying": underlying,
                "expiry": expiry,
                "dte": dte,
                "spot_price": spot_price,
                "spread_type": spread_type,
                "option_type": option_type,
                "long_strike": long_strike,
                "short_strike": short_strike,
                "long_quantity": long_qty,
                "short_quantity": short_qty,
                "long_premium": long_option["ltp"],
                "short_premium": short_option["ltp"],
                "net_credit_debit": net_credit_debit,
                "long_delta": long_option.get("delta", 0.50),
                "short_delta": short_option.get("delta", 0.20),
                "long_iv": long_option.get("iv", 0),
                "short_iv": short_option.get("iv", 0),
            }
        
        return None
    
    def _check_exit_conditions(
        self,
        current_data: pd.DataFrame,
        timestamp: datetime
    ) -> Optional[Signal]:
        """
        Check exit conditions for all open ratio spread positions.
        
        Exit conditions:
        1. Profit target: 75% of max profit
        2. Stop loss: Underlying breaches short strike significantly
        3. Time exit: 7 days before expiry
        
        Args:
            current_data: Current day's options data
            timestamp: Current timestamp
        
        Returns:
            Exit Signal or None
        """
        for pos_id, ratio in list(self.ratio_positions.items()):
            # Get current spot price
            if current_data.empty:
                continue
            
            current_spot = current_data["spot_price"].iloc[0]
            
            # Update current option prices
            option_type = "PE" if ratio.spread_type == "PUT_RATIO" else "CE"
            
            long_data = current_data[
                (current_data["strike"] == ratio.long_strike) &
                (current_data["option_type"] == option_type) &
                (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(ratio.expiry))
            ]
            short_data = current_data[
                (current_data["strike"] == ratio.short_strike) &
                (current_data["option_type"] == option_type) &
                (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(ratio.expiry))
            ]
            
            if long_data.empty or short_data.empty:
                continue
            
            ratio.long_current_price = long_data["ltp"].iloc[0]
            ratio.short_current_price = short_data["ltp"].iloc[0]
            
            profit_pct = ratio.get_profit_percentage()
            
            # Check time-based exit
            days_to_expiry = (ratio.expiry - pd.to_datetime(timestamp)).days
            if days_to_expiry <= self.config["days_before_expiry_exit"]:
                return Signal(
                    signal_type=SignalType.EXIT_LONG if ratio.spread_type == "PUT_RATIO" else SignalType.EXIT_SHORT,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Time exit: {days_to_expiry} days to expiry",
                    metadata={
                        "exit_type": "time",
                        "profit_pct": profit_pct,
                        "current_value": ratio.get_current_value(),
                        "initial_credit_debit": ratio.net_credit_debit,
                    }
                )
            
            # Check profit target (75% of max profit)
            if profit_pct >= self.config["profit_target_pct"]:
                return Signal(
                    signal_type=SignalType.EXIT_LONG if ratio.spread_type == "PUT_RATIO" else SignalType.EXIT_SHORT,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Profit target: {profit_pct:.1%} >= {self.config['profit_target_pct']:.1%}",
                    metadata={
                        "exit_type": "profit_target",
                        "profit_pct": profit_pct,
                        "current_value": ratio.get_current_value(),
                        "initial_credit_debit": ratio.net_credit_debit,
                    }
                )
            
            # Check stop loss (underlying breaches short strike significantly)
            breach_threshold = ratio.short_strike * (1 - self.config["stop_loss_breach_pct"])
            if ratio.spread_type == "PUT_RATIO":
                # For put ratio, risk is on downside
                if current_spot <= breach_threshold:
                    return Signal(
                        signal_type=SignalType.EXIT_LONG,
                        symbol=pos_id,
                        timestamp=timestamp,
                        reason=f"Stop loss: spot {current_spot:.0f} breached {breach_threshold:.0f}",
                        metadata={
                            "exit_type": "stop_loss",
                            "profit_pct": profit_pct,
                            "current_value": ratio.get_current_value(),
                            "breach_level": breach_threshold,
                        }
                    )
            else:
                # For call ratio, risk is on upside
                breach_threshold = ratio.short_strike * (1 + self.config["stop_loss_breach_pct"])
                if current_spot >= breach_threshold:
                    return Signal(
                        signal_type=SignalType.EXIT_SHORT,
                        symbol=pos_id,
                        timestamp=timestamp,
                        reason=f"Stop loss: spot {current_spot:.0f} breached {breach_threshold:.0f}",
                        metadata={
                            "exit_type": "stop_loss",
                            "profit_pct": profit_pct,
                            "current_value": ratio.get_current_value(),
                            "breach_level": breach_threshold,
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
        Calculate position size for a ratio spread trade.
        
        Position sizing based on:
        - Maximum risk per trade (% of capital)
        - Conservative sizing due to unlimited risk on one side
        - Lot size of underlying
        
        Args:
            capital: Available capital
            price: Not used for ratio spreads (use metadata from signal)
            signal: Trading signal with metadata
        
        Returns:
            Number of ratio spreads (lots) to trade
        """
        if signal.metadata.get("strategy") != "ratio_spread":
            return 0
        
        underlying = signal.metadata.get("underlying", "NIFTY")
        lot_size = self.config["lot_sizes"].get(underlying, 50)
        
        # Get spread parameters
        long_strike = signal.metadata.get("long_strike", 0)
        short_strike = signal.metadata.get("short_strike", 0)
        net_credit_debit = signal.metadata.get("net_credit_debit", 0)
        
        if long_strike == 0 or short_strike == 0:
            return 0
        
        # Maximum risk per trade
        max_risk = capital * self.config["position_size_pct"]
        
        # Estimate risk: For ratio spreads, risk is typically the spread width
        # times the extra sold options minus the credit received
        spread_width = abs(long_strike - short_strike)
        extra_short_qty = self.config["ratio"][1] - self.config["ratio"][0]
        estimated_risk = spread_width * extra_short_qty * lot_size
        
        if estimated_risk <= 0:
            return 1
        
        # Calculate number of ratio spreads
        num_spreads = int(max_risk / estimated_risk)
        
        # Cap at max_positions due to high risk nature of ratio spreads
        max_positions = self.config.get("max_positions", 2)
        return max(1, min(num_spreads, max_positions))
    
    def open_ratio_spread(
        self,
        signal: Signal,
        quantity: int
    ) -> RatioSpreadPosition:
        """
        Open a new ratio spread position.
        
        Args:
            signal: Entry signal with ratio spread details
            quantity: Number of ratio spreads to open
        
        Returns:
            RatioSpreadPosition object
        """
        metadata = signal.metadata
        
        ratio = RatioSpreadPosition(
            underlying=metadata["underlying"],
            expiry=metadata["expiry"],
            spread_type=metadata["spread_type"],
            long_strike=metadata["long_strike"],
            short_strike=metadata["short_strike"],
            long_quantity=metadata["long_quantity"],
            short_quantity=metadata["short_quantity"],
            long_premium=metadata["long_premium"],
            short_premium=metadata["short_premium"],
            net_credit_debit=metadata["net_credit_debit"],
            entry_date=signal.timestamp,
            quantity=quantity,
            long_current_price=metadata["long_premium"],
            short_current_price=metadata["short_premium"],
            entry_iv_rank=metadata.get("iv_rank", 0),
            entry_spot=metadata["spot_price"],
            metadata=metadata
        )
        
        # Generate unique position ID
        pos_id = (
            f"{metadata['underlying']}_{metadata['expiry'].strftime('%Y%m%d')}_"
            f"{metadata['spread_type']}_{metadata['long_strike']}_{metadata['short_strike']}"
        )
        self.ratio_positions[pos_id] = ratio
        
        credit_debit_str = "Credit" if metadata["net_credit_debit"] > 0 else "Debit"
        logger.info(
            f"Opened Ratio Spread: {pos_id}, "
            f"Type={metadata['spread_type']}, "
            f"Long={metadata['long_strike']}x{metadata['long_quantity']} @ {metadata['long_premium']:.2f}, "
            f"Short={metadata['short_strike']}x{metadata['short_quantity']} @ {metadata['short_premium']:.2f}, "
            f"Net {credit_debit_str}={abs(metadata['net_credit_debit']):.2f}"
        )
        
        return ratio
    
    def close_ratio_spread(
        self,
        pos_id: str,
        signal: Signal
    ) -> Trade:
        """
        Close a ratio spread position.
        
        Args:
            pos_id: Position identifier
            signal: Exit signal
        
        Returns:
            Trade object representing the closed position
        """
        ratio = self.ratio_positions[pos_id]
        
        # Calculate PnL
        initial_value = -ratio.net_credit_debit * ratio.quantity
        exit_value = ratio.get_current_value()
        pnl = exit_value - initial_value
        
        lot_size = self.config["lot_sizes"].get(ratio.underlying, 50)
        
        # Determine direction based on spread type
        direction = "LONG" if ratio.spread_type == "PUT_RATIO" else "SHORT"
        
        trade = Trade(
            symbol=pos_id,
            direction=direction,
            quantity=ratio.quantity * lot_size,
            entry_price=abs(ratio.net_credit_debit),
            exit_price=abs(exit_value / ratio.quantity) if ratio.quantity > 0 else 0,
            entry_date=ratio.entry_date,
            exit_date=signal.timestamp,
            pnl=pnl * lot_size,  # Scale by lot size
            exit_reason=signal.reason,
            metadata={
                "strategy": "ratio_spread",
                "spread_type": ratio.spread_type,
                "long_strike": ratio.long_strike,
                "short_strike": ratio.short_strike,
                "ratio": f"{ratio.long_quantity}:{ratio.short_quantity}",
                "entry_iv_rank": ratio.entry_iv_rank,
                "exit_type": signal.metadata.get("exit_type", "unknown"),
            }
        )
        
        # Calculate return percentage
        max_profit = ratio.get_max_profit_at_short_strike()
        trade.return_pct = pnl / max_profit if max_profit > 0 else 0
        
        self.trades.append(trade)
        del self.ratio_positions[pos_id]
        
        logger.info(
            f"Closed Ratio Spread: {pos_id}, "
            f"PnL={pnl:.2f}, Return={trade.return_pct:.2%}, "
            f"Reason={signal.reason}"
        )
        
        return trade
    
    def should_exit(
        self,
        position: RatioSpreadPosition,
        current_spot: float,
        current_timestamp: datetime
    ) -> Tuple[bool, str]:
        """
        Determine if a ratio spread position should be exited.
        
        Args:
            position: The ratio spread position to check
            current_spot: Current spot price
            current_timestamp: Current timestamp
        
        Returns:
            Tuple of (should_exit, reason)
        """
        # Time-based exit
        days_to_expiry = (position.expiry - pd.to_datetime(current_timestamp)).days
        if days_to_expiry <= self.config["days_before_expiry_exit"]:
            return True, f"Time exit: {days_to_expiry} days to expiry"
        
        # Profit target
        profit_pct = position.get_profit_percentage()
        if profit_pct >= self.config["profit_target_pct"]:
            return True, f"Profit target reached: {profit_pct:.1%}"
        
        # Stop loss - short strike breach
        if position.spread_type == "PUT_RATIO":
            breach_threshold = position.short_strike * (1 - self.config["stop_loss_breach_pct"])
            if current_spot <= breach_threshold:
                return True, f"Short put strike breached: spot {current_spot:.0f} <= {breach_threshold:.0f}"
        else:
            breach_threshold = position.short_strike * (1 + self.config["stop_loss_breach_pct"])
            if current_spot >= breach_threshold:
                return True, f"Short call strike breached: spot {current_spot:.0f} >= {breach_threshold:.0f}"
        
        return False, ""
    
    def get_strategy_statistics(self) -> Dict[str, Any]:
        """
        Get detailed strategy statistics.
        
        Returns:
            Dictionary with strategy-specific statistics
        """
        base_stats = self.get_trade_statistics()
        
        # Add ratio spread-specific stats
        if self.trades:
            exit_types = {}
            spread_types = {}
            for trade in self.trades:
                exit_type = trade.metadata.get("exit_type", "unknown")
                exit_types[exit_type] = exit_types.get(exit_type, 0) + 1
                
                spread_type = trade.metadata.get("spread_type", "unknown")
                spread_types[spread_type] = spread_types.get(spread_type, 0) + 1
            
            base_stats["exit_type_breakdown"] = exit_types
            base_stats["spread_type_breakdown"] = spread_types
            base_stats["avg_holding_period"] = sum(t.holding_period for t in self.trades) / len(self.trades)
        
        base_stats["open_positions"] = len(self.ratio_positions)
        base_stats["config"] = self.config
        
        return base_stats
    
    def reset(self) -> None:
        """Reset strategy state."""
        super().reset()
        self.ratio_positions.clear()
        self.iv_rank_history = pd.Series(dtype=float)
