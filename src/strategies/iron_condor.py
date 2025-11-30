"""
Iron Condor Strategy Module

Implements an Iron Condor options strategy for neutral market conditions.

Strategy Overview:
An Iron Condor is a neutral options strategy combining a bull put spread 
and bear call spread. It profits from time decay when the underlying 
stays within a defined range.

Structure:
- Sell OTM Put (lower strike)
- Buy further OTM Put (lowest strike) - protection
- Sell OTM Call (higher strike)
- Buy further OTM Call (highest strike) - protection

Entry Conditions:
- IV Rank > 50 (moderate to high IV environment)
- Select short strikes at 15-20 delta
- Wing width: 50-100 points for NIFTY, 100-200 for BANKNIFTY
- Minimum 14 days to expiry, maximum 45 days

Exit Conditions:
- Profit target: 50% of max profit (credit received)
- Stop loss: 200% of credit received (or when short strike is breached)
- Time exit: Close 5-7 days before expiry
- Adjustment: Roll untested side if one side is breached

Risk Management:
- Max loss is defined (wing width - credit received)
- Position size based on max loss, not margin

Mathematical Formulas:
- Max Profit = Net Credit Received
- Max Loss = Wing Width - Net Credit
- Breakeven Upper = Short Call Strike + Net Credit
- Breakeven Lower = Short Put Strike - Net Credit

Note: Iron Condors have defined risk but limited profit potential.
Best suited for range-bound markets with elevated implied volatility.
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
class IronCondorPosition:
    """
    Data class representing an Iron Condor position.
    
    An Iron Condor consists of:
    - Long Put (lowest strike) - protection
    - Short Put (lower strike)
    - Short Call (upper strike)
    - Long Call (highest strike) - protection
    """
    underlying: str
    expiry: datetime
    long_put_strike: float
    short_put_strike: float
    short_call_strike: float
    long_call_strike: float
    long_put_premium: float
    short_put_premium: float
    short_call_premium: float
    long_call_premium: float
    net_credit: float
    entry_date: datetime
    quantity: int = 1
    long_put_current_price: float = 0.0
    short_put_current_price: float = 0.0
    short_call_current_price: float = 0.0
    long_call_current_price: float = 0.0
    entry_iv_rank: float = 0.0
    entry_spot: float = 0.0
    wing_width: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_current_cost_to_close(self) -> float:
        """Calculate current cost to close the position."""
        cost = (
            self.short_put_current_price + 
            self.short_call_current_price - 
            self.long_put_current_price - 
            self.long_call_current_price
        )
        return cost * self.quantity
    
    def get_unrealized_pnl(self) -> float:
        """Calculate unrealized P&L."""
        return (self.net_credit * self.quantity) - self.get_current_cost_to_close()
    
    def get_profit_percentage(self) -> float:
        """Calculate profit as percentage of credit received."""
        if self.net_credit > 0:
            return self.get_unrealized_pnl() / (self.net_credit * self.quantity)
        return 0.0
    
    def get_max_profit(self) -> float:
        """Calculate maximum profit (net credit received)."""
        return self.net_credit * self.quantity
    
    def get_max_loss(self) -> float:
        """Calculate maximum loss (wing width - net credit)."""
        return (self.wing_width - self.net_credit) * self.quantity
    
    def get_breakeven_upper(self) -> float:
        """Calculate upper breakeven point."""
        return self.short_call_strike + self.net_credit
    
    def get_breakeven_lower(self) -> float:
        """Calculate lower breakeven point."""
        return self.short_put_strike - self.net_credit


class IronCondorStrategy(BaseStrategy):
    """
    Iron Condor Strategy for neutral market conditions.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Iron Condor Strategy."""
        default_config = {
            "iv_rank_entry_threshold": 50,
            "short_delta_range": (0.15, 0.20),
            "wing_width": {"NIFTY": 50, "BANKNIFTY": 100, "SENSEX": 100},
            "profit_target_pct": 0.50,
            "stop_loss_pct": 2.00,
            "days_before_expiry_exit": 7,
            "position_size_pct": 0.02,
            "min_days_to_expiry": 14,
            "max_days_to_expiry": 45,
            "max_positions": 3,
            "lot_sizes": {"NIFTY": 50, "BANKNIFTY": 15, "SENSEX": 10},
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(name="IronCondorStrategy", config=default_config)
        
        self.iron_condor_positions: Dict[str, IronCondorPosition] = {}
        self.iv_rank_history: pd.Series = pd.Series(dtype=float)
        self._iv_calculator = None
    
    def initialize(self, data: pd.DataFrame) -> None:
        """Initialize strategy with historical data."""
        super().initialize(data)
        
        from ..indicators.volatility import IVRankCalculator
        self._iv_calculator = IVRankCalculator()
        
        if "iv" in data.columns:
            iv_series = self._extract_atm_iv_series(data)
            if len(iv_series) > 0:
                self.iv_rank_history = self._iv_calculator.calculate_iv_rank(
                    iv_series, lookback_days=252
                )
        
        logger.info(f"Strategy initialized with {len(self.iv_rank_history)} IV Rank values")
    
    def _extract_atm_iv_series(self, data: pd.DataFrame) -> pd.Series:
        """Extract ATM IV time series from options data."""
        iv_values = []
        
        for date in data["date"].unique():
            date_data = data[data["date"] == date]
            if date_data.empty:
                continue
            
            spot = date_data["spot_price"].iloc[0]
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
        """Generate trading signal based on market data and IV Rank."""
        current_data = data[data["date"] == timestamp]
        if current_data.empty:
            return None
        
        exit_signal = self._check_exit_conditions(current_data, timestamp)
        if exit_signal:
            return exit_signal
        
        if len(self.iron_condor_positions) >= self.config["max_positions"]:
            return None
        
        current_iv_rank = self._get_current_iv_rank(data, timestamp)
        if current_iv_rank is None:
            return None
        
        if current_iv_rank < self.config["iv_rank_entry_threshold"]:
            return None
        
        underlying = current_data["underlying"].iloc[0]
        entry_setup = self._find_entry_setup(current_data, timestamp)
        
        if entry_setup is None:
            return None
        
        return Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol=f"{underlying}_IRON_CONDOR",
            timestamp=timestamp,
            reason=f"IV Rank {current_iv_rank:.1f} > {self.config['iv_rank_entry_threshold']}",
            metadata={
                "strategy": "iron_condor",
                "iv_rank": current_iv_rank,
                **entry_setup
            }
        )
    
    def _get_current_iv_rank(
        self,
        data: pd.DataFrame,
        timestamp: datetime
    ) -> Optional[float]:
        """Get current IV Rank from pre-computed history or calculate."""
        ts = pd.to_datetime(timestamp)
        
        if len(self.iv_rank_history) > 0 and ts in self.iv_rank_history.index:
            return self.iv_rank_history[ts]
        
        iv_series = self._extract_atm_iv_series(data[data["date"] <= timestamp])
        
        if len(iv_series) < 30:
            return None
        
        iv_rank = self._iv_calculator.calculate_iv_rank(iv_series)
        return iv_rank.iloc[-1] if len(iv_rank) > 0 else None
    
    def _find_entry_setup(
        self,
        current_data: pd.DataFrame,
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Find suitable iron condor entry setup."""
        spot_price = current_data["spot_price"].iloc[0]
        underlying = current_data["underlying"].iloc[0]
        
        delta_low, delta_high = self.config["short_delta_range"]
        wing_width = self.config["wing_width"].get(underlying, 100)
        
        expiries = pd.to_datetime(current_data["expiry"]).unique()
        
        for expiry in sorted(expiries):
            dte = (expiry - pd.to_datetime(timestamp)).days
            
            if dte < self.config["min_days_to_expiry"]:
                continue
            if dte > self.config["max_days_to_expiry"]:
                continue
            
            expiry_data = current_data[pd.to_datetime(current_data["expiry"]) == expiry]
            
            calls = expiry_data[expiry_data["option_type"] == "CE"].copy()
            puts = expiry_data[expiry_data["option_type"] == "PE"].copy()
            
            if calls.empty or puts.empty:
                continue
            
            otm_calls = calls[
                (calls["strike"] > spot_price) &
                (calls["delta"] >= delta_low) &
                (calls["delta"] <= delta_high)
            ]
            
            otm_puts = puts[
                (puts["strike"] < spot_price) &
                (puts["delta"] <= -delta_low) &
                (puts["delta"] >= -delta_high)
            ]
            
            if otm_calls.empty or otm_puts.empty:
                otm_calls = calls[calls["strike"] > spot_price]
                otm_puts = puts[puts["strike"] < spot_price]
                
                if otm_calls.empty or otm_puts.empty:
                    continue
                
                target_delta = (delta_low + delta_high) / 2
                otm_calls = otm_calls.copy()
                otm_calls.loc[:, "delta_dist"] = abs(otm_calls["delta"] - target_delta)
                otm_puts = otm_puts.copy()
                otm_puts.loc[:, "delta_dist"] = abs(abs(otm_puts["delta"]) - target_delta)
                
                otm_calls = otm_calls.nsmallest(1, "delta_dist")
                otm_puts = otm_puts.nsmallest(1, "delta_dist")
            else:
                target_delta = (delta_low + delta_high) / 2
                otm_calls = otm_calls.copy()
                otm_calls.loc[:, "delta_dist"] = abs(otm_calls["delta"] - target_delta)
                otm_puts = otm_puts.copy()
                otm_puts.loc[:, "delta_dist"] = abs(abs(otm_puts["delta"]) - target_delta)
                
                otm_calls = otm_calls.nsmallest(1, "delta_dist")
                otm_puts = otm_puts.nsmallest(1, "delta_dist")
            
            short_call = otm_calls.iloc[0]
            short_put = otm_puts.iloc[0]
            
            long_call_strike = short_call["strike"] + wing_width
            long_put_strike = short_put["strike"] - wing_width
            
            long_call_data = calls[calls["strike"] == long_call_strike]
            long_put_data = puts[puts["strike"] == long_put_strike]
            
            if long_call_data.empty:
                calls_above = calls[calls["strike"] > short_call["strike"]]
                if calls_above.empty:
                    continue
                long_call_data = calls_above.nsmallest(1, "strike")
                long_call_strike = long_call_data.iloc[0]["strike"]
            
            if long_put_data.empty:
                puts_below = puts[puts["strike"] < short_put["strike"]]
                if puts_below.empty:
                    continue
                long_put_data = puts_below.nlargest(1, "strike")
                long_put_strike = long_put_data.iloc[0]["strike"]
            
            long_call = long_call_data.iloc[0]
            long_put = long_put_data.iloc[0]
            
            net_credit = (
                short_call["ltp"] + short_put["ltp"] - 
                long_call["ltp"] - long_put["ltp"]
            )
            
            if net_credit <= 0:
                continue
            
            actual_wing_width = min(
                long_call_strike - short_call["strike"],
                short_put["strike"] - long_put_strike
            )
            
            return {
                "underlying": underlying,
                "expiry": expiry,
                "dte": dte,
                "spot_price": spot_price,
                "long_put_strike": long_put_strike,
                "short_put_strike": short_put["strike"],
                "short_call_strike": short_call["strike"],
                "long_call_strike": long_call_strike,
                "long_put_premium": long_put["ltp"],
                "short_put_premium": short_put["ltp"],
                "short_call_premium": short_call["ltp"],
                "long_call_premium": long_call["ltp"],
                "net_credit": net_credit,
                "wing_width": actual_wing_width,
                "short_call_delta": short_call["delta"],
                "short_put_delta": short_put["delta"],
            }
        
        return None
    
    def _check_exit_conditions(
        self,
        current_data: pd.DataFrame,
        timestamp: datetime
    ) -> Optional[Signal]:
        """Check exit conditions for all open iron condor positions."""
        for pos_id, ic in list(self.iron_condor_positions.items()):
            long_put_data = current_data[
                (current_data["strike"] == ic.long_put_strike) &
                (current_data["option_type"] == "PE") &
                (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(ic.expiry))
            ]
            short_put_data = current_data[
                (current_data["strike"] == ic.short_put_strike) &
                (current_data["option_type"] == "PE") &
                (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(ic.expiry))
            ]
            short_call_data = current_data[
                (current_data["strike"] == ic.short_call_strike) &
                (current_data["option_type"] == "CE") &
                (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(ic.expiry))
            ]
            long_call_data = current_data[
                (current_data["strike"] == ic.long_call_strike) &
                (current_data["option_type"] == "CE") &
                (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(ic.expiry))
            ]
            
            if long_put_data.empty or short_put_data.empty or short_call_data.empty or long_call_data.empty:
                continue
            
            ic.long_put_current_price = long_put_data["ltp"].iloc[0]
            ic.short_put_current_price = short_put_data["ltp"].iloc[0]
            ic.short_call_current_price = short_call_data["ltp"].iloc[0]
            ic.long_call_current_price = long_call_data["ltp"].iloc[0]
            
            profit_pct = ic.get_profit_percentage()
            
            days_to_expiry = (ic.expiry - pd.to_datetime(timestamp)).days
            if days_to_expiry <= self.config["days_before_expiry_exit"]:
                return Signal(
                    signal_type=SignalType.EXIT_SHORT,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Time exit: {days_to_expiry} days to expiry",
                    metadata={
                        "exit_type": "time",
                        "profit_pct": profit_pct,
                        "current_value": ic.get_current_cost_to_close(),
                        "initial_credit": ic.net_credit,
                    }
                )
            
            if profit_pct >= self.config["profit_target_pct"]:
                return Signal(
                    signal_type=SignalType.EXIT_SHORT,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Profit target: {profit_pct:.1%} >= {self.config['profit_target_pct']:.1%}",
                    metadata={
                        "exit_type": "profit_target",
                        "profit_pct": profit_pct,
                        "current_value": ic.get_current_cost_to_close(),
                        "initial_credit": ic.net_credit,
                    }
                )
            
            if profit_pct <= -self.config["stop_loss_pct"]:
                return Signal(
                    signal_type=SignalType.EXIT_SHORT,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Stop loss: {profit_pct:.1%} <= -{self.config['stop_loss_pct']:.1%}",
                    metadata={
                        "exit_type": "stop_loss",
                        "profit_pct": profit_pct,
                        "current_value": ic.get_current_cost_to_close(),
                        "initial_credit": ic.net_credit,
                    }
                )
        
        return None
    
    def calculate_position_size(
        self,
        capital: float,
        price: float,
        signal: Signal
    ) -> int:
        """Calculate position size for an iron condor trade."""
        if signal.metadata.get("strategy") != "iron_condor":
            return 0
        
        underlying = signal.metadata.get("underlying", "NIFTY")
        lot_size = self.config["lot_sizes"].get(underlying, 50)
        net_credit = signal.metadata.get("net_credit", 0)
        wing_width = signal.metadata.get("wing_width", 100)
        
        if net_credit <= 0 or wing_width <= 0:
            return 0
        
        max_risk = capital * self.config["position_size_pct"]
        max_loss_per_ic = (wing_width - net_credit) * lot_size
        
        if max_loss_per_ic <= 0:
            return 1
        
        num_ics = int(max_risk / max_loss_per_ic)
        return max(1, num_ics)
    
    def open_iron_condor(
        self,
        signal: Signal,
        quantity: int
    ) -> IronCondorPosition:
        """Open a new iron condor position."""
        metadata = signal.metadata
        
        ic = IronCondorPosition(
            underlying=metadata["underlying"],
            expiry=metadata["expiry"],
            long_put_strike=metadata["long_put_strike"],
            short_put_strike=metadata["short_put_strike"],
            short_call_strike=metadata["short_call_strike"],
            long_call_strike=metadata["long_call_strike"],
            long_put_premium=metadata["long_put_premium"],
            short_put_premium=metadata["short_put_premium"],
            short_call_premium=metadata["short_call_premium"],
            long_call_premium=metadata["long_call_premium"],
            net_credit=metadata["net_credit"],
            entry_date=signal.timestamp,
            quantity=quantity,
            long_put_current_price=metadata["long_put_premium"],
            short_put_current_price=metadata["short_put_premium"],
            short_call_current_price=metadata["short_call_premium"],
            long_call_current_price=metadata["long_call_premium"],
            entry_iv_rank=metadata.get("iv_rank", 0),
            entry_spot=metadata["spot_price"],
            wing_width=metadata["wing_width"],
            metadata=metadata
        )
        
        pos_id = (
            f"{metadata['underlying']}_{metadata['expiry'].strftime('%Y%m%d')}_"
            f"IC_{metadata['short_put_strike']}_{metadata['short_call_strike']}"
        )
        self.iron_condor_positions[pos_id] = ic
        
        logger.info(
            f"Opened Iron Condor: {pos_id}, "
            f"Put Spread={metadata['long_put_strike']}/{metadata['short_put_strike']}, "
            f"Call Spread={metadata['short_call_strike']}/{metadata['long_call_strike']}, "
            f"Net Credit={metadata['net_credit']:.2f}"
        )
        
        return ic
    
    def close_iron_condor(
        self,
        pos_id: str,
        signal: Signal
    ) -> Trade:
        """Close an iron condor position."""
        ic = self.iron_condor_positions[pos_id]
        
        initial_credit = ic.net_credit * ic.quantity
        exit_cost = ic.get_current_cost_to_close()
        pnl = initial_credit - exit_cost
        
        lot_size = self.config["lot_sizes"].get(ic.underlying, 50)
        
        trade = Trade(
            symbol=pos_id,
            direction="SHORT",
            quantity=ic.quantity * lot_size,
            entry_price=ic.net_credit,
            exit_price=ic.get_current_cost_to_close() / ic.quantity if ic.quantity > 0 else 0,
            entry_date=ic.entry_date,
            exit_date=signal.timestamp,
            pnl=pnl * lot_size,
            exit_reason=signal.reason,
            metadata={
                "strategy": "iron_condor",
                "long_put_strike": ic.long_put_strike,
                "short_put_strike": ic.short_put_strike,
                "short_call_strike": ic.short_call_strike,
                "long_call_strike": ic.long_call_strike,
                "entry_iv_rank": ic.entry_iv_rank,
                "exit_type": signal.metadata.get("exit_type", "unknown"),
            }
        )
        
        trade.return_pct = pnl / initial_credit if initial_credit > 0 else 0
        
        self.trades.append(trade)
        del self.iron_condor_positions[pos_id]
        
        logger.info(
            f"Closed Iron Condor: {pos_id}, "
            f"PnL={pnl:.2f}, Return={trade.return_pct:.2%}, "
            f"Reason={signal.reason}"
        )
        
        return trade
    
    def should_exit(
        self,
        position: IronCondorPosition,
        current_spot: float,
        current_timestamp: datetime
    ) -> Tuple[bool, str]:
        """Determine if an iron condor position should be exited."""
        days_to_expiry = (position.expiry - pd.to_datetime(current_timestamp)).days
        if days_to_expiry <= self.config["days_before_expiry_exit"]:
            return True, f"Time exit: {days_to_expiry} days to expiry"
        
        profit_pct = position.get_profit_percentage()
        if profit_pct >= self.config["profit_target_pct"]:
            return True, f"Profit target reached: {profit_pct:.1%}"
        
        if profit_pct <= -self.config["stop_loss_pct"]:
            return True, f"Stop loss triggered: {profit_pct:.1%}"
        
        if current_spot >= position.short_call_strike:
            return True, f"Short call strike breached: spot {current_spot} >= {position.short_call_strike}"
        
        if current_spot <= position.short_put_strike:
            return True, f"Short put strike breached: spot {current_spot} <= {position.short_put_strike}"
        
        return False, ""
    
    def get_strategy_statistics(self) -> Dict[str, Any]:
        """Get detailed strategy statistics."""
        base_stats = self.get_trade_statistics()
        
        if self.trades:
            exit_types = {}
            for trade in self.trades:
                exit_type = trade.metadata.get("exit_type", "unknown")
                exit_types[exit_type] = exit_types.get(exit_type, 0) + 1
            
            base_stats["exit_type_breakdown"] = exit_types
            base_stats["avg_holding_period"] = sum(t.holding_period for t in self.trades) / len(self.trades)
        
        base_stats["open_positions"] = len(self.iron_condor_positions)
        base_stats["config"] = self.config
        
        return base_stats
    
    def reset(self) -> None:
        """Reset strategy state."""
        super().reset()
        self.iron_condor_positions.clear()
        self.iv_rank_history = pd.Series(dtype=float)
