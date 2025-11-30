"""
Abstract Base Class for Data Providers.

Defines the interface for real-time data providers.
"""

import logging
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class DataProvider(ABC):
    """
    Abstract base class for real-time data providers.
    
    All data providers must implement this interface to be compatible
    with the RealTimeDataManager.
    """
    
    # Feed modes
    FEED_MODE_LTP = 1     # LTP mode - only last traded price
    FEED_MODE_QUOTE = 2   # Quote mode - LTP + OHLC + volume
    FEED_MODE_DEPTH = 3   # Full depth mode - 5 best bid/ask
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data provider.
        
        Args:
            config: Optional configuration dictionary
        """
        self._config = config or {}
        self._tick_callbacks: List[Callable] = []
        self._is_connected = False
        
    @property
    def is_connected(self) -> bool:
        """Check if provider is connected."""
        return self._is_connected
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the data source.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """
        Disconnect from the data source.
        
        Returns:
            True if disconnection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def subscribe(self, tokens: List[str], mode: int = 1) -> bool:
        """
        Subscribe to market data for given tokens.
        
        Args:
            tokens: List of symbol tokens to subscribe
            mode: Feed mode (1=LTP, 2=Quote, 3=Depth)
            
        Returns:
            True if subscription successful, False otherwise
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, tokens: List[str]) -> bool:
        """
        Unsubscribe from market data.
        
        Args:
            tokens: List of symbol tokens to unsubscribe
            
        Returns:
            True if unsubscription successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_ltp(self, token: str) -> Optional[float]:
        """
        Get the last traded price for a token.
        
        Args:
            token: Symbol token
            
        Returns:
            LTP value or None if not available
        """
        pass
    
    @abstractmethod
    def get_quote(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get the full quote for a token.
        
        Args:
            token: Symbol token
            
        Returns:
            Quote dictionary or None if not available
        """
        pass
    
    def register_tick_callback(self, callback: Callable) -> None:
        """
        Register a callback for tick data.
        
        Args:
            callback: Callable that receives tick data dict
        """
        if callback not in self._tick_callbacks:
            self._tick_callbacks.append(callback)
            logger.debug(f"Registered tick callback: {callback}")
    
    def unregister_tick_callback(self, callback: Callable) -> None:
        """
        Unregister a tick callback.
        
        Args:
            callback: Callback to remove
        """
        if callback in self._tick_callbacks:
            self._tick_callbacks.remove(callback)
            logger.debug(f"Unregistered tick callback: {callback}")
    
    def _notify_tick(self, tick_data: Dict[str, Any]) -> None:
        """
        Notify all registered callbacks with tick data.
        
        Args:
            tick_data: Tick data dictionary
        """
        for callback in self._tick_callbacks:
            try:
                callback(tick_data)
            except Exception as e:
                logger.exception(f"Tick callback exception: {e}")
    
    @abstractmethod
    def get_subscribed_tokens(self) -> List[str]:
        """
        Get list of currently subscribed tokens.
        
        Returns:
            List of subscribed token strings
        """
        pass
