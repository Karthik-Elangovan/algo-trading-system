"""
Data Handler Module

Provides data fetching and processing functionality for the trading dashboard.
Integrates with the existing Phase 1 data modules and trading logic.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.historical_data import HistoricalDataFetcher
from src.strategies.base_strategy import Position, Trade
from src.strategies.premium_selling import StranglePosition, PremiumSellingStrategy
from src.indicators.volatility import IVRankCalculator, VolatilityIndicators
from src.backtesting.metrics import calculate_var, calculate_cvar
from config.settings import PREMIUM_SELLING_CONFIG, RISK_CONFIG, INSTRUMENT_CONFIG


@dataclass
class MarketData:
    """
    Container for current market data.
    
    Attributes:
        spot_price: Current spot price
        iv: Current implied volatility
        iv_rank: Current IV Rank
        bid: Best bid price
        ask: Best ask price
        change: Daily change percentage
        volume: Trading volume
        timestamp: Data timestamp
    """
    spot_price: float
    iv: float = 0.0
    iv_rank: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    change: float = 0.0
    volume: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RiskMetrics:
    """
    Container for risk metrics.
    
    Attributes:
        var_95: Value at Risk (95%)
        var_99: Value at Risk (99%)
        cvar_95: Conditional VaR (95%)
        margin_used: Margin usage percentage
        max_exposure: Maximum portfolio exposure
        daily_pnl: Daily P&L
        total_pnl: Total P&L
        drawdown: Current drawdown
        delta_exposure: Total delta exposure
        gamma_exposure: Total gamma exposure
        theta_exposure: Total theta exposure
        vega_exposure: Total vega exposure
    """
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    margin_used: float = 0.0
    max_exposure: float = 0.0
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    drawdown: float = 0.0
    delta_exposure: float = 0.0
    gamma_exposure: float = 0.0
    theta_exposure: float = 0.0
    vega_exposure: float = 0.0


@dataclass
class PositionData:
    """
    Container for position data with Greeks.
    
    Attributes:
        symbol: Position symbol
        underlying: Underlying asset
        position_type: Type of position (e.g., 'Short Strangle')
        quantity: Number of contracts
        entry_price: Entry price
        current_price: Current price
        unrealized_pnl: Unrealized P&L
        delta: Position delta
        gamma: Position gamma
        theta: Position theta
        vega: Position vega
        entry_date: Entry timestamp
        expiry: Option expiry date
    """
    symbol: str
    underlying: str
    position_type: str
    quantity: int
    entry_price: float
    current_price: float
    unrealized_pnl: float
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    entry_date: datetime = field(default_factory=datetime.now)
    expiry: Optional[datetime] = None


class DashboardDataHandler:
    """
    Handles data fetching and processing for the trading dashboard.
    
    Integrates with existing Phase 1 modules to provide:
    - Real-time market data (simulated from historical data)
    - Position tracking
    - Risk metrics calculation
    - P&L history
    - Order history
    
    Attributes:
        data_fetcher: Historical data fetcher instance
        iv_calculator: IV Rank calculator instance
        vol_indicators: Volatility indicators instance
        strategy: Current trading strategy instance
    """
    
    def __init__(self, initial_capital: float = 1_000_000):
        """
        Initialize the data handler.
        
        Args:
            initial_capital: Initial trading capital
        """
        self.data_fetcher = HistoricalDataFetcher()
        self.iv_calculator = IVRankCalculator()
        self.vol_indicators = VolatilityIndicators()
        self.strategy = PremiumSellingStrategy(config=PREMIUM_SELLING_CONFIG)
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        
        # Cache for performance
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._last_update: Optional[datetime] = None
        
        # Simulated data for demo
        self._pnl_history: List[Dict[str, Any]] = []
        self._order_history: List[Dict[str, Any]] = []
        self._positions: List[PositionData] = []
        
        # Initialize with sample data
        self._initialize_sample_data()
    
    def _initialize_sample_data(self) -> None:
        """Initialize sample data for demonstration."""
        np.random.seed(42)
        
        # Generate sample P&L history
        dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
        cumulative_pnl = 0
        
        for i, date in enumerate(dates):
            daily_pnl = np.random.normal(2000, 5000)
            cumulative_pnl += daily_pnl
            self._pnl_history.append({
                "date": date,
                "daily_pnl": daily_pnl,
                "cumulative_pnl": cumulative_pnl,
                "equity": self.initial_capital + cumulative_pnl,
            })
        
        # Update current capital
        if self._pnl_history:
            self.current_capital = self._pnl_history[-1]["equity"]
        
        # Generate sample order history
        order_types = ["Market", "Limit"]
        order_statuses = ["Filled", "Filled", "Filled", "Cancelled", "Pending"]
        instruments = ["NIFTY", "BANKNIFTY"]
        
        for i in range(20):
            order_date = datetime.now() - timedelta(days=np.random.randint(1, 30))
            instrument = np.random.choice(instruments)
            lot_size = INSTRUMENT_CONFIG[instrument]["lot_size"]
            
            self._order_history.append({
                "order_id": f"ORD{1000 + i}",
                "timestamp": order_date,
                "symbol": f"{instrument}25DEC{18000 + i * 50}{'CE' if i % 2 == 0 else 'PE'}",
                "underlying": instrument,
                "side": np.random.choice(["BUY", "SELL"]),
                "quantity": lot_size * np.random.randint(1, 3),
                "order_type": np.random.choice(order_types),
                "price": np.random.uniform(50, 300),
                "status": np.random.choice(order_statuses),
            })
        
        # Sort order history by timestamp
        self._order_history.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Generate sample positions
        self._generate_sample_positions()
    
    def _generate_sample_positions(self) -> None:
        """Generate sample positions for demonstration."""
        # Sample strangle positions
        positions = [
            {
                "symbol": "NIFTY_25DEC_19500C_18500P",
                "underlying": "NIFTY",
                "position_type": "Short Strangle",
                "quantity": 100,
                "entry_price": 250,
                "current_price": 180,
                "delta": -0.15,
                "gamma": 0.002,
                "theta": -8.5,
                "vega": 12.3,
                "expiry": datetime.now() + timedelta(days=15),
            },
            {
                "symbol": "BANKNIFTY_25DEC_44500C_42500P",
                "underlying": "BANKNIFTY",
                "position_type": "Short Strangle",
                "quantity": 45,
                "entry_price": 380,
                "current_price": 320,
                "delta": -0.08,
                "gamma": 0.001,
                "theta": -12.2,
                "vega": 18.5,
                "expiry": datetime.now() + timedelta(days=22),
            },
            {
                "symbol": "NIFTY_25DEC_20000C_18000P",
                "underlying": "NIFTY",
                "position_type": "Short Strangle",
                "quantity": 50,
                "entry_price": 180,
                "current_price": 220,
                "delta": 0.22,
                "gamma": 0.003,
                "theta": -6.8,
                "vega": 9.2,
                "expiry": datetime.now() + timedelta(days=8),
            },
        ]
        
        for pos in positions:
            unrealized_pnl = (pos["entry_price"] - pos["current_price"]) * pos["quantity"]
            self._positions.append(PositionData(
                symbol=pos["symbol"],
                underlying=pos["underlying"],
                position_type=pos["position_type"],
                quantity=pos["quantity"],
                entry_price=pos["entry_price"],
                current_price=pos["current_price"],
                unrealized_pnl=unrealized_pnl,
                delta=pos["delta"],
                gamma=pos["gamma"],
                theta=pos["theta"],
                vega=pos["vega"],
                entry_date=datetime.now() - timedelta(days=np.random.randint(5, 20)),
                expiry=pos["expiry"],
            ))
    
    def get_market_data(self, underlying: str = "NIFTY") -> MarketData:
        """
        Get current market data for an underlying.
        
        Args:
            underlying: Name of the underlying asset
        
        Returns:
            MarketData object with current market data
        """
        # Base prices for different underlyings
        base_prices = {
            "NIFTY": 19250,
            "BANKNIFTY": 43500,
            "SENSEX": 64800,
        }
        
        base_price = base_prices.get(underlying, 19250)
        
        # Add some randomness to simulate live data
        noise = np.random.normal(0, base_price * 0.001)
        current_price = base_price + noise
        
        # Generate other market data
        return MarketData(
            spot_price=round(current_price, 2),
            iv=round(np.random.uniform(0.12, 0.22), 4),
            iv_rank=round(np.random.uniform(40, 85), 1),
            bid=round(current_price - np.random.uniform(0.5, 2), 2),
            ask=round(current_price + np.random.uniform(0.5, 2), 2),
            change=round(np.random.uniform(-1.5, 1.5), 2),
            volume=np.random.randint(10000, 100000),
            timestamp=datetime.now(),
        )
    
    def get_positions(self) -> List[PositionData]:
        """
        Get current open positions.
        
        Returns:
            List of PositionData objects
        """
        # Update positions with slight price movement for demo
        for pos in self._positions:
            price_change = np.random.normal(0, pos.current_price * 0.02)
            pos.current_price = round(pos.current_price + price_change, 2)
            pos.unrealized_pnl = round(
                (pos.entry_price - pos.current_price) * pos.quantity, 2
            )
        
        return self._positions
    
    def get_risk_metrics(self) -> RiskMetrics:
        """
        Calculate and return current risk metrics.
        
        Returns:
            RiskMetrics object with current risk metrics
        """
        # Get P&L history for VaR calculation
        if len(self._pnl_history) > 10:
            daily_returns = pd.Series([p["daily_pnl"] / self.initial_capital 
                                      for p in self._pnl_history[-60:]])
            var_95 = calculate_var(daily_returns, confidence=0.95)
            var_99 = calculate_var(daily_returns, confidence=0.99)
            cvar_95 = calculate_cvar(daily_returns, confidence=0.95)
        else:
            var_95 = 0.0
            var_99 = 0.0
            cvar_95 = 0.0
        
        # Calculate total Greeks exposure
        total_delta = sum(p.delta * p.quantity for p in self._positions)
        total_gamma = sum(p.gamma * p.quantity for p in self._positions)
        total_theta = sum(p.theta * p.quantity for p in self._positions)
        total_vega = sum(p.vega * p.quantity for p in self._positions)
        
        # Calculate other metrics
        total_unrealized_pnl = sum(p.unrealized_pnl for p in self._positions)
        daily_pnl = self._pnl_history[-1]["daily_pnl"] if self._pnl_history else 0
        total_pnl = self._pnl_history[-1]["cumulative_pnl"] if self._pnl_history else 0
        
        # Calculate margin and exposure
        total_exposure = sum(abs(p.current_price * p.quantity) for p in self._positions)
        margin_used = min(total_exposure / self.current_capital * 100, 100) if self.current_capital > 0 else 0
        
        # Calculate drawdown
        if self._pnl_history:
            equity_series = pd.Series([p["equity"] for p in self._pnl_history])
            peak = equity_series.expanding().max()
            drawdown = ((equity_series - peak) / peak).min()
        else:
            drawdown = 0.0
        
        return RiskMetrics(
            var_95=round(var_95 * self.current_capital, 2),
            var_99=round(var_99 * self.current_capital, 2),
            cvar_95=round(cvar_95 * self.current_capital, 2),
            margin_used=round(margin_used, 2),
            max_exposure=round(total_exposure, 2),
            daily_pnl=round(daily_pnl, 2),
            total_pnl=round(total_pnl + total_unrealized_pnl, 2),
            drawdown=round(abs(drawdown) * 100, 2),
            delta_exposure=round(total_delta, 4),
            gamma_exposure=round(total_gamma, 6),
            theta_exposure=round(total_theta, 2),
            vega_exposure=round(total_vega, 2),
        )
    
    def get_pnl_history(self) -> pd.DataFrame:
        """
        Get P&L history as DataFrame.
        
        Returns:
            DataFrame with P&L history
        """
        if not self._pnl_history:
            return pd.DataFrame()
        
        return pd.DataFrame(self._pnl_history)
    
    def get_order_history(self) -> List[Dict[str, Any]]:
        """
        Get order history.
        
        Returns:
            List of order dictionaries
        """
        return self._order_history
    
    def get_equity_curve(self) -> pd.DataFrame:
        """
        Get equity curve data.
        
        Returns:
            DataFrame with equity curve data
        """
        if not self._pnl_history:
            return pd.DataFrame()
        
        df = pd.DataFrame(self._pnl_history)
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        
        # Calculate drawdown series
        df["peak"] = df["equity"].expanding().max()
        df["drawdown"] = (df["equity"] - df["peak"]) / df["peak"]
        
        return df
    
    def get_strategies(self) -> List[Dict[str, Any]]:
        """
        Get available trading strategies.
        
        Returns:
            List of strategy configurations
        """
        return [
            {
                "name": "Premium Selling (Short Strangle)",
                "description": "Sell OTM calls and puts when IV is high",
                "parameters": {
                    "iv_rank_threshold": 70,
                    "delta_range": (0.15, 0.20),
                    "profit_target_pct": 0.50,
                    "stop_loss_pct": 1.50,
                    "max_positions": 5,
                },
                "status": "active",
            },
            {
                "name": "Iron Condor",
                "description": "Sell strangle with wings for defined risk",
                "parameters": {
                    "iv_rank_threshold": 60,
                    "short_delta": 0.20,
                    "long_delta": 0.10,
                    "profit_target_pct": 0.40,
                },
                "status": "inactive",
            },
            {
                "name": "Calendar Spread",
                "description": "Sell near-term, buy far-term options",
                "parameters": {
                    "front_dte": 7,
                    "back_dte": 30,
                    "profit_target_pct": 0.30,
                },
                "status": "inactive",
            },
        ]
    
    def add_alert(self, alert_type: str, message: str) -> None:
        """
        Add a new alert to the system.
        
        Args:
            alert_type: Type of alert (info, warning, danger, success)
            message: Alert message
        """
        # This would typically be stored and managed by the AlertManager
        pass
    
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Place a new order (simulated).
        
        Args:
            symbol: Trading symbol
            side: Order side (BUY or SELL)
            quantity: Order quantity
            order_type: Order type (Market, Limit, Stop)
            price: Limit price (optional)
        
        Returns:
            Order confirmation dictionary
        """
        order = {
            "order_id": f"ORD{len(self._order_history) + 1001}",
            "timestamp": datetime.now(),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "price": price or np.random.uniform(100, 300),
            "status": "Pending",
        }
        
        self._order_history.insert(0, order)
        
        return order
    
    def close_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Close a position (simulated).
        
        Args:
            symbol: Position symbol to close
        
        Returns:
            Closing order details or None if position not found
        """
        for i, pos in enumerate(self._positions):
            if pos.symbol == symbol:
                # Create closing order
                order = self.place_order(
                    symbol=symbol,
                    side="BUY" if pos.quantity > 0 else "SELL",
                    quantity=abs(pos.quantity),
                    order_type="Market",
                )
                order["status"] = "Filled"
                
                # Remove position
                self._positions.pop(i)
                
                return order
        
        return None
    
    def get_available_underlyings(self) -> List[str]:
        """
        Get list of available underlying assets.
        
        Returns:
            List of underlying asset names
        """
        return list(INSTRUMENT_CONFIG.keys())
    
    def get_instrument_config(self, underlying: str) -> Dict[str, Any]:
        """
        Get configuration for an underlying instrument.
        
        Args:
            underlying: Underlying asset name
        
        Returns:
            Instrument configuration dictionary
        """
        return INSTRUMENT_CONFIG.get(underlying, INSTRUMENT_CONFIG["NIFTY"])
