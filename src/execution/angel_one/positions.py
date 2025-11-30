"""
Angel One Position Management Module.

Handles position tracking, holdings, and position-related operations.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AngelOnePositions:
    """
    Handles position management with Angel One SmartAPI.
    
    Supports:
    - Get current positions
    - Get holdings
    - Position conversion
    - Square off positions
    - Position P&L calculation
    """
    
    def __init__(self, smart_api, config: Optional[Dict[str, Any]] = None):
        """
        Initialize position handler.
        
        Args:
            smart_api: Authenticated SmartAPI instance
            config: Optional configuration
        """
        self._smart_api = smart_api
        self._config = config or {}
        
        logger.info("Initialized AngelOnePositions")
    
    def get_positions(self) -> Dict[str, Any]:
        """
        Get current positions (intraday + carryforward).
        
        Returns:
            Dictionary with position details
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            response = self._smart_api.position()
            
            if response.get('status'):
                positions_data = response.get('data', []) or []
                positions = []
                
                for pos in positions_data:
                    net_qty = int(pos.get('netqty', 0))
                    if net_qty == 0:
                        continue  # Skip closed positions
                    
                    buy_value = float(pos.get('totalbuyvalue', 0))
                    sell_value = float(pos.get('totalsellvalue', 0))
                    buy_qty = int(pos.get('daybuyqty', 0)) + int(pos.get('cfbuyqty', 0))
                    sell_qty = int(pos.get('daysellqty', 0)) + int(pos.get('cfsellqty', 0))
                    
                    avg_price = 0
                    if net_qty > 0 and buy_qty > 0:
                        avg_price = buy_value / buy_qty
                    elif net_qty < 0 and sell_qty > 0:
                        avg_price = sell_value / sell_qty
                    
                    ltp = float(pos.get('ltp', 0))
                    pnl = float(pos.get('pnl', 0))
                    
                    positions.append({
                        'symbol': pos.get('tradingsymbol', ''),
                        'symbol_token': pos.get('symboltoken', ''),
                        'exchange': pos.get('exchange', ''),
                        'product_type': pos.get('producttype', ''),
                        'quantity': net_qty,
                        'average_price': avg_price,
                        'last_price': ltp,
                        'pnl': pnl,
                        'pnl_percentage': (pnl / (avg_price * abs(net_qty)) * 100) if avg_price > 0 and net_qty != 0 else 0,
                        'buy_quantity': buy_qty,
                        'sell_quantity': sell_qty,
                        'buy_value': buy_value,
                        'sell_value': sell_value,
                        'day_buy_quantity': int(pos.get('daybuyqty', 0)),
                        'day_sell_quantity': int(pos.get('daysellqty', 0)),
                        'cf_buy_quantity': int(pos.get('cfbuyqty', 0)),
                        'cf_sell_quantity': int(pos.get('cfsellqty', 0)),
                        'multiplier': int(pos.get('lotsize', 1)),
                    })
                
                logger.info(f"Retrieved {len(positions)} positions")
                return {
                    'status': True,
                    'positions': positions,
                    'count': len(positions)
                }
            else:
                return {
                    'status': False,
                    'message': response.get('message', 'Failed to get positions')
                }
                
        except Exception as e:
            logger.exception(f"Get positions exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def get_holdings(self) -> Dict[str, Any]:
        """
        Get portfolio holdings (delivery positions).
        
        Returns:
            Dictionary with holdings details
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            response = self._smart_api.holding()
            
            if response.get('status'):
                holdings_data = response.get('data', []) or []
                holdings = []
                
                for holding in holdings_data:
                    quantity = int(holding.get('quantity', 0))
                    if quantity == 0:
                        continue
                    
                    avg_price = float(holding.get('averageprice', 0))
                    ltp = float(holding.get('ltp', 0))
                    pnl = (ltp - avg_price) * quantity
                    pnl_pct = ((ltp - avg_price) / avg_price * 100) if avg_price > 0 else 0
                    
                    holdings.append({
                        'symbol': holding.get('tradingsymbol', ''),
                        'symbol_token': holding.get('symboltoken', ''),
                        'exchange': holding.get('exchange', ''),
                        'isin': holding.get('isin', ''),
                        'quantity': quantity,
                        'average_price': avg_price,
                        'last_price': ltp,
                        'close_price': float(holding.get('close', 0)),
                        'pnl': pnl,
                        'pnl_percentage': pnl_pct,
                        'authorized_quantity': int(holding.get('authorisedquantity', 0)),
                        'collateral_quantity': int(holding.get('collateralquantity', 0)),
                        'collateral_type': holding.get('collateraltype', ''),
                        'haircut': float(holding.get('haircut', 0)),
                        't1_quantity': int(holding.get('t1quantity', 0)),
                    })
                
                logger.info(f"Retrieved {len(holdings)} holdings")
                return {
                    'status': True,
                    'holdings': holdings,
                    'count': len(holdings)
                }
            else:
                return {
                    'status': False,
                    'message': response.get('message', 'Failed to get holdings')
                }
                
        except Exception as e:
            logger.exception(f"Get holdings exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def convert_position(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        from_product: str,
        to_product: str,
        symbol_token: str = ""
    ) -> Dict[str, Any]:
        """
        Convert position product type.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            transaction_type: BUY or SELL
            quantity: Quantity to convert
            from_product: Current product type (INTRADAY, DELIVERY, CARRYFORWARD)
            to_product: Target product type
            symbol_token: Symbol token
            
        Returns:
            Dictionary with conversion status
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        # Product type mapping
        product_map = {
            'INTRADAY': 'INTRADAY',
            'MIS': 'INTRADAY',
            'DELIVERY': 'DELIVERY',
            'CNC': 'DELIVERY',
            'CARRYFORWARD': 'CARRYFORWARD',
            'NRML': 'CARRYFORWARD',
        }
        
        try:
            params = {
                'exchange': exchange.upper(),
                'tradingsymbol': symbol,
                'symboltoken': symbol_token,
                'transactiontype': transaction_type.upper(),
                'positiontype': 'DAY',
                'quantity': quantity,
                'oldproducttype': product_map.get(from_product.upper(), from_product.upper()),
                'newproducttype': product_map.get(to_product.upper(), to_product.upper()),
            }
            
            logger.info(f"Converting position: {params}")
            
            response = self._smart_api.convertPosition(params)
            
            if response.get('status'):
                logger.info(f"Position converted successfully for {symbol}")
                return {
                    'status': True,
                    'message': 'Position converted successfully'
                }
            else:
                error_msg = response.get('message', 'Position conversion failed')
                logger.error(f"Position conversion failed: {error_msg}")
                return {
                    'status': False,
                    'message': error_msg
                }
                
        except Exception as e:
            logger.exception(f"Convert position exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def square_off_position(
        self,
        symbol: str,
        exchange: str,
        product_type: str,
        quantity: Optional[int] = None,
        symbol_token: str = ""
    ) -> Dict[str, Any]:
        """
        Square off a position.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            product_type: Product type
            quantity: Quantity to square off (None = full position)
            symbol_token: Symbol token
            
        Returns:
            Dictionary with square off order ID
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            # Get current position to determine direction
            positions_result = self.get_positions()
            if not positions_result.get('status'):
                return positions_result
            
            position = None
            for pos in positions_result.get('positions', []):
                if (pos['symbol'] == symbol and 
                    pos['exchange'] == exchange.upper() and
                    pos['product_type'].upper() == product_type.upper()):
                    position = pos
                    break
            
            if not position:
                return {
                    'status': False,
                    'message': f'Position not found for {symbol}'
                }
            
            net_qty = position['quantity']
            if net_qty == 0:
                return {
                    'status': False,
                    'message': 'Position already squared off'
                }
            
            # Determine transaction type (opposite of position)
            transaction_type = 'SELL' if net_qty > 0 else 'BUY'
            sq_off_qty = quantity if quantity else abs(net_qty)
            
            # Place square off order
            from .orders import AngelOneOrders
            orders = AngelOneOrders(self._smart_api, self._config)
            
            result = orders.place_order(
                symbol=symbol,
                exchange=exchange,
                transaction_type=transaction_type,
                quantity=sq_off_qty,
                order_type='MARKET',
                product_type=product_type,
                symbol_token=symbol_token or position.get('symbol_token', '')
            )
            
            if result.get('status'):
                logger.info(f"Position squared off for {symbol}. Order ID: {result.get('order_id')}")
            
            return result
            
        except Exception as e:
            logger.exception(f"Square off position exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def square_off_all(self, product_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Square off all positions.
        
        Args:
            product_type: Optional filter by product type
            
        Returns:
            Dictionary with results for each position
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            positions_result = self.get_positions()
            if not positions_result.get('status'):
                return positions_result
            
            positions = positions_result.get('positions', [])
            if product_type:
                positions = [p for p in positions if p['product_type'].upper() == product_type.upper()]
            
            if not positions:
                return {
                    'status': True,
                    'message': 'No positions to square off',
                    'results': []
                }
            
            results = []
            for pos in positions:
                result = self.square_off_position(
                    symbol=pos['symbol'],
                    exchange=pos['exchange'],
                    product_type=pos['product_type'],
                    symbol_token=pos.get('symbol_token', '')
                )
                results.append({
                    'symbol': pos['symbol'],
                    'result': result
                })
            
            success_count = sum(1 for r in results if r['result'].get('status'))
            
            return {
                'status': True,
                'message': f'Squared off {success_count}/{len(results)} positions',
                'results': results
            }
            
        except Exception as e:
            logger.exception(f"Square off all exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def get_position_pnl(self) -> Dict[str, Any]:
        """
        Calculate total P&L for all positions.
        
        Returns:
            Dictionary with P&L summary
        """
        positions_result = self.get_positions()
        if not positions_result.get('status'):
            return positions_result
        
        positions = positions_result.get('positions', [])
        
        total_pnl = sum(pos['pnl'] for pos in positions)
        realized_pnl = 0  # Would need trade book for accurate realized P&L
        unrealized_pnl = total_pnl  # Current positions are unrealized
        
        intraday_pnl = sum(pos['pnl'] for pos in positions if pos['product_type'] == 'INTRADAY')
        carryforward_pnl = sum(pos['pnl'] for pos in positions if pos['product_type'] == 'CARRYFORWARD')
        
        return {
            'status': True,
            'total_pnl': total_pnl,
            'realized_pnl': realized_pnl,
            'unrealized_pnl': unrealized_pnl,
            'intraday_pnl': intraday_pnl,
            'carryforward_pnl': carryforward_pnl,
            'position_count': len(positions)
        }
    
    def get_position_by_symbol(self, symbol: str, exchange: str = "NFO") -> Dict[str, Any]:
        """
        Get position for a specific symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            
        Returns:
            Dictionary with position details or None if not found
        """
        positions_result = self.get_positions()
        if not positions_result.get('status'):
            return positions_result
        
        for pos in positions_result.get('positions', []):
            if pos['symbol'] == symbol and pos['exchange'] == exchange.upper():
                return {
                    'status': True,
                    'position': pos
                }
        
        return {
            'status': False,
            'message': f'No position found for {symbol}'
        }
