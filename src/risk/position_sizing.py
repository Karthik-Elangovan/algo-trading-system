"""
Position Sizing Module

This module provides utilities for calculating appropriate position sizes
based on various risk management methods.

Supported Methods:
- Fixed percentage of capital
- Kelly Criterion
- Volatility-based sizing
- Maximum drawdown-based sizing
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class PositionSizeResult:
    """
    Result of position size calculation.
    
    Attributes:
        quantity: Recommended position size
        capital_allocated: Amount of capital allocated
        risk_amount: Amount at risk
        method: Sizing method used
        details: Additional calculation details
    """
    quantity: int
    capital_allocated: float
    risk_amount: float
    method: str
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class PositionSizer:
    """
    Position sizing calculator with multiple methods.
    
    Implements various position sizing algorithms to help
    manage risk effectively across trades.
    
    Attributes:
        default_method: Default sizing method to use
        config: Configuration parameters
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        default_method: str = "fixed_percentage"
    ):
        """
        Initialize the PositionSizer.
        
        Args:
            config: Configuration dictionary with:
                - max_position_size_pct: Maximum position as % of capital
                - max_portfolio_risk_pct: Maximum total portfolio risk
                - daily_loss_limit_pct: Daily loss limit
                - default_risk_per_trade_pct: Default risk per trade
            default_method: Default sizing method
        """
        self.config = config or {
            "max_position_size_pct": 0.02,
            "max_portfolio_risk_pct": 0.10,
            "daily_loss_limit_pct": 0.05,
            "default_risk_per_trade_pct": 0.01,
        }
        self.default_method = default_method
    
    def calculate_position_size(
        self,
        capital: float,
        price: float,
        stop_loss: Optional[float] = None,
        lot_size: int = 1,
        method: Optional[str] = None,
        **kwargs
    ) -> PositionSizeResult:
        """
        Calculate position size based on specified method.
        
        Args:
            capital: Available capital
            price: Entry price
            stop_loss: Stop loss price (required for some methods)
            lot_size: Minimum lot size
            method: Sizing method ('fixed_percentage', 'risk_based', 'kelly', 'volatility')
            **kwargs: Additional method-specific parameters
        
        Returns:
            PositionSizeResult with recommended position size
        """
        method = method or self.default_method
        
        if method == "fixed_percentage":
            return self._fixed_percentage_sizing(capital, price, lot_size, **kwargs)
        elif method == "risk_based":
            return self._risk_based_sizing(capital, price, stop_loss, lot_size, **kwargs)
        elif method == "kelly":
            return self._kelly_criterion_sizing(capital, price, lot_size, **kwargs)
        elif method == "volatility":
            return self._volatility_based_sizing(capital, price, lot_size, **kwargs)
        else:
            logger.warning(f"Unknown sizing method: {method}. Using fixed_percentage.")
            return self._fixed_percentage_sizing(capital, price, lot_size, **kwargs)
    
    def _fixed_percentage_sizing(
        self,
        capital: float,
        price: float,
        lot_size: int = 1,
        position_pct: Optional[float] = None,
        **kwargs
    ) -> PositionSizeResult:
        """
        Calculate position size as fixed percentage of capital.
        
        Formula:
            Position Size = (Capital * Position%) / Price
        
        Args:
            capital: Available capital
            price: Entry price
            lot_size: Minimum lot size
            position_pct: Position as percentage of capital
        
        Returns:
            PositionSizeResult
        """
        pct = position_pct or self.config["max_position_size_pct"]
        
        capital_to_allocate = capital * pct
        raw_quantity = capital_to_allocate / price
        quantity = int(raw_quantity / lot_size) * lot_size
        
        actual_allocation = quantity * price
        
        return PositionSizeResult(
            quantity=max(lot_size, quantity),
            capital_allocated=actual_allocation,
            risk_amount=actual_allocation,  # Full position is at risk
            method="fixed_percentage",
            details={
                "position_pct": pct,
                "raw_quantity": raw_quantity,
            }
        )
    
    def _risk_based_sizing(
        self,
        capital: float,
        price: float,
        stop_loss: Optional[float],
        lot_size: int = 1,
        risk_pct: Optional[float] = None,
        **kwargs
    ) -> PositionSizeResult:
        """
        Calculate position size based on risk per trade.
        
        Formula:
            Risk per share = |Entry Price - Stop Loss|
            Position Size = (Capital * Risk%) / Risk per share
        
        This method ensures consistent risk across all trades
        regardless of the underlying's price or volatility.
        
        Args:
            capital: Available capital
            price: Entry price
            stop_loss: Stop loss price
            lot_size: Minimum lot size
            risk_pct: Risk as percentage of capital
        
        Returns:
            PositionSizeResult
        """
        if stop_loss is None:
            logger.warning("Stop loss required for risk-based sizing. Using fixed percentage.")
            return self._fixed_percentage_sizing(capital, price, lot_size)
        
        risk_pct = risk_pct or self.config["default_risk_per_trade_pct"]
        
        # Calculate risk per unit
        risk_per_unit = abs(price - stop_loss)
        
        if risk_per_unit <= 0:
            logger.warning("Invalid stop loss (no risk). Using fixed percentage.")
            return self._fixed_percentage_sizing(capital, price, lot_size)
        
        # Maximum amount to risk
        max_risk = capital * risk_pct
        
        # Calculate quantity
        raw_quantity = max_risk / risk_per_unit
        quantity = int(raw_quantity / lot_size) * lot_size
        
        # Ensure we don't exceed max position size
        max_position_value = capital * self.config["max_position_size_pct"]
        max_quantity_by_value = int(max_position_value / price / lot_size) * lot_size
        quantity = min(quantity, max_quantity_by_value)
        
        actual_risk = quantity * risk_per_unit
        actual_allocation = quantity * price
        
        return PositionSizeResult(
            quantity=max(lot_size, quantity),
            capital_allocated=actual_allocation,
            risk_amount=actual_risk,
            method="risk_based",
            details={
                "risk_pct": risk_pct,
                "risk_per_unit": risk_per_unit,
                "stop_loss": stop_loss,
            }
        )
    
    def _kelly_criterion_sizing(
        self,
        capital: float,
        price: float,
        lot_size: int = 1,
        win_rate: float = 0.5,
        win_loss_ratio: float = 1.5,
        kelly_fraction: float = 0.25,  # Quarter Kelly for safety
        **kwargs
    ) -> PositionSizeResult:
        """
        Calculate position size using Kelly Criterion.
        
        Kelly Formula:
            f* = (bp - q) / b
        
        Where:
            f* = fraction of capital to bet
            b = odds received (win/loss ratio)
            p = probability of winning
            q = probability of losing (1 - p)
        
        Args:
            capital: Available capital
            price: Entry price
            lot_size: Minimum lot size
            win_rate: Historical win rate
            win_loss_ratio: Average win / Average loss
            kelly_fraction: Fraction of Kelly to use (default 0.25 = quarter Kelly)
        
        Returns:
            PositionSizeResult
        """
        # Validate inputs
        win_rate = max(0.01, min(0.99, win_rate))
        win_loss_ratio = max(0.1, win_loss_ratio)
        
        # Calculate Kelly percentage
        b = win_loss_ratio
        p = win_rate
        q = 1 - p
        
        kelly_pct = (b * p - q) / b
        
        # Apply Kelly fraction for safety
        adjusted_kelly = kelly_pct * kelly_fraction
        
        # Ensure non-negative and capped
        adjusted_kelly = max(0, min(adjusted_kelly, self.config["max_position_size_pct"]))
        
        capital_to_allocate = capital * adjusted_kelly
        raw_quantity = capital_to_allocate / price
        quantity = int(raw_quantity / lot_size) * lot_size
        
        return PositionSizeResult(
            quantity=max(lot_size, quantity) if adjusted_kelly > 0 else 0,
            capital_allocated=quantity * price,
            risk_amount=quantity * price,
            method="kelly",
            details={
                "full_kelly_pct": kelly_pct,
                "adjusted_kelly_pct": adjusted_kelly,
                "win_rate": win_rate,
                "win_loss_ratio": win_loss_ratio,
                "kelly_fraction": kelly_fraction,
            }
        )
    
    def _volatility_based_sizing(
        self,
        capital: float,
        price: float,
        lot_size: int = 1,
        volatility: float = 0.20,  # Annualized volatility
        target_risk_pct: Optional[float] = None,
        lookback_days: int = 20,
        **kwargs
    ) -> PositionSizeResult:
        """
        Calculate position size based on volatility.
        
        Formula:
            Daily Vol = Annual Vol / sqrt(252)
            Position Size = (Capital * Target Risk%) / (Price * Daily Vol * 2)
        
        This normalizes position sizes so that each position contributes
        approximately the same risk to the portfolio.
        
        Args:
            capital: Available capital
            price: Entry price
            lot_size: Minimum lot size
            volatility: Annualized volatility
            target_risk_pct: Target risk percentage
            lookback_days: Days used for volatility calculation
        
        Returns:
            PositionSizeResult
        """
        target_risk = target_risk_pct or self.config["default_risk_per_trade_pct"]
        
        # Convert to daily volatility
        daily_vol = volatility / np.sqrt(252)
        
        # 2-sigma move covers ~95% of daily moves
        expected_daily_move = price * daily_vol * 2
        
        if expected_daily_move <= 0:
            logger.warning("Invalid volatility. Using fixed percentage.")
            return self._fixed_percentage_sizing(capital, price, lot_size)
        
        # Calculate position size
        max_risk = capital * target_risk
        raw_quantity = max_risk / expected_daily_move
        quantity = int(raw_quantity / lot_size) * lot_size
        
        # Cap at maximum position size
        max_quantity = int(capital * self.config["max_position_size_pct"] / price / lot_size) * lot_size
        quantity = min(quantity, max_quantity)
        
        return PositionSizeResult(
            quantity=max(lot_size, quantity),
            capital_allocated=quantity * price,
            risk_amount=quantity * expected_daily_move,
            method="volatility",
            details={
                "annualized_volatility": volatility,
                "daily_volatility": daily_vol,
                "expected_daily_move": expected_daily_move,
                "target_risk_pct": target_risk,
            }
        )
    
    def calculate_strangle_position_size(
        self,
        capital: float,
        call_premium: float,
        put_premium: float,
        lot_size: int,
        stop_loss_pct: float = 1.50,
        position_risk_pct: Optional[float] = None
    ) -> int:
        """
        Calculate position size for a short strangle.
        
        For strangles, risk is defined as the stop loss amount
        (typically 150% of premium collected).
        
        Args:
            capital: Available capital
            call_premium: Premium for call option
            put_premium: Premium for put option
            lot_size: Lot size of the underlying
            stop_loss_pct: Stop loss as multiple of premium
            position_risk_pct: Maximum risk per trade
        
        Returns:
            Number of strangles to trade
        """
        risk_pct = position_risk_pct or self.config["max_position_size_pct"]
        
        total_premium = call_premium + put_premium
        
        if total_premium <= 0:
            return 0
        
        # Risk per strangle = premium * stop_loss_pct * lot_size
        risk_per_strangle = total_premium * stop_loss_pct * lot_size
        
        # Maximum risk allowed
        max_risk = capital * risk_pct
        
        # Calculate number of strangles
        num_strangles = int(max_risk / risk_per_strangle)
        
        return max(1, num_strangles)
    
    def validate_position(
        self,
        quantity: int,
        price: float,
        capital: float,
        existing_positions: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Validate if a position can be taken given constraints.
        
        Checks:
        - Position size vs maximum allowed
        - Portfolio risk vs maximum allowed
        - Daily loss limit
        
        Args:
            quantity: Proposed position size
            price: Entry price
            capital: Available capital
            existing_positions: List of existing positions
        
        Returns:
            Dictionary with validation results
        """
        position_value = quantity * price
        position_pct = position_value / capital
        
        result = {
            "is_valid": True,
            "position_value": position_value,
            "position_pct": position_pct,
            "violations": []
        }
        
        # Check position size
        if position_pct > self.config["max_position_size_pct"]:
            result["is_valid"] = False
            result["violations"].append(
                f"Position size {position_pct:.2%} exceeds maximum {self.config['max_position_size_pct']:.2%}"
            )
        
        # Check portfolio risk
        if existing_positions:
            total_risk = sum(p.get("risk_amount", 0) for p in existing_positions)
            total_risk += position_value  # Simplified - use actual risk
            
            portfolio_risk_pct = total_risk / capital
            if portfolio_risk_pct > self.config["max_portfolio_risk_pct"]:
                result["is_valid"] = False
                result["violations"].append(
                    f"Portfolio risk {portfolio_risk_pct:.2%} would exceed maximum {self.config['max_portfolio_risk_pct']:.2%}"
                )
        
        return result
    
    def adjust_for_correlation(
        self,
        base_quantity: int,
        correlation: float,
        existing_exposure: float,
        max_exposure: float
    ) -> int:
        """
        Adjust position size based on correlation with existing positions.
        
        Reduces position size when adding correlated positions to maintain
        diversification.
        
        Args:
            base_quantity: Base position size without adjustment
            correlation: Correlation with existing portfolio
            existing_exposure: Current exposure to correlated assets
            max_exposure: Maximum allowed correlated exposure
        
        Returns:
            Adjusted position size
        """
        if correlation >= 0.7:  # High correlation
            adjustment_factor = 0.5
        elif correlation >= 0.4:  # Moderate correlation
            adjustment_factor = 0.75
        else:  # Low correlation
            adjustment_factor = 1.0
        
        # Further adjust based on existing exposure
        remaining_capacity = max(0, max_exposure - existing_exposure)
        exposure_factor = remaining_capacity / max_exposure if max_exposure > 0 else 0
        
        adjusted_quantity = int(base_quantity * adjustment_factor * exposure_factor)
        
        return max(0, adjusted_quantity)
