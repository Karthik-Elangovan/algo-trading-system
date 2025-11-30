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
    variety: str = "NORMAL"


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
    ltp: float
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


class BaseBroker(ABC):
    """Abstract base class for broker implementations."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._is_authenticated = False
        self._session_token: Optional[str] = None
        self._feed_token: Optional[str] = None
        logger.info(f"Initialized {self.__class__.__name__}")
    
    @property
    def is_authenticated(self) -> bool:
        return self._is_authenticated
    
    @abstractmethod
    def login(self) -> bool:
        pass
    
    @abstractmethod
    def logout(self) -> bool:
        pass
    
    @abstractmethod
    def get_profile(self) -> AccountInfo:
        pass
    
    @abstractmethod
    def get_ltp(self, symbol: str, exchange: str) -> float:
        pass
    
    @abstractmethod
    def get_quote(self, symbol: str, exchange: str) -> Quote:
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
        pass
    
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
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str, variety: str = "NORMAL") -> bool:
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Order:
        pass
    
    @abstractmethod
    def get_order_history(self) -> List[Order]:
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        pass
    
    @abstractmethod
    def get_holdings(self) -> List[Holding]:
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
        pass
    
    @abstractmethod
    def square_off_position(
        self,
        symbol: str,
        exchange: str,
        product_type: str,
        quantity: Optional[int] = None
    ) -> str:
        pass
    
    @abstractmethod
    def get_margin(self) -> Dict[str, float]:
        pass
    
    @abstractmethod
    def get_rms_limits(self) -> Dict[str, Any]:
        pass


class BrokerFactory:
    """Factory class for creating broker instances."""
    
    _brokers: Dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str, broker_class: type) -> None:
        cls._brokers[name.lower()] = broker_class
        logger.info(f"Registered broker: {name}")
    
    @classmethod
    def create(
        cls,
        mode: str = "paper",
        config: Optional[Dict[str, Any]] = None
    ) -> BaseBroker:
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
        return list(cls._brokers.keys())
