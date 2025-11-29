"""
Base Strategy Module

This module provides the abstract base class for all trading strategies.
All strategy implementations should inherit from BaseStrategy.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import pandas as pd
import logging

# Configure logging
logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Enumeration of signal types."""
    ENTRY_LONG = "ENTRY_LONG"
    ENTRY_SHORT = "ENTRY_SHORT"
    EXIT_LONG = "EXIT_LONG"
    EXIT_SHORT = "EXIT_SHORT"
    HOLD = "HOLD"
    NO_ACTION = "NO_ACTION"


class OrderType(Enum):
    """Enumeration of order types."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LIMIT = "STOP_LIMIT"


@dataclass
class Signal:
    """
    Data class representing a trading signal.
    
    Attributes:
        signal_type: Type of signal (entry, exit, hold)
        symbol: Trading symbol
        quantity: Number of contracts/shares
        price: Target price for limit orders
        stop_loss: Stop loss price
        take_profit: Take profit price
        timestamp: Time when signal was generated
        reason: Reason for the signal
        metadata: Additional signal metadata
    """
    signal_type: SignalType
    symbol: str
    quantity: int = 0
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_entry(self) -> bool:
        """Check if signal is an entry signal."""
        return self.signal_type in [SignalType.ENTRY_LONG, SignalType.ENTRY_SHORT]
    
    def is_exit(self) -> bool:
        """Check if signal is an exit signal."""
        return self.signal_type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]


@dataclass
class Position:
    """
    Data class representing an open position.
    
    Attributes:
        symbol: Trading symbol
        quantity: Position size (negative for short)
        entry_price: Average entry price
        entry_date: Date position was opened
        current_price: Current market price
        unrealized_pnl: Unrealized profit/loss
        stop_loss: Stop loss price
        take_profit: Take profit price
        metadata: Additional position metadata
    """
    symbol: str
    quantity: int
    entry_price: float
    entry_date: datetime
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_price(self, current_price: float) -> None:
        """Update current price and calculate unrealized PnL."""
        self.current_price = current_price
        self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
    
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.quantity > 0
    
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.quantity < 0


@dataclass
class Trade:
    """
    Data class representing a completed trade.
    
    Attributes:
        symbol: Trading symbol
        direction: 'LONG' or 'SHORT'
        quantity: Trade size
        entry_price: Entry price
        exit_price: Exit price
        entry_date: Entry timestamp
        exit_date: Exit timestamp
        pnl: Realized profit/loss
        return_pct: Percentage return
        holding_period: Duration of trade in days
        exit_reason: Reason for exit
        metadata: Additional trade metadata
    """
    symbol: str
    direction: str
    quantity: int
    entry_price: float
    exit_price: float
    entry_date: datetime
    exit_date: datetime
    pnl: float = 0.0
    return_pct: float = 0.0
    holding_period: int = 0
    exit_reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields after initialization."""
        if self.entry_price > 0:
            if self.direction == "LONG":
                self.pnl = (self.exit_price - self.entry_price) * self.quantity
                self.return_pct = (self.exit_price - self.entry_price) / self.entry_price
            else:  # SHORT
                self.pnl = (self.entry_price - self.exit_price) * abs(self.quantity)
                self.return_pct = (self.entry_price - self.exit_price) / self.entry_price
        
        self.holding_period = (self.exit_date - self.entry_date).days


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies.
    
    All trading strategies should inherit from this class and implement
    the required abstract methods.
    
    Attributes:
        name: Strategy name
        config: Strategy configuration dictionary
        positions: Dictionary of open positions
        trades: List of completed trades
        signals: List of generated signals
    """
    
    def __init__(
        self,
        name: str = "BaseStrategy",
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the base strategy.
        
        Args:
            name: Strategy name
            config: Configuration dictionary with strategy parameters
        """
        self.name = name
        self.config = config or {}
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.signals: List[Signal] = []
        self._is_initialized = False
    
    @abstractmethod
    def generate_signal(
        self,
        data: pd.DataFrame,
        timestamp: datetime
    ) -> Optional[Signal]:
        """
        Generate trading signal based on market data.
        
        This method must be implemented by all strategy subclasses.
        
        Args:
            data: DataFrame with market data up to current timestamp
            timestamp: Current timestamp
        
        Returns:
            Signal object or None if no signal
        """
        pass
    
    @abstractmethod
    def calculate_position_size(
        self,
        capital: float,
        price: float,
        signal: Signal
    ) -> int:
        """
        Calculate position size for a trade.
        
        This method must be implemented by all strategy subclasses.
        
        Args:
            capital: Available capital
            price: Current price
            signal: Trading signal
        
        Returns:
            Position size (number of contracts/shares)
        """
        pass
    
    def initialize(self, data: pd.DataFrame) -> None:
        """
        Initialize strategy with historical data.
        
        Called before backtesting begins. Use this to pre-compute
        indicators or set up any required state.
        
        Args:
            data: Historical market data
        """
        logger.info(f"Initializing strategy: {self.name}")
        self._is_initialized = True
    
    def on_bar(
        self,
        data: pd.DataFrame,
        timestamp: datetime,
        capital: float
    ) -> Optional[Signal]:
        """
        Process a new bar of data.
        
        Called by the backtesting engine for each time period.
        
        Args:
            data: Market data up to current timestamp
            timestamp: Current timestamp
            capital: Current available capital
        
        Returns:
            Signal object or None
        """
        if not self._is_initialized:
            self.initialize(data)
        
        signal = self.generate_signal(data, timestamp)
        
        if signal:
            self.signals.append(signal)
            logger.debug(f"Signal generated: {signal}")
        
        return signal
    
    def open_position(
        self,
        symbol: str,
        quantity: int,
        entry_price: float,
        entry_date: datetime,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Position:
        """
        Open a new position.
        
        Args:
            symbol: Trading symbol
            quantity: Position size (negative for short)
            entry_price: Entry price
            entry_date: Entry timestamp
            stop_loss: Stop loss price
            take_profit: Take profit price
            metadata: Additional position metadata
        
        Returns:
            New Position object
        """
        position = Position(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            entry_date=entry_date,
            current_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata=metadata or {}
        )
        
        self.positions[symbol] = position
        logger.info(f"Opened position: {symbol} @ {entry_price}, qty={quantity}")
        
        return position
    
    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_date: datetime,
        exit_reason: str = ""
    ) -> Optional[Trade]:
        """
        Close an existing position.
        
        Args:
            symbol: Trading symbol
            exit_price: Exit price
            exit_date: Exit timestamp
            exit_reason: Reason for closing
        
        Returns:
            Trade object representing the completed trade, or None
        """
        if symbol not in self.positions:
            logger.warning(f"No position found for symbol: {symbol}")
            return None
        
        position = self.positions[symbol]
        
        trade = Trade(
            symbol=symbol,
            direction="LONG" if position.is_long() else "SHORT",
            quantity=abs(position.quantity),
            entry_price=position.entry_price,
            exit_price=exit_price,
            entry_date=position.entry_date,
            exit_date=exit_date,
            exit_reason=exit_reason,
            metadata=position.metadata
        )
        
        self.trades.append(trade)
        del self.positions[symbol]
        
        logger.info(
            f"Closed position: {symbol} @ {exit_price}, "
            f"PnL={trade.pnl:.2f}, Return={trade.return_pct:.2%}"
        )
        
        return trade
    
    def update_positions(
        self,
        prices: Dict[str, float],
        timestamp: datetime
    ) -> List[Signal]:
        """
        Update all positions with current prices and check exit conditions.
        
        Args:
            prices: Dictionary mapping symbols to current prices
            timestamp: Current timestamp
        
        Returns:
            List of exit signals generated
        """
        exit_signals = []
        
        for symbol, position in list(self.positions.items()):
            if symbol in prices:
                position.update_price(prices[symbol])
                
                # Check stop loss
                if position.stop_loss:
                    if position.is_long() and prices[symbol] <= position.stop_loss:
                        exit_signals.append(Signal(
                            signal_type=SignalType.EXIT_LONG,
                            symbol=symbol,
                            quantity=abs(position.quantity),
                            price=prices[symbol],
                            timestamp=timestamp,
                            reason="Stop loss triggered"
                        ))
                    elif position.is_short() and prices[symbol] >= position.stop_loss:
                        exit_signals.append(Signal(
                            signal_type=SignalType.EXIT_SHORT,
                            symbol=symbol,
                            quantity=abs(position.quantity),
                            price=prices[symbol],
                            timestamp=timestamp,
                            reason="Stop loss triggered"
                        ))
                
                # Check take profit
                if position.take_profit:
                    if position.is_long() and prices[symbol] >= position.take_profit:
                        exit_signals.append(Signal(
                            signal_type=SignalType.EXIT_LONG,
                            symbol=symbol,
                            quantity=abs(position.quantity),
                            price=prices[symbol],
                            timestamp=timestamp,
                            reason="Take profit triggered"
                        ))
                    elif position.is_short() and prices[symbol] <= position.take_profit:
                        exit_signals.append(Signal(
                            signal_type=SignalType.EXIT_SHORT,
                            symbol=symbol,
                            quantity=abs(position.quantity),
                            price=prices[symbol],
                            timestamp=timestamp,
                            reason="Take profit triggered"
                        ))
        
        return exit_signals
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        return self.positions.get(symbol)
    
    def has_position(self, symbol: str) -> bool:
        """Check if position exists for a symbol."""
        return symbol in self.positions
    
    def get_total_positions(self) -> int:
        """Get total number of open positions."""
        return len(self.positions)
    
    def get_trade_statistics(self) -> Dict[str, Any]:
        """
        Calculate basic trade statistics.
        
        Returns:
            Dictionary with trade statistics
        """
        if not self.trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0,
                "avg_winner": 0.0,
                "avg_loser": 0.0,
            }
        
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl < 0]
        
        return {
            "total_trades": len(self.trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": len(winning_trades) / len(self.trades) if self.trades else 0,
            "total_pnl": sum(t.pnl for t in self.trades),
            "avg_pnl": sum(t.pnl for t in self.trades) / len(self.trades),
            "avg_winner": sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0,
            "avg_loser": sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0,
        }
    
    def reset(self) -> None:
        """Reset strategy state."""
        self.positions.clear()
        self.trades.clear()
        self.signals.clear()
        self._is_initialized = False
        logger.info(f"Strategy {self.name} reset")
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
