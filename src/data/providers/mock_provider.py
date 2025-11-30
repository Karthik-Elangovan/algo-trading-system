"""
Mock Data Provider for Testing.

Generates simulated real-time market data for testing purposes.
"""

import logging
import threading
import time
import random
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from .base_provider import DataProvider

logger = logging.getLogger(__name__)


class MockDataProvider(DataProvider):
    """
    Mock data provider that generates simulated real-time data.
    
    Useful for:
    - Testing strategies without live data
    - Development and debugging
    - Backtesting with simulated ticks
    """
    
    # Default base prices for common instruments
    DEFAULT_BASE_PRICES = {
        'NIFTY': 24200.0,
        'BANKNIFTY': 52000.0,
        'SENSEX': 80000.0,
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize mock data provider.
        
        Args:
            config: Configuration dictionary with options:
                - tick_interval_ms: Milliseconds between ticks (default: 500)
                - price_volatility: Price change volatility (default: 0.001)
                - base_prices: Dict of token -> base price
                - simulate_market_hours: Simulate market hours (default: False)
        """
        super().__init__(config)
        
        self._tick_interval_ms = self._config.get('tick_interval_ms', 500)
        self._price_volatility = self._config.get('price_volatility', 0.001)
        self._base_prices = self._config.get('base_prices', {})
        self._simulate_market_hours = self._config.get('simulate_market_hours', False)
        
        # Internal state
        self._subscribed_tokens: Set[str] = set()
        self._current_prices: Dict[str, float] = {}
        self._quote_data: Dict[str, Dict[str, Any]] = {}
        self._stop_event = threading.Event()
        self._tick_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        logger.info("Initialized MockDataProvider")
    
    def connect(self) -> bool:
        """
        Connect to the mock data source.
        
        Starts the tick generation thread.
        
        Returns:
            True (always succeeds for mock)
        """
        if self._is_connected:
            return True
        
        self._is_connected = True
        self._stop_event.clear()
        
        logger.info("MockDataProvider connected")
        return True
    
    def disconnect(self) -> bool:
        """
        Disconnect from the mock data source.
        
        Stops the tick generation thread.
        
        Returns:
            True (always succeeds for mock)
        """
        self._stop_event.set()
        
        if self._tick_thread and self._tick_thread.is_alive():
            self._tick_thread.join(timeout=2.0)
        
        self._is_connected = False
        self._subscribed_tokens.clear()
        self._current_prices.clear()
        self._quote_data.clear()
        
        logger.info("MockDataProvider disconnected")
        return True
    
    def subscribe(self, tokens: List[str], mode: int = 1) -> bool:
        """
        Subscribe to market data for given tokens.
        
        Args:
            tokens: List of symbol tokens to subscribe
            mode: Feed mode (not used in mock, all data is generated)
            
        Returns:
            True if subscription successful
        """
        if not self._is_connected:
            logger.warning("Cannot subscribe: not connected")
            return False
        
        with self._lock:
            for token in tokens:
                self._subscribed_tokens.add(token)
                
                # Initialize price if not set
                if token not in self._current_prices:
                    base_price = self._get_base_price(token)
                    self._current_prices[token] = base_price
                    self._initialize_quote(token, base_price)
        
        # Start tick generation if not already running
        if not self._tick_thread or not self._tick_thread.is_alive():
            self._tick_thread = threading.Thread(
                target=self._generate_ticks,
                daemon=True
            )
            self._tick_thread.start()
        
        logger.info(f"Subscribed to {len(tokens)} tokens (total: {len(self._subscribed_tokens)})")
        return True
    
    def unsubscribe(self, tokens: List[str]) -> bool:
        """
        Unsubscribe from market data.
        
        Args:
            tokens: List of symbol tokens to unsubscribe
            
        Returns:
            True if unsubscription successful
        """
        with self._lock:
            for token in tokens:
                self._subscribed_tokens.discard(token)
                self._current_prices.pop(token, None)
                self._quote_data.pop(token, None)
        
        logger.info(f"Unsubscribed from {len(tokens)} tokens")
        return True
    
    def get_ltp(self, token: str) -> Optional[float]:
        """
        Get the last traded price for a token.
        
        Args:
            token: Symbol token
            
        Returns:
            LTP value or None if not subscribed
        """
        with self._lock:
            return self._current_prices.get(token)
    
    def get_quote(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get the full quote for a token.
        
        Args:
            token: Symbol token
            
        Returns:
            Quote dictionary or None if not subscribed
        """
        with self._lock:
            return self._quote_data.get(token, {}).copy() if token in self._quote_data else None
    
    def get_subscribed_tokens(self) -> List[str]:
        """
        Get list of currently subscribed tokens.
        
        Returns:
            List of subscribed token strings
        """
        with self._lock:
            return list(self._subscribed_tokens)
    
    def set_price(self, token: str, price: float) -> None:
        """
        Manually set price for a token (for testing).
        
        Args:
            token: Symbol token
            price: Price to set
        """
        with self._lock:
            self._current_prices[token] = price
            if token in self._quote_data:
                self._quote_data[token]['ltp'] = price
    
    def _get_base_price(self, token: str) -> float:
        """Get base price for a token."""
        # Check custom base prices first
        if token in self._base_prices:
            return self._base_prices[token]
        
        # Check default prices based on token name
        for name, price in self.DEFAULT_BASE_PRICES.items():
            if name in token.upper():
                return price
        
        # Default price for options (smaller values)
        if any(x in token.upper() for x in ['CE', 'PE']):
            return random.uniform(50, 500)
        
        # Default for unknown tokens
        return random.uniform(100, 1000)
    
    def _initialize_quote(self, token: str, price: float) -> None:
        """Initialize quote data for a token."""
        self._quote_data[token] = {
            'token': token,
            'ltp': price,
            'open': price * (1 + random.uniform(-0.005, 0.005)),
            'high': price * (1 + random.uniform(0, 0.01)),
            'low': price * (1 - random.uniform(0, 0.01)),
            'close': price * (1 + random.uniform(-0.005, 0.005)),
            'volume': random.randint(10000, 500000),
            'timestamp': datetime.now().isoformat()
        }
    
    def _generate_ticks(self) -> None:
        """Generate tick data for all subscribed tokens."""
        logger.debug("Starting tick generation thread")
        
        while not self._stop_event.is_set():
            # Check market hours if enabled
            if self._simulate_market_hours and not self._is_market_hours():
                time.sleep(1)
                continue
            
            with self._lock:
                tokens = list(self._subscribed_tokens)
            
            for token in tokens:
                if self._stop_event.is_set():
                    break
                
                tick_data = self._generate_tick(token)
                if tick_data:
                    self._notify_tick(tick_data)
            
            # Sleep for tick interval
            time.sleep(self._tick_interval_ms / 1000.0)
        
        logger.debug("Tick generation thread stopped")
    
    def _generate_tick(self, token: str) -> Optional[Dict[str, Any]]:
        """Generate a single tick for a token."""
        with self._lock:
            if token not in self._current_prices:
                return None
            
            current_price = self._current_prices[token]
            
            # Generate random price change
            change_pct = random.gauss(0, self._price_volatility)
            new_price = current_price * (1 + change_pct)
            new_price = max(0.05, new_price)  # Price floor
            
            # Update price
            self._current_prices[token] = new_price
            
            # Update quote data
            if token in self._quote_data:
                quote = self._quote_data[token]
                quote['ltp'] = new_price
                quote['high'] = max(quote['high'], new_price)
                quote['low'] = min(quote['low'], new_price)
                quote['volume'] += random.randint(10, 1000)
                quote['timestamp'] = datetime.now().isoformat()
            
            tick_data = {
                'token': token,
                'ltp': round(new_price, 2),
                'change': round((new_price - current_price), 2),
                'change_pct': round(change_pct * 100, 4),
                'volume': self._quote_data.get(token, {}).get('volume', 0),
                'timestamp': datetime.now().isoformat()
            }
            
            return tick_data
    
    def _is_market_hours(self) -> bool:
        """Check if current time is within market hours (9:15 AM - 3:30 PM IST)."""
        now = datetime.now()
        
        # Skip weekends
        if now.weekday() >= 5:
            return False
        
        # Check time (assuming IST)
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_open <= now <= market_close
