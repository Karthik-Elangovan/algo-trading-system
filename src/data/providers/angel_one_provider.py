"""
Angel One Data Provider.

Implements the DataProvider interface using Angel One's WebSocket API.
"""

import logging
from typing import Any, Dict, List, Optional

from .base_provider import DataProvider

logger = logging.getLogger(__name__)


class AngelOneDataProvider(DataProvider):
    """
    Data provider that connects to Angel One's WebSocket API.
    
    Wraps the existing AngelOneWebSocket to provide a consistent
    interface with the RealTimeDataManager.
    """
    
    def __init__(
        self,
        auth_token: str,
        api_key: str,
        client_code: str,
        feed_token: str,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Angel One data provider.
        
        Args:
            auth_token: JWT authentication token
            api_key: API key
            client_code: Client code
            feed_token: Feed token for WebSocket
            config: Optional configuration dictionary
        """
        super().__init__(config)
        
        self._auth_token = auth_token
        self._api_key = api_key
        self._client_code = client_code
        self._feed_token = feed_token
        self._websocket = None
        self._subscribed_tokens: List[str] = []
        self._current_mode = self.FEED_MODE_LTP
        
        logger.info("Initialized AngelOneDataProvider")
    
    def connect(self) -> bool:
        """
        Connect to Angel One WebSocket.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            from src.execution.angel_one.websocket import AngelOneWebSocket
            
            self._websocket = AngelOneWebSocket(
                auth_token=self._auth_token,
                api_key=self._api_key,
                client_code=self._client_code,
                feed_token=self._feed_token,
                config=self._config
            )
            
            # Register our tick handler
            self._websocket.register_callback('tick', self._on_tick)
            self._websocket.register_callback('connect', self._on_connect)
            self._websocket.register_callback('disconnect', self._on_disconnect)
            self._websocket.register_callback('error', self._on_error)
            
            result = self._websocket.connect()
            
            if result:
                self._is_connected = True
                logger.info("AngelOneDataProvider connected")
            else:
                logger.error("Failed to connect AngelOneDataProvider")
            
            return result
            
        except ImportError as e:
            logger.error(f"Import error: {e}")
            return False
        except Exception as e:
            logger.exception(f"Connect exception: {e}")
            return False
    
    def disconnect(self) -> bool:
        """
        Disconnect from Angel One WebSocket.
        
        Returns:
            True if disconnection successful, False otherwise
        """
        try:
            if self._websocket:
                self._websocket.disconnect()
            
            self._is_connected = False
            self._subscribed_tokens.clear()
            
            logger.info("AngelOneDataProvider disconnected")
            return True
            
        except Exception as e:
            logger.exception(f"Disconnect exception: {e}")
            return False
    
    def subscribe(self, tokens: List[str], mode: int = 1) -> bool:
        """
        Subscribe to market data for given tokens.
        
        Args:
            tokens: List of symbol tokens to subscribe
            mode: Feed mode (1=LTP, 2=Quote, 3=Depth)
            
        Returns:
            True if subscription successful, False otherwise
        """
        if not self._is_connected or not self._websocket:
            logger.warning("Cannot subscribe: not connected")
            return False
        
        try:
            # Angel One expects tokens in specific format
            # Default to NFO (exchange type 2)
            exchange_type = self._config.get('exchange_type', 2)
            
            token_list = [{"exchangeType": exchange_type, "tokens": tokens}]
            
            result = self._websocket.subscribe(token_list, mode)
            
            if result:
                self._subscribed_tokens.extend(tokens)
                self._current_mode = mode
                logger.info(f"Subscribed to {len(tokens)} tokens in mode {mode}")
            
            return result
            
        except Exception as e:
            logger.exception(f"Subscribe exception: {e}")
            return False
    
    def unsubscribe(self, tokens: List[str]) -> bool:
        """
        Unsubscribe from market data.
        
        Args:
            tokens: List of symbol tokens to unsubscribe
            
        Returns:
            True if unsubscription successful, False otherwise
        """
        if not self._websocket:
            return True
        
        try:
            exchange_type = self._config.get('exchange_type', 2)
            token_list = [{"exchangeType": exchange_type, "tokens": tokens}]
            
            result = self._websocket.unsubscribe(token_list, self._current_mode)
            
            if result:
                for token in tokens:
                    if token in self._subscribed_tokens:
                        self._subscribed_tokens.remove(token)
            
            return result
            
        except Exception as e:
            logger.exception(f"Unsubscribe exception: {e}")
            return False
    
    def get_ltp(self, token: str) -> Optional[float]:
        """
        Get the last traded price for a token.
        
        Args:
            token: Symbol token
            
        Returns:
            LTP value or None if not available
        """
        if not self._websocket:
            return None
        
        return self._websocket.get_ltp(token)
    
    def get_quote(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get the full quote for a token.
        
        Args:
            token: Symbol token
            
        Returns:
            Quote dictionary or None if not available
        """
        if not self._websocket:
            return None
        
        return self._websocket.get_quote(token)
    
    def get_subscribed_tokens(self) -> List[str]:
        """
        Get list of currently subscribed tokens.
        
        Returns:
            List of subscribed token strings
        """
        return self._subscribed_tokens.copy()
    
    def _on_tick(self, data: Dict[str, Any]) -> None:
        """Handle incoming tick data from WebSocket."""
        # Transform data if needed and notify callbacks
        # Note: Angel One returns prices in paise (1/100 of rupee)
        raw_ltp = data.get('last_traded_price', 0)
        ltp = data.get('ltp', raw_ltp / 100 if raw_ltp else None)
        
        tick_data = {
            'token': str(data.get('token', '')),
            'ltp': ltp,
            'volume': data.get('volume_trade_for_the_day', 0),
            'timestamp': data.get('timestamp'),
        }
        
        # Add quote data if available (convert from paise to rupees)
        if 'open_price_of_the_day' in data:
            open_price = data.get('open_price_of_the_day', 0)
            high_price = data.get('high_price_of_the_day', 0)
            low_price = data.get('low_price_of_the_day', 0)
            close_price = data.get('closed_price', 0)
            
            tick_data['open'] = open_price / 100 if open_price else None
            tick_data['high'] = high_price / 100 if high_price else None
            tick_data['low'] = low_price / 100 if low_price else None
            tick_data['close'] = close_price / 100 if close_price else None
        
        self._notify_tick(tick_data)
    
    def _on_connect(self) -> None:
        """Handle WebSocket connection event."""
        self._is_connected = True
        logger.info("AngelOne WebSocket connected")
    
    def _on_disconnect(self) -> None:
        """Handle WebSocket disconnection event."""
        self._is_connected = False
        logger.warning("AngelOne WebSocket disconnected")
    
    def _on_error(self, error: Any) -> None:
        """Handle WebSocket error event."""
        logger.error(f"AngelOne WebSocket error: {error}")
