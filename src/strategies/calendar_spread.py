"""
Calendar Spread Strategy Module

Implements a Calendar Spread (Time Spread) options strategy.

Strategy Overview:
A Calendar Spread involves selling a near-term option and buying a 
longer-term option at the same strike. It profits from faster time decay
in the near-term option and from volatility expansion.

Structure:
- Sell near-term option (7-14 days to expiry)
- Buy far-term option (30-45 days to expiry)
- Same strike price (typically ATM)

Entry Conditions:
- IV Rank < 30 (low IV environment, expecting expansion)
- ATM strike selection
- Near expiry: 7-14 days
- Far expiry: 30-45 days

Exit Conditions:
- Profit target: 25-50% of debit paid
- Stop loss: 50% of debit paid
- Time exit: Close when near-term has 2-3 days left

Risk Management:
- Max loss is limited to debit paid
- Position size based on max loss

Mathematical Concepts:
- Profit = Far Option Value - Near Option Value - Initial Debit
- Max Loss = Initial Debit Paid
- Best case: Near option expires worthless, far option retains value
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

logger = logging.getLogger(__name__)


@dataclass
class CalendarPosition:
    """Data class representing a Calendar Spread position."""
    underlying: str
    strike: float
    near_expiry: datetime
    far_expiry: datetime
    option_type: str  # CE or PE
    near_premium_sold: float
    far_premium_paid: float
    net_debit: float
    entry_date: datetime
    quantity: int = 1
    near_current_price: float = 0.0
    far_current_price: float = 0.0
    entry_iv_rank: float = 0.0
    entry_spot: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_current_value(self) -> float:
        """Calculate current spread value."""
        return (self.far_current_price - self.near_current_price) * self.quantity
    
    def get_unrealized_pnl(self) -> float:
        """Calculate unrealized P&L."""
        return self.get_current_value() - (self.net_debit * self.quantity)
    
    def get_profit_percentage(self) -> float:
        """Calculate profit as percentage of debit paid."""
        if self.net_debit > 0:
            return self.get_unrealized_pnl() / (self.net_debit * self.quantity)
        return 0.0


class CalendarSpreadStrategy(BaseStrategy):
    """Calendar Spread Strategy for low IV environments."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Calendar Spread Strategy."""
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
            "lot_sizes": {"NIFTY": 50, "BANKNIFTY": 15, "SENSEX": 10},
            "max_positions": 3,
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(name="CalendarSpreadStrategy", config=default_config)
        
        self.calendar_positions: Dict[str, CalendarPosition] = {}
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
        """Generate trading signal."""
        current_data = data[data["date"] == timestamp]
        if current_data.empty:
            return None
        
        exit_signal = self._check_exit_conditions(current_data, timestamp)
        if exit_signal:
            return exit_signal
        
        if len(self.calendar_positions) >= self.config["max_positions"]:
            return None
        
        current_iv_rank = self._get_current_iv_rank(data, timestamp)
        if current_iv_rank is None:
            return None
        
        if self.config["iv_rank_entry_below"]:
            if current_iv_rank >= self.config["iv_rank_entry_threshold"]:
                return None
        else:
            if current_iv_rank < self.config["iv_rank_entry_threshold"]:
                return None
        
        entry_setup = self._find_entry_setup(current_data, timestamp)
        if entry_setup is None:
            return None
        
        underlying = current_data["underlying"].iloc[0]
        
        return Signal(
            signal_type=SignalType.ENTRY_LONG,
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
        """Get current IV Rank."""
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
        """Find suitable calendar spread entry setup."""
        spot_price = current_data["spot_price"].iloc[0]
        underlying = current_data["underlying"].iloc[0]
        
        near_min, near_max = self.config["near_expiry_days_range"]
        far_min, far_max = self.config["far_expiry_days_range"]
        
        expiries = sorted(pd.to_datetime(current_data["expiry"]).unique())
        
        near_expiry = None
        far_expiry = None
        
        for expiry in expiries:
            dte = (expiry - pd.to_datetime(timestamp)).days
            if near_min <= dte <= near_max and near_expiry is None:
                near_expiry = expiry
            if far_min <= dte <= far_max and far_expiry is None:
                far_expiry = expiry
        
        if near_expiry is None or far_expiry is None:
            return None
        
        near_data = current_data[pd.to_datetime(current_data["expiry"]) == near_expiry]
        far_data = current_data[pd.to_datetime(current_data["expiry"]) == far_expiry]
        
        near_calls = near_data[near_data["option_type"] == "CE"]
        far_calls = far_data[far_data["option_type"] == "CE"]
        
        if near_calls.empty or far_calls.empty:
            return None
        
        near_calls = near_calls.copy()
        near_calls.loc[:, "distance"] = abs(near_calls["strike"] - spot_price)
        atm_strike = near_calls.loc[near_calls["distance"].idxmin(), "strike"]
        
        near_option = near_calls[near_calls["strike"] == atm_strike]
        far_option = far_calls[far_calls["strike"] == atm_strike]
        
        if near_option.empty or far_option.empty:
            return None
        
        near_premium = near_option["ltp"].iloc[0]
        far_premium = far_option["ltp"].iloc[0]
        net_debit = far_premium - near_premium
        
        if net_debit <= 0:
            return None
        
        return {
            "underlying": underlying,
            "strike": atm_strike,
            "near_expiry": near_expiry,
            "far_expiry": far_expiry,
            "option_type": "CE",
            "near_premium_sold": near_premium,
            "far_premium_paid": far_premium,
            "net_debit": net_debit,
            "spot_price": spot_price,
            "near_dte": (near_expiry - pd.to_datetime(timestamp)).days,
            "far_dte": (far_expiry - pd.to_datetime(timestamp)).days,
        }
    
    def _check_exit_conditions(
        self,
        current_data: pd.DataFrame,
        timestamp: datetime
    ) -> Optional[Signal]:
        """Check exit conditions for calendar positions."""
        for pos_id, cal in list(self.calendar_positions.items()):
            near_data = current_data[
                (current_data["strike"] == cal.strike) &
                (current_data["option_type"] == cal.option_type) &
                (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(cal.near_expiry))
            ]
            far_data = current_data[
                (current_data["strike"] == cal.strike) &
                (current_data["option_type"] == cal.option_type) &
                (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(cal.far_expiry))
            ]
            
            if near_data.empty or far_data.empty:
                continue
            
            cal.near_current_price = near_data["ltp"].iloc[0]
            cal.far_current_price = far_data["ltp"].iloc[0]
            
            profit_pct = cal.get_profit_percentage()
            
            days_to_near_expiry = (cal.near_expiry - pd.to_datetime(timestamp)).days
            if days_to_near_expiry <= self.config["days_before_near_expiry_exit"]:
                return Signal(
                    signal_type=SignalType.EXIT_LONG,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Time exit: {days_to_near_expiry} days to near expiry",
                    metadata={"exit_type": "time", "profit_pct": profit_pct}
                )
            
            if profit_pct >= self.config["profit_target_pct"]:
                return Signal(
                    signal_type=SignalType.EXIT_LONG,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Profit target: {profit_pct:.1%}",
                    metadata={"exit_type": "profit_target", "profit_pct": profit_pct}
                )
            
            if profit_pct <= -self.config["stop_loss_pct"]:
                return Signal(
                    signal_type=SignalType.EXIT_LONG,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Stop loss: {profit_pct:.1%}",
                    metadata={"exit_type": "stop_loss", "profit_pct": profit_pct}
                )
        
        return None
    
    def calculate_position_size(
        self,
        capital: float,
        price: float,
        signal: Signal
    ) -> int:
        """Calculate position size for calendar spread."""
        if signal.metadata.get("strategy") != "calendar_spread":
            return 0
        
        underlying = signal.metadata.get("underlying", "NIFTY")
        lot_size = self.config["lot_sizes"].get(underlying, 50)
        net_debit = signal.metadata.get("net_debit", 0)
        
        if net_debit <= 0:
            return 0
        
        max_risk = capital * self.config["position_size_pct"]
        cost_per_calendar = net_debit * lot_size
        
        num_calendars = int(max_risk / cost_per_calendar)
        return max(1, num_calendars)
    
    def open_calendar(
        self,
        signal: Signal,
        quantity: int
    ) -> CalendarPosition:
        """Open a new calendar spread position."""
        metadata = signal.metadata
        
        cal = CalendarPosition(
            underlying=metadata["underlying"],
            strike=metadata["strike"],
            near_expiry=metadata["near_expiry"],
            far_expiry=metadata["far_expiry"],
            option_type=metadata["option_type"],
            near_premium_sold=metadata["near_premium_sold"],
            far_premium_paid=metadata["far_premium_paid"],
            net_debit=metadata["net_debit"],
            entry_date=signal.timestamp,
            quantity=quantity,
            near_current_price=metadata["near_premium_sold"],
            far_current_price=metadata["far_premium_paid"],
            entry_iv_rank=metadata.get("iv_rank", 0),
            entry_spot=metadata["spot_price"],
            metadata=metadata
        )
        
        pos_id = (
            f"{metadata['underlying']}_{metadata['strike']}_{metadata['option_type']}_"
            f"CAL_{metadata['near_expiry'].strftime('%Y%m%d')}_{metadata['far_expiry'].strftime('%Y%m%d')}"
        )
        self.calendar_positions[pos_id] = cal
        
        logger.info(
            f"Opened Calendar: {pos_id}, Strike={metadata['strike']}, "
            f"Net Debit={metadata['net_debit']:.2f}"
        )
        
        return cal
    
    def close_calendar(
        self,
        pos_id: str,
        signal: Signal
    ) -> Trade:
        """Close a calendar spread position."""
        cal = self.calendar_positions[pos_id]
        
        initial_debit = cal.net_debit * cal.quantity
        exit_value = cal.get_current_value()
        pnl = exit_value - initial_debit
        
        lot_size = self.config["lot_sizes"].get(cal.underlying, 50)
        
        trade = Trade(
            symbol=pos_id,
            direction="LONG",
            quantity=cal.quantity * lot_size,
            entry_price=cal.net_debit,
            exit_price=cal.get_current_value() / cal.quantity if cal.quantity > 0 else 0,
            entry_date=cal.entry_date,
            exit_date=signal.timestamp,
            pnl=pnl * lot_size,
            exit_reason=signal.reason,
            metadata={
                "strategy": "calendar_spread",
                "strike": cal.strike,
                "option_type": cal.option_type,
                "entry_iv_rank": cal.entry_iv_rank,
            }
        )
        
        trade.return_pct = pnl / initial_debit if initial_debit > 0 else 0
        
        self.trades.append(trade)
        del self.calendar_positions[pos_id]
        
        logger.info(
            f"Closed Calendar: {pos_id}, PnL={pnl:.2f}, "
            f"Return={trade.return_pct:.2%}"
        )
        
        return trade
    
    def reset(self) -> None:
        """Reset strategy state."""
        super().reset()
        self.calendar_positions.clear()
        self.iv_rank_history = pd.Series(dtype=float)
