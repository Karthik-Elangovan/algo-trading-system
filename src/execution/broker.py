"""
Abstract Broker Interface and Factory Pattern.

This module defines the abstract base class for broker implementations
and provides a factory for creating broker instances.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order types supported by brokers."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOPLOSS"
    STOP_LOSS_MARKET = "STOPLOSS_MARKET"


class TransactionType(Enum):
    """Transaction types for orders."""
    BUY = "BUY"
    SELL = "SELL"


class ProductType(Enum):
    """Product types for positions."""
    INTRADAY = "INTRADAY"  # MIS
    DELIVERY = "DELIVERY"  # CNC
    CARRYFORWARD = "CARRYFORWARD"  # NRML


class Exchange(Enum):
    """Stock exchanges."""
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"  # NSE F&O
    BFO = "BFO"  # BSE F&O
    MCX = "MCX"  # Commodity


class OrderStatus(Enum):
    """Order status values."""
    PENDING = "pending"
    OPEN = "open"
    COMPLETE = "complete"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    TRIGGER_PENDING = "trigger pending"


@dataclass
class Order:
    """Represents a trading order."""
    order_id: str
    symbol: str
    exchange: str
    transaction_type: str
    quantity: int
    order_type: str
    product_type: str
    price: float = 0.0
    trigger_price: float = 0.0
    status: str = "pending"
    filled_quantity: int = 0
    average_price: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    message: str = ""
    variety: str = "NORMAL"  # NORMAL, STOPLOSS, AMO, ROBO


@dataclass
class Position:
    """Represents a trading position."""
    symbol: str
    exchange: str
    product_type: str
    quantity: int
    average_price: float
    last_price: float = 0.0
    pnl: float = 0.0
    pnl_percentage: float = 0.0
    day_buy_quantity: int = 0
    day_sell_quantity: int = 0
    day_buy_value: float = 0.0
    day_sell_value: float = 0.0
    multiplier: int = 1


@dataclass
class Holding:
    """Represents a portfolio holding."""
    symbol: str
    exchange: str
    quantity: int
    average_price: float
    last_price: float = 0.0
    pnl: float = 0.0
    pnl_percentage: float = 0.0
    isin: str = ""


@dataclass
class Quote:
    """Market quote data."""
    symbol: str
    exchange: str
    ltp: float  # Last Traded Price
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    bid_price: float = 0.0
    ask_price: float = 0.0
    bid_quantity: int = 0
    ask_quantity: int = 0


@dataclass
class AccountInfo:
    """Account information."""
    client_id: str
    name: str
    email: str = ""
    phone: str = ""
    broker: str = ""
    available_margin: float = 0.0
    used_margin: float = 0.0
    total_margin: float = 0.0


class BrokerError(Exception):
    """Base exception for broker-related errors."""
    pass


class AuthenticationError(BrokerError):
    """Authentication failed."""
    pass


class OrderError(BrokerError):
    """Order-related error."""
    pass


class ConnectionError(BrokerError):
    """Connection error with broker API."""
    pass


class BaseBroker(ABC):
    """
    Abstract base class for broker implementations.
    
    All broker implementations (live, paper) must inherit from this class
    and implement all abstract methods.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the broker.
        
        Args:
            config: Configuration dictionary for the broker
        """
        self.config = config or {}
        self._is_authenticated = False
        self._session_token: Optional[str] = None
        self._feed_token: Optional[str] = None
        logger.info(f"Initialized {self.__class__.__name__}")
    
    @property
    def is_authenticated(self) -> bool:
        """Check if broker is authenticated."""
        return self._is_authenticated
    
    # ==================== Authentication ====================
    
    @abstractmethod
    def login(self) -> bool:
        """
        Authenticate with the broker.
        
        Returns:
            True if login successful, False otherwise
        """
        pass
    
    @abstractmethod
    def logout(self) -> bool:
        """
        Logout from the broker.
        
        Returns:
            True if logout successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_profile(self) -> AccountInfo:
        """
        Get user profile information.
        
        Returns:
            AccountInfo object with user details
        """
        pass
    
    # ==================== Market Data ====================
    
    @abstractmethod
    def get_ltp(self, symbol: str, exchange: str) -> float:
        """
        Get Last Traded Price for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange (NSE, NFO, etc.)
            
        Returns:
            Last traded price
        """
        pass
    
    @abstractmethod
    def get_quote(self, symbol: str, exchange: str) -> Quote:
        """
        Get full quote for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            
        Returns:
            Quote object with market data
        """
        pass
    
    @abstractmethod
    def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get historical candle data.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            interval: Candle interval (ONE_MINUTE, FIVE_MINUTE, etc.)
            from_date: Start date
            to_date: End date
            
        Returns:
            List of candle data dictionaries
        """
        pass
    
    # ==================== Order Management ====================
    
    @abstractmethod
    def place_order(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str = "MARKET",
        product_type: str = "INTRADAY",
        price: float = 0.0,
        trigger_price: float = 0.0,
        variety: str = "NORMAL"
    ) -> str:
        """
        Place a new order.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            transaction_type: BUY or SELL
            quantity: Order quantity
            order_type: MARKET, LIMIT, STOPLOSS, STOPLOSS_MARKET
            product_type: INTRADAY, DELIVERY, CARRYFORWARD
            price: Limit price (for LIMIT orders)
            trigger_price: Trigger price (for STOPLOSS orders)
            variety: NORMAL, STOPLOSS, AMO, ROBO
            
        Returns:
            Order ID string
        """
        pass
    
    @abstractmethod
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        order_type: Optional[str] = None
    ) -> bool:
        """
        Modify an existing order.
        
        Args:
            order_id: Order ID to modify
            quantity: New quantity (optional)
            price: New price (optional)
            trigger_price: New trigger price (optional)
            order_type: New order type (optional)
            
        Returns:
            True if modification successful
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str, variety: str = "NORMAL") -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            variety: Order variety
            
        Returns:
            True if cancellation successful
        """
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Order:
        """
        Get status of an order.
        
        Args:
            order_id: Order ID
            
        Returns:
            Order object with current status
        """
        pass
    
    @abstractmethod
    def get_order_history(self) -> List[Order]:
        """
        Get all orders for the day.
        
        Returns:
            List of Order objects
        """
        pass
    
    # ==================== Position Management ====================
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """
        Get current positions.
        
        Returns:
            List of Position objects
        """
        pass
    
    @abstractmethod
    def get_holdings(self) -> List[Holding]:
        """
        Get portfolio holdings.
        
        Returns:
            List of Holding objects
        """
        pass
    
    @abstractmethod
    def convert_position(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        from_product: str,
        to_product: str
    ) -> bool:
        """
        Convert position product type.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            transaction_type: BUY or SELL
            quantity: Quantity to convert
            from_product: Current product type
            to_product: Target product type
            
        Returns:
            True if conversion successful
        """
        pass
    
    @abstractmethod
    def square_off_position(
        self,
        symbol: str,
        exchange: str,
        product_type: str,
        quantity: Optional[int] = None
    ) -> str:
        """
        Square off a position.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            product_type: Product type
            quantity: Quantity to square off (None = full position)
            
        Returns:
            Order ID of square off order
        """
        pass
    
    # ==================== Account Information ====================
    
    @abstractmethod
    def get_margin(self) -> Dict[str, float]:
        """
        Get margin/funds information.
        
        Returns:
            Dictionary with margin details
        """
        pass
    
    @abstractmethod
    def get_rms_limits(self) -> Dict[str, Any]:
        """
        Get RMS (Risk Management) limits.
        
        Returns:
            Dictionary with RMS limit details
        """
        pass


class BrokerFactory:
    """
    Factory class for creating broker instances.
    
    Supports creating live (Angel One) and paper trading brokers
    based on configuration.
    """
    
    _brokers: Dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str, broker_class: type) -> None:
        """
        Register a broker implementation.
        
        Args:
            name: Broker name identifier
            broker_class: Broker class to register
        """
        cls._brokers[name.lower()] = broker_class
        logger.info(f"Registered broker: {name}")
    
    @classmethod
    def create(
        cls,
        mode: str = "paper",
        config: Optional[Dict[str, Any]] = None
    ) -> BaseBroker:
        """
        Create a broker instance.
        
        Args:
            mode: Trading mode ("live" or "paper")
            config: Broker configuration
            
        Returns:
            Broker instance
            
        Raises:
            ValueError: If mode is not supported
        """
        mode = mode.lower()
        
        if mode not in cls._brokers:
            available = list(cls._brokers.keys())
            raise ValueError(
                f"Broker mode '{mode}' not supported. "
                f"Available modes: {available}"
            )
        
        broker_class = cls._brokers[mode]
        logger.info(f"Creating broker instance: mode={mode}")
        return broker_class(config)
    
    @classmethod
    def available_brokers(cls) -> List[str]:
        """Get list of available broker implementations."""
        return list(cls._brokers.keys())
