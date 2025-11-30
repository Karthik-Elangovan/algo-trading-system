"""
Real-Time Data Manager Module.

Provides a unified interface for real-time market data streaming,
with support for multiple data providers and event-driven callbacks.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from .providers.base_provider import DataProvider

logger = logging.getLogger(__name__)


class RealTimeDataManager:
    """
    Unified interface for real-time market data.
    
    Features:
    - Support for multiple data providers
    - Event-driven architecture with callbacks
    - Thread-safe data storage and retrieval
    - Automatic reconnection handling
    - Rate limiting and throttling
    
    Example:
        >>> from src.data.providers import MockDataProvider
        >>> provider = MockDataProvider()
        >>> manager = RealTimeDataManager(provider)
        >>> manager.start()
        >>> manager.subscribe(['NIFTY', 'BANKNIFTY'])
        >>> manager.register_callback('tick', lambda data: print(data))
    """
    
    # Event types
    EVENT_TICK = 'tick'
    EVENT_CONNECT = 'connect'
    EVENT_DISCONNECT = 'disconnect'
    EVENT_ERROR = 'error'
    EVENT_SUBSCRIBE = 'subscribe'
    EVENT_UNSUBSCRIBE = 'unsubscribe'
    
    def __init__(
        self,
        provider: DataProvider,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the RealTimeDataManager.
        
        Args:
            provider: Data provider instance
            config: Optional configuration dictionary with options:
                - reconnect_attempts: Max reconnection attempts (default: 5)
                - reconnect_delay: Delay between reconnects in seconds (default: 5)
                - tick_throttle_ms: Minimum ms between tick callbacks (default: 100)
                - default_mode: Default subscription mode (default: 'ltp')
        """
        self._provider = provider
        self._config = config or {}
        
        # Configuration
        self._reconnect_attempts = self._config.get('reconnect_attempts', 5)
        self._reconnect_delay = self._config.get('reconnect_delay', 5)
        self._tick_throttle_ms = self._config.get('tick_throttle_ms', 100)
        self._default_mode = self._config.get('default_mode', 'ltp')
        
        # Internal state
        self._is_running = False
        self._callbacks: Dict[str, List[Callable]] = {
            self.EVENT_TICK: [],
            self.EVENT_CONNECT: [],
            self.EVENT_DISCONNECT: [],
            self.EVENT_ERROR: [],
            self.EVENT_SUBSCRIBE: [],
            self.EVENT_UNSUBSCRIBE: [],
        }
        self._subscriptions: Set[str] = set()
        self._last_tick_time: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._reconnect_thread: Optional[threading.Thread] = None
        self._current_reconnect_attempts = 0
        
        # Register provider callbacks
        self._provider.register_tick_callback(self._on_tick)
        
        logger.info("Initialized RealTimeDataManager")
    
    @property
    def is_running(self) -> bool:
        """Check if the manager is running."""
        return self._is_running
    
    @property
    def is_connected(self) -> bool:
        """Check if the provider is connected."""
        return self._provider.is_connected
    
    def start(self) -> bool:
        """
        Start the real-time data manager.
        
        Connects to the data provider.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self._is_running:
            logger.warning("Manager already running")
            return True
        
        logger.info("Starting RealTimeDataManager")
        
        result = self._provider.connect()
        
        if result:
            self._is_running = True
            self._current_reconnect_attempts = 0
            self._notify_event(self.EVENT_CONNECT, {
                'timestamp': datetime.now().isoformat()
            })
            logger.info("RealTimeDataManager started successfully")
        else:
            logger.error("Failed to start RealTimeDataManager")
        
        return result
    
    def stop(self) -> bool:
        """
        Stop the real-time data manager.
        
        Disconnects from the data provider.
        
        Returns:
            True if stopped successfully, False otherwise
        """
        if not self._is_running:
            return True
        
        logger.info("Stopping RealTimeDataManager")
        
        result = self._provider.disconnect()
        
        self._is_running = False
        self._subscriptions.clear()
        self._last_tick_time.clear()
        
        self._notify_event(self.EVENT_DISCONNECT, {
            'timestamp': datetime.now().isoformat()
        })
        
        logger.info("RealTimeDataManager stopped")
        return result
    
    def subscribe(
        self,
        symbols: List[str],
        mode: str = 'ltp'
    ) -> bool:
        """
        Subscribe to market data for given symbols.
        
        Args:
            symbols: List of symbols to subscribe
            mode: Subscription mode ('ltp', 'quote', 'depth')
            
        Returns:
            True if subscription successful, False otherwise
        """
        if not self._is_running:
            logger.warning("Cannot subscribe: manager not running")
            return False
        
        # Map mode string to provider constant
        mode_map = {
            'ltp': DataProvider.FEED_MODE_LTP,
            'quote': DataProvider.FEED_MODE_QUOTE,
            'depth': DataProvider.FEED_MODE_DEPTH,
        }
        feed_mode = mode_map.get(mode.lower(), DataProvider.FEED_MODE_LTP)
        
        result = self._provider.subscribe(symbols, feed_mode)
        
        if result:
            with self._lock:
                self._subscriptions.update(symbols)
            
            self._notify_event(self.EVENT_SUBSCRIBE, {
                'symbols': symbols,
                'mode': mode,
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"Subscribed to {len(symbols)} symbols in {mode} mode")
        
        return result
    
    def unsubscribe(self, symbols: List[str]) -> bool:
        """
        Unsubscribe from market data.
        
        Args:
            symbols: List of symbols to unsubscribe
            
        Returns:
            True if unsubscription successful, False otherwise
        """
        result = self._provider.unsubscribe(symbols)
        
        if result:
            with self._lock:
                self._subscriptions.difference_update(symbols)
            
            self._notify_event(self.EVENT_UNSUBSCRIBE, {
                'symbols': symbols,
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"Unsubscribed from {len(symbols)} symbols")
        
        return result
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """
        Get the last traded price for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            LTP value or None if not available
        """
        return self._provider.get_ltp(symbol)
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get the full quote for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Quote dictionary or None if not available
        """
        return self._provider.get_quote(symbol)
    
    def register_callback(
        self,
        event: str,
        callback: Callable
    ) -> None:
        """
        Register a callback for an event.
        
        Args:
            event: Event type ('tick', 'connect', 'disconnect', 'error',
                   'subscribe', 'unsubscribe')
            callback: Callable to invoke when event occurs
        """
        if event not in self._callbacks:
            logger.warning(f"Unknown event type: {event}")
            return
        
        if callback not in self._callbacks[event]:
            self._callbacks[event].append(callback)
            logger.debug(f"Registered callback for event: {event}")
    
    def unregister_callback(
        self,
        event: str,
        callback: Callable
    ) -> None:
        """
        Unregister a callback for an event.
        
        Args:
            event: Event type
            callback: Callback to remove
        """
        if event in self._callbacks and callback in self._callbacks[event]:
            self._callbacks[event].remove(callback)
            logger.debug(f"Unregistered callback for event: {event}")
    
    def get_all_subscriptions(self) -> List[str]:
        """
        Get all current subscriptions.
        
        Returns:
            List of subscribed symbols
        """
        with self._lock:
            return list(self._subscriptions)
    
    def get_all_ltp(self) -> Dict[str, float]:
        """
        Get LTP for all subscribed symbols.
        
        Returns:
            Dictionary of symbol -> LTP
        """
        with self._lock:
            symbols = list(self._subscriptions)
        
        result = {}
        for symbol in symbols:
            ltp = self._provider.get_ltp(symbol)
            if ltp is not None:
                result[symbol] = ltp
        
        return result
    
    def _on_tick(self, tick_data: Dict[str, Any]) -> None:
        """
        Handle incoming tick data from provider.
        
        Applies throttling and notifies callbacks.
        
        Args:
            tick_data: Tick data dictionary
        """
        token = tick_data.get('token', '')
        current_time = time.time() * 1000  # Convert to ms
        
        # Apply throttling
        with self._lock:
            last_time = self._last_tick_time.get(token, 0)
            
            if current_time - last_time < self._tick_throttle_ms:
                return  # Skip this tick due to throttling
            
            self._last_tick_time[token] = current_time
        
        # Notify callbacks
        self._notify_event(self.EVENT_TICK, tick_data)
    
    def _notify_event(
        self,
        event: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Notify all registered callbacks for an event.
        
        Args:
            event: Event type
            data: Event data dictionary
        """
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.exception(f"Callback exception for {event}: {e}")
    
    def _handle_disconnect(self) -> None:
        """Handle provider disconnection with auto-reconnect."""
        if not self._is_running:
            return
        
        self._notify_event(self.EVENT_DISCONNECT, {
            'timestamp': datetime.now().isoformat()
        })
        
        # Attempt reconnection
        if self._current_reconnect_attempts < self._reconnect_attempts:
            self._schedule_reconnect()
    
    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return
        
        self._current_reconnect_attempts += 1
        logger.info(
            f"Scheduling reconnection attempt "
            f"{self._current_reconnect_attempts}/{self._reconnect_attempts}"
        )
        
        def reconnect():
            time.sleep(self._reconnect_delay)
            if self._is_running and not self._provider.is_connected:
                if self._provider.connect():
                    self._current_reconnect_attempts = 0
                    self._notify_event(self.EVENT_CONNECT, {
                        'reconnected': True,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # Resubscribe to previous subscriptions
                    with self._lock:
                        symbols = list(self._subscriptions)
                    
                    if symbols:
                        self._provider.subscribe(
                            symbols,
                            DataProvider.FEED_MODE_LTP
                        )
                else:
                    self._schedule_reconnect()
        
        self._reconnect_thread = threading.Thread(target=reconnect, daemon=True)
        self._reconnect_thread.start()
