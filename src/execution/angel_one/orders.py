"""
Angel One Order Execution Module.

Handles all order-related operations including placing,
modifying, and cancelling orders.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AngelOneOrders:
    """
    Handles order execution with Angel One SmartAPI.
    
    Supports:
    - Market, Limit, Stop Loss orders
    - Cover orders, Bracket orders
    - AMO (After Market Orders)
    - Order modification and cancellation
    - Order status tracking
    """
    
    # Order type mapping
    ORDER_TYPE_MAP = {
        'MARKET': 'MARKET',
        'LIMIT': 'LIMIT',
        'STOPLOSS': 'STOPLOSS_LIMIT',
        'STOPLOSS_LIMIT': 'STOPLOSS_LIMIT',
        'STOPLOSS_MARKET': 'STOPLOSS_MARKET',
        'SL': 'STOPLOSS_LIMIT',
        'SLM': 'STOPLOSS_MARKET',
    }
    
    # Product type mapping
    PRODUCT_TYPE_MAP = {
        'INTRADAY': 'INTRADAY',
        'MIS': 'INTRADAY',
        'DELIVERY': 'DELIVERY',
        'CNC': 'DELIVERY',
        'CARRYFORWARD': 'CARRYFORWARD',
        'NRML': 'CARRYFORWARD',
    }
    
    # Variety mapping
    VARIETY_MAP = {
        'NORMAL': 'NORMAL',
        'STOPLOSS': 'STOPLOSS',
        'AMO': 'AMO',
        'ROBO': 'ROBO',
    }
    
    def __init__(self, smart_api, config: Optional[Dict[str, Any]] = None):
        """
        Initialize order handler.
        
        Args:
            smart_api: Authenticated SmartAPI instance
            config: Optional configuration
        """
        self._smart_api = smart_api
        self._config = config or {}
        
        logger.info("Initialized AngelOneOrders")
    
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
        symbol_token: str = "",
        variety: str = "NORMAL",
        duration: str = "DAY",
        disclosed_quantity: int = 0
    ) -> Dict[str, Any]:
        """
        Place a new order.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange (NSE, NFO, etc.)
            transaction_type: BUY or SELL
            quantity: Order quantity
            order_type: MARKET, LIMIT, STOPLOSS, STOPLOSS_MARKET
            product_type: INTRADAY, DELIVERY, CARRYFORWARD
            price: Limit price (for LIMIT orders)
            trigger_price: Trigger price (for STOPLOSS orders)
            symbol_token: Symbol token (required for Angel One)
            variety: NORMAL, STOPLOSS, AMO, ROBO
            duration: DAY or IOC
            disclosed_quantity: Disclosed quantity (optional)
            
        Returns:
            Dictionary with order ID or error
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            # Map order parameters
            order_type = self.ORDER_TYPE_MAP.get(order_type.upper(), order_type.upper())
            product_type = self.PRODUCT_TYPE_MAP.get(product_type.upper(), product_type.upper())
            variety = self.VARIETY_MAP.get(variety.upper(), variety.upper())
            transaction_type = transaction_type.upper()
            
            # Build order parameters
            order_params = {
                'variety': variety,
                'tradingsymbol': symbol,
                'symboltoken': symbol_token,
                'transactiontype': transaction_type,
                'exchange': exchange.upper(),
                'ordertype': order_type,
                'producttype': product_type,
                'duration': duration,
                'quantity': quantity,
            }
            
            # Add price for limit orders
            if order_type in ['LIMIT', 'STOPLOSS_LIMIT']:
                order_params['price'] = price
            else:
                order_params['price'] = 0
            
            # Add trigger price for stop loss orders
            if order_type in ['STOPLOSS_LIMIT', 'STOPLOSS_MARKET']:
                order_params['triggerprice'] = trigger_price
            else:
                order_params['triggerprice'] = 0
            
            # Add disclosed quantity if specified
            if disclosed_quantity > 0:
                order_params['disclosedquantity'] = disclosed_quantity
            
            logger.info(f"Placing order: {order_params}")
            
            response = self._smart_api.placeOrder(order_params)
            
            if response.get('status'):
                order_id = response.get('data', {}).get('orderid', '')
                logger.info(f"Order placed successfully. Order ID: {order_id}")
                return {
                    'status': True,
                    'order_id': order_id,
                    'message': 'Order placed successfully'
                }
            else:
                error_msg = response.get('message', 'Order placement failed')
                logger.error(f"Order placement failed: {error_msg}")
                return {
                    'status': False,
                    'message': error_msg
                }
                
        except Exception as e:
            logger.exception(f"Place order exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def modify_order(
        self,
        order_id: str,
        variety: str = "NORMAL",
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        order_type: Optional[str] = None,
        exchange: str = "NFO",
        symbol_token: str = "",
        symbol: str = ""
    ) -> Dict[str, Any]:
        """
        Modify an existing order.
        
        Args:
            order_id: Order ID to modify
            variety: Order variety
            quantity: New quantity (optional)
            price: New price (optional)
            trigger_price: New trigger price (optional)
            order_type: New order type (optional)
            exchange: Exchange
            symbol_token: Symbol token
            symbol: Trading symbol
            
        Returns:
            Dictionary with modification status
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            # Build modification parameters
            modify_params = {
                'variety': variety,
                'orderid': order_id,
                'exchange': exchange,
                'symboltoken': symbol_token,
                'tradingsymbol': symbol,
            }
            
            if quantity is not None:
                modify_params['quantity'] = quantity
            
            if price is not None:
                modify_params['price'] = price
            
            if trigger_price is not None:
                modify_params['triggerprice'] = trigger_price
            
            if order_type is not None:
                order_type = self.ORDER_TYPE_MAP.get(order_type.upper(), order_type.upper())
                modify_params['ordertype'] = order_type
            
            logger.info(f"Modifying order {order_id}: {modify_params}")
            
            response = self._smart_api.modifyOrder(modify_params)
            
            if response.get('status'):
                logger.info(f"Order {order_id} modified successfully")
                return {
                    'status': True,
                    'order_id': order_id,
                    'message': 'Order modified successfully'
                }
            else:
                error_msg = response.get('message', 'Order modification failed')
                logger.error(f"Order modification failed: {error_msg}")
                return {
                    'status': False,
                    'message': error_msg
                }
                
        except Exception as e:
            logger.exception(f"Modify order exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def cancel_order(
        self,
        order_id: str,
        variety: str = "NORMAL"
    ) -> Dict[str, Any]:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            variety: Order variety
            
        Returns:
            Dictionary with cancellation status
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            logger.info(f"Cancelling order: {order_id}")
            
            response = self._smart_api.cancelOrder(
                order_id=order_id,
                variety=variety
            )
            
            if response.get('status'):
                logger.info(f"Order {order_id} cancelled successfully")
                return {
                    'status': True,
                    'order_id': order_id,
                    'message': 'Order cancelled successfully'
                }
            else:
                error_msg = response.get('message', 'Order cancellation failed')
                logger.error(f"Order cancellation failed: {error_msg}")
                return {
                    'status': False,
                    'message': error_msg
                }
                
        except Exception as e:
            logger.exception(f"Cancel order exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status of a specific order.
        
        Args:
            order_id: Order ID
            
        Returns:
            Dictionary with order details
        """
        # Get all orders and find the specific one
        orders_result = self.get_order_book()
        
        if not orders_result.get('status'):
            return orders_result
        
        for order in orders_result.get('orders', []):
            if order.get('order_id') == order_id:
                return {
                    'status': True,
                    'order': order
                }
        
        return {
            'status': False,
            'message': f'Order not found: {order_id}'
        }
    
    def get_order_book(self) -> Dict[str, Any]:
        """
        Get all orders for the day.
        
        Returns:
            Dictionary with list of orders
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            response = self._smart_api.orderBook()
            
            if response.get('status'):
                orders_data = response.get('data', []) or []
                orders = []
                
                for order in orders_data:
                    orders.append({
                        'order_id': order.get('orderid', ''),
                        'symbol': order.get('tradingsymbol', ''),
                        'exchange': order.get('exchange', ''),
                        'transaction_type': order.get('transactiontype', ''),
                        'quantity': order.get('quantity', 0),
                        'filled_quantity': order.get('filledshares', 0),
                        'pending_quantity': order.get('unfilledshares', 0),
                        'order_type': order.get('ordertype', ''),
                        'product_type': order.get('producttype', ''),
                        'price': order.get('price', 0),
                        'trigger_price': order.get('triggerprice', 0),
                        'average_price': order.get('averageprice', 0),
                        'status': order.get('status', ''),
                        'variety': order.get('variety', ''),
                        'order_time': order.get('orderupdatetime', ''),
                        'text': order.get('text', ''),
                    })
                
                logger.info(f"Retrieved {len(orders)} orders")
                return {
                    'status': True,
                    'orders': orders,
                    'count': len(orders)
                }
            else:
                return {
                    'status': False,
                    'message': response.get('message', 'Failed to get order book')
                }
                
        except Exception as e:
            logger.exception(f"Get order book exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def get_trade_book(self) -> Dict[str, Any]:
        """
        Get all trades for the day.
        
        Returns:
            Dictionary with list of trades
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            response = self._smart_api.tradeBook()
            
            if response.get('status'):
                trades_data = response.get('data', []) or []
                trades = []
                
                for trade in trades_data:
                    trades.append({
                        'trade_id': trade.get('tradeid', ''),
                        'order_id': trade.get('orderid', ''),
                        'symbol': trade.get('tradingsymbol', ''),
                        'exchange': trade.get('exchange', ''),
                        'transaction_type': trade.get('transactiontype', ''),
                        'quantity': trade.get('quantity', 0),
                        'price': trade.get('price', 0),
                        'product_type': trade.get('producttype', ''),
                        'trade_time': trade.get('filltime', ''),
                    })
                
                logger.info(f"Retrieved {len(trades)} trades")
                return {
                    'status': True,
                    'trades': trades,
                    'count': len(trades)
                }
            else:
                return {
                    'status': False,
                    'message': response.get('message', 'Failed to get trade book')
                }
                
        except Exception as e:
            logger.exception(f"Get trade book exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def place_bracket_order(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        price: float,
        target: float,
        stoploss: float,
        trailing_stoploss: float = 0.0,
        symbol_token: str = ""
    ) -> Dict[str, Any]:
        """
        Place a bracket order.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            transaction_type: BUY or SELL
            quantity: Order quantity
            price: Entry price
            target: Target price
            stoploss: Stop loss price
            trailing_stoploss: Trailing stop loss (optional)
            symbol_token: Symbol token
            
        Returns:
            Dictionary with order IDs
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            order_params = {
                'variety': 'ROBO',
                'tradingsymbol': symbol,
                'symboltoken': symbol_token,
                'transactiontype': transaction_type.upper(),
                'exchange': exchange.upper(),
                'ordertype': 'LIMIT',
                'producttype': 'INTRADAY',
                'duration': 'DAY',
                'price': price,
                'quantity': quantity,
                'squareoff': target,
                'stoploss': stoploss,
            }
            
            if trailing_stoploss > 0:
                order_params['trailingstoploss'] = trailing_stoploss
            
            logger.info(f"Placing bracket order: {order_params}")
            
            response = self._smart_api.placeOrder(order_params)
            
            if response.get('status'):
                order_id = response.get('data', {}).get('orderid', '')
                logger.info(f"Bracket order placed. Order ID: {order_id}")
                return {
                    'status': True,
                    'order_id': order_id,
                    'message': 'Bracket order placed successfully'
                }
            else:
                return {
                    'status': False,
                    'message': response.get('message', 'Bracket order failed')
                }
                
        except Exception as e:
            logger.exception(f"Place bracket order exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def place_cover_order(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        price: float,
        trigger_price: float,
        symbol_token: str = ""
    ) -> Dict[str, Any]:
        """
        Place a cover order (order with stop loss).
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            transaction_type: BUY or SELL
            quantity: Order quantity
            price: Entry price (0 for market)
            trigger_price: Stop loss trigger price
            symbol_token: Symbol token
            
        Returns:
            Dictionary with order ID
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            order_type = 'MARKET' if price == 0 else 'LIMIT'
            
            order_params = {
                'variety': 'STOPLOSS',
                'tradingsymbol': symbol,
                'symboltoken': symbol_token,
                'transactiontype': transaction_type.upper(),
                'exchange': exchange.upper(),
                'ordertype': order_type,
                'producttype': 'INTRADAY',
                'duration': 'DAY',
                'price': price,
                'quantity': quantity,
                'triggerprice': trigger_price,
            }
            
            logger.info(f"Placing cover order: {order_params}")
            
            response = self._smart_api.placeOrder(order_params)
            
            if response.get('status'):
                order_id = response.get('data', {}).get('orderid', '')
                logger.info(f"Cover order placed. Order ID: {order_id}")
                return {
                    'status': True,
                    'order_id': order_id,
                    'message': 'Cover order placed successfully'
                }
            else:
                return {
                    'status': False,
                    'message': response.get('message', 'Cover order failed')
                }
                
        except Exception as e:
            logger.exception(f"Place cover order exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def place_amo_order(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str = "LIMIT",
        product_type: str = "DELIVERY",
        price: float = 0.0,
        trigger_price: float = 0.0,
        symbol_token: str = ""
    ) -> Dict[str, Any]:
        """
        Place an After Market Order (AMO).
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            transaction_type: BUY or SELL
            quantity: Order quantity
            order_type: Order type
            product_type: Product type
            price: Limit price
            trigger_price: Trigger price
            symbol_token: Symbol token
            
        Returns:
            Dictionary with order ID
        """
        return self.place_order(
            symbol=symbol,
            exchange=exchange,
            transaction_type=transaction_type,
            quantity=quantity,
            order_type=order_type,
            product_type=product_type,
            price=price,
            trigger_price=trigger_price,
            symbol_token=symbol_token,
            variety="AMO"
        )
