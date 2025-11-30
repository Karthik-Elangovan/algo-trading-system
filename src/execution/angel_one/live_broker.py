"""
Angel One Live Broker Implementation.

Complete broker implementation using Angel One SmartAPI.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..broker import (
    BaseBroker,
    BrokerFactory,
    Order,
    Position,
    Holding,
    Quote,
    AccountInfo,
)
from .auth import AngelOneAuth
from .market_data import AngelOneMarketData
from .orders import AngelOneOrders
from .positions import AngelOnePositions
from .account import AngelOneAccount
from .websocket import AngelOneWebSocket

logger = logging.getLogger(__name__)


class AngelOneBroker(BaseBroker):
    """
    Angel One live trading broker implementation.
    
    Provides complete integration with Angel One SmartAPI for:
    - Authentication with TOTP
    - Real-time market data
    - Order execution
    - Position management
    - Account management
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Angel One broker.
        
        Args:
            config: Configuration dictionary with API credentials
        """
        super().__init__(config)
        
        self._auth: Optional[AngelOneAuth] = None
        self._market_data: Optional[AngelOneMarketData] = None
        self._orders: Optional[AngelOneOrders] = None
        self._positions: Optional[AngelOnePositions] = None
        self._account: Optional[AngelOneAccount] = None
        self._websocket: Optional[AngelOneWebSocket] = None
        
        logger.info("Initialized AngelOneBroker")
    
    # ==================== Authentication ====================
    
    def login(self, totp: Optional[str] = None) -> bool:
        """
        Authenticate with Angel One.
        
        Args:
            totp: TOTP code (auto-generated if configured)
            
        Returns:
            True if login successful
        """
        try:
            self._auth = AngelOneAuth(self.config)
            result = self._auth.login(totp=totp)
            
            if result.get('status'):
                # Initialize all modules with authenticated SmartAPI
                smart_api = self._auth.smart_api
                
                self._market_data = AngelOneMarketData(smart_api, self.config)
                self._orders = AngelOneOrders(smart_api, self.config)
                self._positions = AngelOnePositions(smart_api, self.config)
                self._account = AngelOneAccount(smart_api, {
                    **self.config,
                    'refresh_token': self._auth._refresh_token
                })
                
                # Store tokens
                self._session_token = self._auth.session_token
                self._feed_token = self._auth.feed_token
                self._is_authenticated = True
                
                logger.info("Angel One login successful")
                return True
            else:
                logger.error(f"Angel One login failed: {result.get('message')}")
                return False
                
        except Exception as e:
            logger.exception(f"Login exception: {e}")
            return False
    
    def logout(self) -> bool:
        """Logout from Angel One."""
        if self._auth:
            result = self._auth.logout()
            self._is_authenticated = False
            self._session_token = None
            self._feed_token = None
            return result.get('status', False)
        return True
    
    def get_profile(self) -> AccountInfo:
        """Get user profile."""
        if not self._account:
            return AccountInfo(
                client_id="",
                name="",
                broker="Angel One"
            )
        
        result = self._account.get_profile()
        if result.get('status'):
            profile = result.get('profile', {})
            margin_result = self._account.get_margin()
            margin = margin_result.get('margin', {}) if margin_result.get('status') else {}
            
            return AccountInfo(
                client_id=profile.get('client_id', ''),
                name=profile.get('name', ''),
                email=profile.get('email', ''),
                phone=profile.get('phone', ''),
                broker='Angel One',
                available_margin=margin.get('available_margin', 0),
                used_margin=margin.get('used_margin', 0),
                total_margin=margin.get('total_margin', 0),
            )
        
        return AccountInfo(client_id="", name="", broker="Angel One")
    
    # ==================== Market Data ====================
    
    def get_ltp(self, symbol: str, exchange: str) -> float:
        """Get last traded price."""
        if not self._market_data:
            return 0.0
        
        result = self._market_data.get_ltp(symbol, exchange)
        return result.get('ltp', 0.0) if result.get('status') else 0.0
    
    def get_quote(self, symbol: str, exchange: str) -> Quote:
        """Get market quote."""
        if not self._market_data:
            return Quote(symbol=symbol, exchange=exchange, ltp=0.0)
        
        result = self._market_data.get_quote(symbol, exchange)
        if result.get('status'):
            return Quote(
                symbol=symbol,
                exchange=exchange,
                ltp=result.get('ltp', 0.0),
                open=result.get('open', 0.0),
                high=result.get('high', 0.0),
                low=result.get('low', 0.0),
                close=result.get('close', 0.0),
                volume=result.get('volume', 0),
            )
        
        return Quote(symbol=symbol, exchange=exchange, ltp=0.0)
    
    def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        from_date: datetime,
        to_date: datetime,
        symbol_token: str = ""
    ) -> List[Dict[str, Any]]:
        """Get historical candle data."""
        if not self._market_data:
            return []
        
        result = self._market_data.get_historical_data(
            symbol=symbol,
            exchange=exchange,
            symbol_token=symbol_token,
            interval=interval,
            from_date=from_date,
            to_date=to_date
        )
        
        return result.get('candles', []) if result.get('status') else []
    
    # ==================== Order Management ====================
    
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
        variety: str = "NORMAL",
        symbol_token: str = ""
    ) -> str:
        """Place an order."""
        if not self._orders:
            raise RuntimeError("Broker not authenticated")
        
        result = self._orders.place_order(
            symbol=symbol,
            exchange=exchange,
            transaction_type=transaction_type,
            quantity=quantity,
            order_type=order_type,
            product_type=product_type,
            price=price,
            trigger_price=trigger_price,
            variety=variety,
            symbol_token=symbol_token
        )
        
        if result.get('status'):
            return result.get('order_id', '')
        else:
            raise RuntimeError(result.get('message', 'Order placement failed'))
    
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        order_type: Optional[str] = None
    ) -> bool:
        """Modify an order."""
        if not self._orders:
            return False
        
        result = self._orders.modify_order(
            order_id=order_id,
            quantity=quantity,
            price=price,
            trigger_price=trigger_price,
            order_type=order_type
        )
        
        return result.get('status', False)
    
    def cancel_order(self, order_id: str, variety: str = "NORMAL") -> bool:
        """Cancel an order."""
        if not self._orders:
            return False
        
        result = self._orders.cancel_order(order_id, variety)
        return result.get('status', False)
    
    def get_order_status(self, order_id: str) -> Order:
        """Get order status."""
        if not self._orders:
            raise RuntimeError("Broker not authenticated")
        
        result = self._orders.get_order_status(order_id)
        if result.get('status'):
            order_data = result.get('order', {})
            return Order(
                order_id=order_data.get('order_id', ''),
                symbol=order_data.get('symbol', ''),
                exchange=order_data.get('exchange', ''),
                transaction_type=order_data.get('transaction_type', ''),
                quantity=order_data.get('quantity', 0),
                order_type=order_data.get('order_type', ''),
                product_type=order_data.get('product_type', ''),
                price=order_data.get('price', 0),
                trigger_price=order_data.get('trigger_price', 0),
                status=order_data.get('status', ''),
                filled_quantity=order_data.get('filled_quantity', 0),
                average_price=order_data.get('average_price', 0),
            )
        
        raise RuntimeError(f"Order not found: {order_id}")
    
    def get_order_history(self) -> List[Order]:
        """Get order history."""
        if not self._orders:
            return []
        
        result = self._orders.get_order_book()
        if result.get('status'):
            orders = []
            for order_data in result.get('orders', []):
                orders.append(Order(
                    order_id=order_data.get('order_id', ''),
                    symbol=order_data.get('symbol', ''),
                    exchange=order_data.get('exchange', ''),
                    transaction_type=order_data.get('transaction_type', ''),
                    quantity=order_data.get('quantity', 0),
                    order_type=order_data.get('order_type', ''),
                    product_type=order_data.get('product_type', ''),
                    price=order_data.get('price', 0),
                    trigger_price=order_data.get('trigger_price', 0),
                    status=order_data.get('status', ''),
                    filled_quantity=order_data.get('filled_quantity', 0),
                    average_price=order_data.get('average_price', 0),
                ))
            return orders
        
        return []
    
    # ==================== Position Management ====================
    
    def get_positions(self) -> List[Position]:
        """Get current positions."""
        if not self._positions:
            return []
        
        result = self._positions.get_positions()
        if result.get('status'):
            positions = []
            for pos_data in result.get('positions', []):
                positions.append(Position(
                    symbol=pos_data.get('symbol', ''),
                    exchange=pos_data.get('exchange', ''),
                    product_type=pos_data.get('product_type', ''),
                    quantity=pos_data.get('quantity', 0),
                    average_price=pos_data.get('average_price', 0),
                    last_price=pos_data.get('last_price', 0),
                    pnl=pos_data.get('pnl', 0),
                    pnl_percentage=pos_data.get('pnl_percentage', 0),
                ))
            return positions
        
        return []
    
    def get_holdings(self) -> List[Holding]:
        """Get holdings."""
        if not self._positions:
            return []
        
        result = self._positions.get_holdings()
        if result.get('status'):
            holdings = []
            for holding_data in result.get('holdings', []):
                holdings.append(Holding(
                    symbol=holding_data.get('symbol', ''),
                    exchange=holding_data.get('exchange', ''),
                    quantity=holding_data.get('quantity', 0),
                    average_price=holding_data.get('average_price', 0),
                    last_price=holding_data.get('last_price', 0),
                    pnl=holding_data.get('pnl', 0),
                    pnl_percentage=holding_data.get('pnl_percentage', 0),
                    isin=holding_data.get('isin', ''),
                ))
            return holdings
        
        return []
    
    def convert_position(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        from_product: str,
        to_product: str
    ) -> bool:
        """Convert position product type."""
        if not self._positions:
            return False
        
        result = self._positions.convert_position(
            symbol=symbol,
            exchange=exchange,
            transaction_type=transaction_type,
            quantity=quantity,
            from_product=from_product,
            to_product=to_product
        )
        
        return result.get('status', False)
    
    def square_off_position(
        self,
        symbol: str,
        exchange: str,
        product_type: str,
        quantity: Optional[int] = None
    ) -> str:
        """Square off a position."""
        if not self._positions:
            raise RuntimeError("Broker not authenticated")
        
        result = self._positions.square_off_position(
            symbol=symbol,
            exchange=exchange,
            product_type=product_type,
            quantity=quantity
        )
        
        if result.get('status'):
            return result.get('order_id', '')
        else:
            raise RuntimeError(result.get('message', 'Square off failed'))
    
    # ==================== Account Management ====================
    
    def get_margin(self) -> Dict[str, float]:
        """Get margin information."""
        if not self._account:
            return {}
        
        result = self._account.get_margin()
        return result.get('margin', {}) if result.get('status') else {}
    
    def get_rms_limits(self) -> Dict[str, Any]:
        """Get RMS limits."""
        if not self._account:
            return {}
        
        result = self._account.get_rms_limits()
        return result.get('rms_limits', {}) if result.get('status') else {}
    
    # ==================== WebSocket ====================
    
    def connect_websocket(self) -> bool:
        """Connect to WebSocket for real-time data."""
        if not self._auth or not self._auth.is_authenticated:
            logger.error("Must be authenticated before connecting WebSocket")
            return False
        
        try:
            self._websocket = AngelOneWebSocket(
                auth_token=self._auth.jwt_token,
                api_key=self.config.get('api_key', ''),
                client_code=self.config.get('client_id', ''),
                feed_token=self._auth.feed_token,
                config=self.config
            )
            
            return self._websocket.connect()
            
        except Exception as e:
            logger.exception(f"WebSocket connection exception: {e}")
            return False
    
    def disconnect_websocket(self) -> bool:
        """Disconnect WebSocket."""
        if self._websocket:
            return self._websocket.disconnect()
        return True
    
    def subscribe_ltp(self, symbol_tokens: List[str], exchange_type: int = 2) -> bool:
        """Subscribe to LTP updates."""
        if not self._websocket:
            return False
        return self._websocket.subscribe_ltp(symbol_tokens, exchange_type)
    
    def get_websocket_ltp(self, token: str) -> Optional[float]:
        """Get LTP from WebSocket cache."""
        if not self._websocket:
            return None
        return self._websocket.get_ltp(token)


# Register with factory
BrokerFactory.register('live', AngelOneBroker)
BrokerFactory.register('angel_one', AngelOneBroker)
