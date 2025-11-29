"""
Angel One WebSocket Handler.

Handles real-time market data streaming via WebSocket.
"""

import json
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AngelOneWebSocket:
    """
    Handles WebSocket connection for real-time market data.
    
    Supports:
    - LTP (Last Traded Price) streaming
    - Full market depth (Level 2)
    - Snapshot mode
    - Auto-reconnection
    """
    
    # Feed modes
    FEED_MODE_LTP = 1        # LTP mode - only last traded price
    FEED_MODE_QUOTE = 2      # Quote mode - LTP + OHLC + volume
    FEED_MODE_DEPTH = 3      # Full depth mode - 5 best bid/ask
    
    def __init__(
        self,
        auth_token: str,
        api_key: str,
        client_code: str,
        feed_token: str,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize WebSocket handler.
        
        Args:
            auth_token: JWT authentication token
            api_key: API key
            client_code: Client code
            feed_token: Feed token for WebSocket
            config: Optional configuration
        """
        self._auth_token = auth_token
        self._api_key = api_key
        self._client_code = client_code
        self._feed_token = feed_token
        self._config = config or {}
        
        self._ws = None
        self._smart_api_ws = None
        self._is_connected = False
        self._subscribed_tokens: Set[str] = set()
        self._callbacks: Dict[str, Callable] = {}
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 5  # seconds
        
        # Data storage
        self._ltp_data: Dict[str, float] = {}
        self._quote_data: Dict[str, Dict[str, Any]] = {}
        self._depth_data: Dict[str, Dict[str, Any]] = {}
        
        logger.info("Initialized AngelOneWebSocket")
    
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._is_connected
    
    def connect(self) -> bool:
        """
        Connect to WebSocket server.
        
        Returns:
            True if connection successful
        """
        try:
            from SmartApi.smartWebSocketV2 import SmartWebSocketV2
            
            self._smart_api_ws = SmartWebSocketV2(
                auth_token=self._auth_token,
                api_key=self._api_key,
                client_code=self._client_code,
                feed_token=self._feed_token
            )
            
            # Set up callbacks
            self._smart_api_ws.on_open = self._on_open
            self._smart_api_ws.on_data = self._on_data
            self._smart_api_ws.on_error = self._on_error
            self._smart_api_ws.on_close = self._on_close
            
            # Connect in a separate thread
            self._ws_thread = threading.Thread(
                target=self._smart_api_ws.connect,
                daemon=True
            )
            self._ws_thread.start()
            
            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self._is_connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            return self._is_connected
            
        except ImportError:
            logger.error("SmartApi package not installed")
            return False
        except Exception as e:
            logger.exception(f"WebSocket connect exception: {e}")
            return False
    
    def disconnect(self) -> bool:
        """
        Disconnect from WebSocket server.
        
        Returns:
            True if disconnection successful
        """
        try:
            if self._smart_api_ws:
                self._smart_api_ws.close_connection()
            
            self._is_connected = False
            self._subscribed_tokens.clear()
            
            logger.info("WebSocket disconnected")
            return True
            
        except Exception as e:
            logger.exception(f"WebSocket disconnect exception: {e}")
            return False
    
    def subscribe(
        self,
        tokens: List[Dict[str, Any]],
        mode: int = 1
    ) -> bool:
        """
        Subscribe to market data for given tokens.
        
        Args:
            tokens: List of token dictionaries with format:
                    [{"exchangeType": 2, "tokens": ["26000", "26009"]}]
                    Exchange types: 1=NSE, 2=NFO, 3=BSE, 4=BFO, 5=MCX, 6=CDS
            mode: Feed mode (1=LTP, 2=Quote, 3=Depth)
            
        Returns:
            True if subscription successful
        """
        if not self._is_connected or not self._smart_api_ws:
            logger.warning("WebSocket not connected")
            return False
        
        try:
            self._smart_api_ws.subscribe(tokens, mode)
            
            # Track subscribed tokens
            for token_group in tokens:
                for token in token_group.get('tokens', []):
                    self._subscribed_tokens.add(f"{token_group['exchangeType']}:{token}")
            
            logger.info(f"Subscribed to {len(self._subscribed_tokens)} tokens in mode {mode}")
            return True
            
        except Exception as e:
            logger.exception(f"Subscribe exception: {e}")
            return False
    
    def unsubscribe(
        self,
        tokens: List[Dict[str, Any]],
        mode: int = 1
    ) -> bool:
        """
        Unsubscribe from market data.
        
        Args:
            tokens: List of token dictionaries
            mode: Feed mode
            
        Returns:
            True if unsubscription successful
        """
        if not self._is_connected or not self._smart_api_ws:
            return True
        
        try:
            self._smart_api_ws.unsubscribe(tokens, mode)
            
            # Remove from tracking
            for token_group in tokens:
                for token in token_group.get('tokens', []):
                    self._subscribed_tokens.discard(f"{token_group['exchangeType']}:{token}")
            
            logger.info(f"Unsubscribed from tokens")
            return True
            
        except Exception as e:
            logger.exception(f"Unsubscribe exception: {e}")
            return False
    
    def subscribe_ltp(self, symbol_tokens: List[str], exchange_type: int = 2) -> bool:
        """
        Subscribe to LTP updates for symbols.
        
        Args:
            symbol_tokens: List of symbol tokens
            exchange_type: Exchange type (default NFO=2)
            
        Returns:
            True if successful
        """
        tokens = [{"exchangeType": exchange_type, "tokens": symbol_tokens}]
        return self.subscribe(tokens, mode=self.FEED_MODE_LTP)
    
    def subscribe_quote(self, symbol_tokens: List[str], exchange_type: int = 2) -> bool:
        """
        Subscribe to quote updates for symbols.
        
        Args:
            symbol_tokens: List of symbol tokens
            exchange_type: Exchange type
            
        Returns:
            True if successful
        """
        tokens = [{"exchangeType": exchange_type, "tokens": symbol_tokens}]
        return self.subscribe(tokens, mode=self.FEED_MODE_QUOTE)
    
    def subscribe_depth(self, symbol_tokens: List[str], exchange_type: int = 2) -> bool:
        """
        Subscribe to market depth updates for symbols.
        
        Args:
            symbol_tokens: List of symbol tokens
            exchange_type: Exchange type
            
        Returns:
            True if successful
        """
        tokens = [{"exchangeType": exchange_type, "tokens": symbol_tokens}]
        return self.subscribe(tokens, mode=self.FEED_MODE_DEPTH)
    
    def get_ltp(self, token: str) -> Optional[float]:
        """
        Get cached LTP for a token.
        
        Args:
            token: Symbol token
            
        Returns:
            LTP value or None
        """
        return self._ltp_data.get(token)
    
    def get_quote(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get cached quote for a token.
        
        Args:
            token: Symbol token
            
        Returns:
            Quote dictionary or None
        """
        return self._quote_data.get(token)
    
    def get_depth(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get cached market depth for a token.
        
        Args:
            token: Symbol token
            
        Returns:
            Depth dictionary or None
        """
        return self._depth_data.get(token)
    
    def register_callback(self, event: str, callback: Callable) -> None:
        """
        Register callback for an event.
        
        Args:
            event: Event name ('tick', 'connect', 'disconnect', 'error')
            callback: Callback function
        """
        self._callbacks[event] = callback
        logger.debug(f"Registered callback for event: {event}")
    
    def _on_open(self, ws) -> None:
        """Handle WebSocket connection opened."""
        self._is_connected = True
        self._reconnect_attempts = 0
        logger.info("WebSocket connected")
        
        if 'connect' in self._callbacks:
            try:
                self._callbacks['connect']()
            except Exception as e:
                logger.exception(f"Connect callback exception: {e}")
    
    def _on_data(self, ws, data) -> None:
        """
        Handle incoming WebSocket data.
        
        Args:
            ws: WebSocket instance
            data: Received data
        """
        try:
            if isinstance(data, dict):
                token = str(data.get('token', ''))
                
                # Update LTP
                if 'last_traded_price' in data:
                    ltp = data['last_traded_price'] / 100  # Price is in paise
                    self._ltp_data[token] = ltp
                    data['ltp'] = ltp
                
                # Update quote data
                if any(k in data for k in ['open_price_of_the_day', 'high_price_of_the_day']):
                    self._quote_data[token] = {
                        'ltp': data.get('last_traded_price', 0) / 100,
                        'open': data.get('open_price_of_the_day', 0) / 100,
                        'high': data.get('high_price_of_the_day', 0) / 100,
                        'low': data.get('low_price_of_the_day', 0) / 100,
                        'close': data.get('closed_price', 0) / 100,
                        'volume': data.get('volume_trade_for_the_day', 0),
                        'timestamp': datetime.now().isoformat()
                    }
                
                # Update depth data
                if 'best_5_buy_data' in data or 'best_5_sell_data' in data:
                    self._depth_data[token] = {
                        'bids': data.get('best_5_buy_data', []),
                        'asks': data.get('best_5_sell_data', []),
                        'timestamp': datetime.now().isoformat()
                    }
                
                # Call tick callback
                if 'tick' in self._callbacks:
                    try:
                        self._callbacks['tick'](data)
                    except Exception as e:
                        logger.exception(f"Tick callback exception: {e}")
                        
        except Exception as e:
            logger.exception(f"Data processing exception: {e}")
    
    def _on_error(self, ws, error) -> None:
        """Handle WebSocket error."""
        logger.error(f"WebSocket error: {error}")
        
        if 'error' in self._callbacks:
            try:
                self._callbacks['error'](error)
            except Exception as e:
                logger.exception(f"Error callback exception: {e}")
    
    def _on_close(self, ws, close_status_code, close_msg) -> None:
        """Handle WebSocket connection closed."""
        self._is_connected = False
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        
        if 'disconnect' in self._callbacks:
            try:
                self._callbacks['disconnect']()
            except Exception as e:
                logger.exception(f"Disconnect callback exception: {e}")
        
        # Attempt reconnection
        if self._reconnect_attempts < self._max_reconnect_attempts:
            self._reconnect_attempts += 1
            logger.info(f"Attempting reconnection ({self._reconnect_attempts}/{self._max_reconnect_attempts})")
            time.sleep(self._reconnect_delay)
            self.connect()
    
    def get_subscribed_count(self) -> int:
        """Get count of subscribed tokens."""
        return len(self._subscribed_tokens)
    
    def get_all_ltp(self) -> Dict[str, float]:
        """Get all cached LTP data."""
        return self._ltp_data.copy()
