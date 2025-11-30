"""
Ratio Spread Strategy Module

Implements a Ratio Spread options strategy for high IV environments.

Strategy Overview:
A Ratio Spread involves buying one option and selling multiple options
at a further OTM strike. It profits from time decay and mild directional
movement, but has unlimited risk on one side.

Structure (Call Ratio):
- Buy 1 ATM Call (0.50 delta)
- Sell 2 OTM Calls (0.20-0.25 delta each)

Entry Conditions:
- IV Rank > 60 (high IV environment)
- Neutral to slightly bullish outlook
- Minimum 21 days to expiry

Exit Conditions:
- Profit target: 75% of max profit
- Stop loss: Exit if underlying moves 2% beyond short strikes
- Time exit: Close 7 days before expiry

Risk Management:
- Unlimited risk if underlying moves strongly past short strikes
- Position size should be smaller due to unlimited risk
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
class RatioPosition:
    """Data class representing a Ratio Spread position."""
    underlying: str
    expiry: datetime
    long_strike: float
    short_strike: float
    option_type: str  # CE or PE
    ratio: Tuple[int, int]  # (buy, sell)
    long_premium: float
    short_premium: float
    net_credit_or_debit: float  # positive = credit, negative = debit
    entry_date: datetime
    quantity: int = 1
    long_current_price: float = 0.0
    short_current_price: float = 0.0
    entry_iv_rank: float = 0.0
    entry_spot: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_current_value(self) -> float:
        """Calculate current spread value."""
        long_qty, short_qty = self.ratio
        return (
            self.long_current_price * long_qty - 
            self.short_current_price * short_qty
        ) * self.quantity
    
    def get_unrealized_pnl(self) -> float:
        """Calculate unrealized P&L."""
        initial_cost = self.net_credit_or_debit * self.quantity
        return self.get_current_value() - initial_cost
    
    def get_profit_percentage(self) -> float:
        """Calculate profit as percentage of initial credit/debit."""
        if abs(self.net_credit_or_debit) > 0:
            return self.get_unrealized_pnl() / abs(self.net_credit_or_debit * self.quantity)
        return 0.0
    
    def is_breached(self, current_spot: float, breach_pct: float = 0.02) -> bool:
        """Check if short strike is breached beyond threshold."""
        if self.option_type == "CE":
            breach_level = self.short_strike * (1 + breach_pct)
            return current_spot > breach_level
        else:
            breach_level = self.short_strike * (1 - breach_pct)
            return current_spot < breach_level


class RatioSpreadStrategy(BaseStrategy):
    """Ratio Spread Strategy for high IV environments."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Ratio Spread Strategy."""
        default_config = {
            "iv_rank_entry_threshold": 60,
            "ratio": (1, 2),
            "long_delta": 0.50,
            "short_delta_range": (0.20, 0.25),
            "profit_target_pct": 0.75,
            "stop_loss_breach_pct": 0.02,
            "days_before_expiry_exit": 7,
            "position_size_pct": 0.01,
            "min_days_to_expiry": 21,
            "max_days_to_expiry": 45,
            "lot_sizes": {"NIFTY": 50, "BANKNIFTY": 15, "SENSEX": 10},
            "max_positions": 2,
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(name="RatioSpreadStrategy", config=default_config)
        
        self.ratio_positions: Dict[str, RatioPosition] = {}
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
        
        if len(self.ratio_positions) >= self.config["max_positions"]:
            return None
        
        current_iv_rank = self._get_current_iv_rank(data, timestamp)
        if current_iv_rank is None:
            return None
        
        if current_iv_rank < self.config["iv_rank_entry_threshold"]:
            return None
        
        entry_setup = self._find_entry_setup(current_data, timestamp)
        if entry_setup is None:
            return None
        
        underlying = current_data["underlying"].iloc[0]
        
        return Signal(
            signal_type=SignalType.ENTRY_SHORT,
            symbol=f"{underlying}_RATIO",
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
        """Find suitable ratio spread entry setup."""
        spot_price = current_data["spot_price"].iloc[0]
        underlying = current_data["underlying"].iloc[0]
        
        expiries = sorted(pd.to_datetime(current_data["expiry"]).unique())
        
        target_expiry = None
        for expiry in expiries:
            dte = (expiry - pd.to_datetime(timestamp)).days
            if self.config["min_days_to_expiry"] <= dte <= self.config["max_days_to_expiry"]:
                target_expiry = expiry
                break
        
        if target_expiry is None:
            return None
        
        expiry_data = current_data[pd.to_datetime(current_data["expiry"]) == target_expiry]
        calls = expiry_data[expiry_data["option_type"] == "CE"]
        
        if calls.empty:
            return None
        
        atm_calls = calls.copy()
        atm_calls.loc[:, "delta_dist"] = abs(atm_calls["delta"] - self.config["long_delta"])
        long_option = atm_calls.nsmallest(1, "delta_dist").iloc[0]
        
        delta_low, delta_high = self.config["short_delta_range"]
        otm_calls = calls[
            (calls["strike"] > long_option["strike"]) &
            (calls["delta"] >= delta_low) &
            (calls["delta"] <= delta_high)
        ]
        
        if otm_calls.empty:
            otm_calls = calls[calls["strike"] > long_option["strike"]]
            if otm_calls.empty:
                return None
            target_delta = (delta_low + delta_high) / 2
            otm_calls = otm_calls.copy()
            otm_calls.loc[:, "delta_dist"] = abs(otm_calls["delta"] - target_delta)
            otm_calls = otm_calls.nsmallest(1, "delta_dist")
        else:
            target_delta = (delta_low + delta_high) / 2
            otm_calls = otm_calls.copy()
            otm_calls.loc[:, "delta_dist"] = abs(otm_calls["delta"] - target_delta)
            otm_calls = otm_calls.nsmallest(1, "delta_dist")
        
        short_option = otm_calls.iloc[0]
        
        long_qty, short_qty = self.config["ratio"]
        long_premium = long_option["ltp"] * long_qty
        short_premium = short_option["ltp"] * short_qty
        
        net_credit_or_debit = short_premium - long_premium
        
        return {
            "underlying": underlying,
            "expiry": target_expiry,
            "dte": (target_expiry - pd.to_datetime(timestamp)).days,
            "long_strike": long_option["strike"],
            "short_strike": short_option["strike"],
            "option_type": "CE",
            "ratio": self.config["ratio"],
            "long_premium": long_option["ltp"],
            "short_premium": short_option["ltp"],
            "net_credit_or_debit": net_credit_or_debit,
            "spot_price": spot_price,
            "long_delta": long_option["delta"],
            "short_delta": short_option["delta"],
        }
    
    def _check_exit_conditions(
        self,
        current_data: pd.DataFrame,
        timestamp: datetime
    ) -> Optional[Signal]:
        """Check exit conditions for ratio positions."""
        for pos_id, ratio in list(self.ratio_positions.items()):
            long_data = current_data[
                (current_data["strike"] == ratio.long_strike) &
                (current_data["option_type"] == ratio.option_type) &
                (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(ratio.expiry))
            ]
            short_data = current_data[
                (current_data["strike"] == ratio.short_strike) &
                (current_data["option_type"] == ratio.option_type) &
                (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(ratio.expiry))
            ]
            
            if long_data.empty or short_data.empty:
                continue
            
            ratio.long_current_price = long_data["ltp"].iloc[0]
            ratio.short_current_price = short_data["ltp"].iloc[0]
            
            profit_pct = ratio.get_profit_percentage()
            
            current_spot = current_data["spot_price"].iloc[0]
            if ratio.is_breached(current_spot, self.config["stop_loss_breach_pct"]):
                return Signal(
                    signal_type=SignalType.EXIT_SHORT,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Short strike breached at spot {current_spot:.2f}",
                    metadata={"exit_type": "breach", "profit_pct": profit_pct}
                )
            
            days_to_expiry = (ratio.expiry - pd.to_datetime(timestamp)).days
            if days_to_expiry <= self.config["days_before_expiry_exit"]:
                return Signal(
                    signal_type=SignalType.EXIT_SHORT,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Time exit: {days_to_expiry} days to expiry",
                    metadata={"exit_type": "time", "profit_pct": profit_pct}
                )
            
            if profit_pct >= self.config["profit_target_pct"]:
                return Signal(
                    signal_type=SignalType.EXIT_SHORT,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason=f"Profit target: {profit_pct:.1%}",
                    metadata={"exit_type": "profit_target", "profit_pct": profit_pct}
                )
        
        return None
    
    def calculate_position_size(
        self,
        capital: float,
        price: float,
        signal: Signal
    ) -> int:
        """Calculate position size for ratio spread."""
        if signal.metadata.get("strategy") != "ratio_spread":
            return 0
        
        underlying = signal.metadata.get("underlying", "NIFTY")
        lot_size = self.config["lot_sizes"].get(underlying, 50)
        
        max_risk = capital * self.config["position_size_pct"]
        
        net = signal.metadata.get("net_credit_or_debit", 0)
        long_premium = signal.metadata.get("long_premium", 0)
        
        if net >= 0:
            estimated_max_loss = long_premium * lot_size * 2
        else:
            estimated_max_loss = abs(net) * lot_size * 3
        
        if estimated_max_loss <= 0:
            return 1
        
        num_ratios = int(max_risk / estimated_max_loss)
        return max(1, num_ratios)
    
    def open_ratio(
        self,
        signal: Signal,
        quantity: int
    ) -> RatioPosition:
        """Open a new ratio spread position."""
        metadata = signal.metadata
        
        ratio = RatioPosition(
            underlying=metadata["underlying"],
            expiry=metadata["expiry"],
            long_strike=metadata["long_strike"],
            short_strike=metadata["short_strike"],
            option_type=metadata["option_type"],
            ratio=metadata["ratio"],
            long_premium=metadata["long_premium"],
            short_premium=metadata["short_premium"],
            net_credit_or_debit=metadata["net_credit_or_debit"],
            entry_date=signal.timestamp,
            quantity=quantity,
            long_current_price=metadata["long_premium"],
            short_current_price=metadata["short_premium"],
            entry_iv_rank=metadata.get("iv_rank", 0),
            entry_spot=metadata["spot_price"],
            metadata=metadata
        )
        
        pos_id = (
            f"{metadata['underlying']}_{metadata['expiry'].strftime('%Y%m%d')}_"
            f"RATIO_{metadata['long_strike']}_{metadata['short_strike']}"
        )
        self.ratio_positions[pos_id] = ratio
        
        logger.info(
            f"Opened Ratio: {pos_id}, Long={metadata['long_strike']}, "
            f"Short={metadata['short_strike']}, Net={metadata['net_credit_or_debit']:.2f}"
        )
        
        return ratio
    
    def close_ratio(
        self,
        pos_id: str,
        signal: Signal
    ) -> Trade:
        """Close a ratio spread position."""
        ratio = self.ratio_positions[pos_id]
        
        initial_value = ratio.net_credit_or_debit * ratio.quantity
        exit_value = ratio.get_current_value()
        pnl = exit_value - initial_value
        
        lot_size = self.config["lot_sizes"].get(ratio.underlying, 50)
        
        trade = Trade(
            symbol=pos_id,
            direction="SHORT",
            quantity=ratio.quantity * lot_size,
            entry_price=ratio.net_credit_or_debit,
            exit_price=ratio.get_current_value() / ratio.quantity if ratio.quantity > 0 else 0,
            entry_date=ratio.entry_date,
            exit_date=signal.timestamp,
            pnl=pnl * lot_size,
            exit_reason=signal.reason,
            metadata={
                "strategy": "ratio_spread",
                "long_strike": ratio.long_strike,
                "short_strike": ratio.short_strike,
                "ratio": ratio.ratio,
                "entry_iv_rank": ratio.entry_iv_rank,
            }
        )
        
        trade.return_pct = pnl / abs(initial_value) if initial_value != 0 else 0
        
        self.trades.append(trade)
        del self.ratio_positions[pos_id]
        
        logger.info(
            f"Closed Ratio: {pos_id}, PnL={pnl:.2f}, "
            f"Return={trade.return_pct:.2%}"
        )
        
        return trade
    
    def reset(self) -> None:
        """Reset strategy state."""
        super().reset()
        self.ratio_positions.clear()
        self.iv_rank_history = pd.Series(dtype=float)
