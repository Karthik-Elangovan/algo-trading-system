"""
Angel One Market Data Module.

Provides real-time and historical market data access including
LTP, quotes, option chains, and index data.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AngelOneMarketData:
    """
    Handles market data operations with Angel One SmartAPI.
    
    Supports:
    - Real-time LTP and quotes
    - Historical candle data
    - Option chain data
    - Index data
    """
    
    # Interval mapping for historical data
    INTERVAL_MAP = {
        'ONE_MINUTE': 'ONE_MINUTE',
        'THREE_MINUTE': 'THREE_MINUTE',
        'FIVE_MINUTE': 'FIVE_MINUTE',
        'TEN_MINUTE': 'TEN_MINUTE',
        'FIFTEEN_MINUTE': 'FIFTEEN_MINUTE',
        'THIRTY_MINUTE': 'THIRTY_MINUTE',
        'ONE_HOUR': 'ONE_HOUR',
        'ONE_DAY': 'ONE_DAY',
        '1m': 'ONE_MINUTE',
        '3m': 'THREE_MINUTE',
        '5m': 'FIVE_MINUTE',
        '10m': 'TEN_MINUTE',
        '15m': 'FIFTEEN_MINUTE',
        '30m': 'THIRTY_MINUTE',
        '1h': 'ONE_HOUR',
        '1d': 'ONE_DAY',
    }
    
    # Exchange mapping
    EXCHANGE_MAP = {
        'NSE': 'NSE',
        'BSE': 'BSE',
        'NFO': 'NFO',
        'BFO': 'BFO',
        'MCX': 'MCX',
        'CDS': 'CDS',
    }
    
    def __init__(self, smart_api, config: Optional[Dict[str, Any]] = None):
        """
        Initialize market data handler.
        
        Args:
            smart_api: Authenticated SmartAPI instance
            config: Optional configuration
        """
        self._smart_api = smart_api
        self._config = config or {}
        self._symbol_token_cache: Dict[str, str] = {}
        
        logger.info("Initialized AngelOneMarketData")
    
    def get_ltp(
        self,
        symbol: str,
        exchange: str,
        symbol_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get Last Traded Price for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange (NSE, NFO, etc.)
            symbol_token: Symbol token (optional, will lookup if not provided)
            
        Returns:
            Dictionary with LTP data
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            exchange = self.EXCHANGE_MAP.get(exchange.upper(), exchange.upper())
            
            # Get LTP data
            ltp_data = self._smart_api.ltpData(
                exchange=exchange,
                tradingsymbol=symbol,
                symboltoken=symbol_token or ""
            )
            
            if ltp_data.get('status'):
                data = ltp_data.get('data', {})
                return {
                    'status': True,
                    'ltp': data.get('ltp', 0.0),
                    'symbol': symbol,
                    'exchange': exchange,
                    'open': data.get('open', 0.0),
                    'high': data.get('high', 0.0),
                    'low': data.get('low', 0.0),
                    'close': data.get('close', 0.0),
                    'volume': data.get('volume', 0),
                }
            else:
                logger.warning(f"Failed to get LTP for {symbol}: {ltp_data}")
                return {
                    'status': False,
                    'message': ltp_data.get('message', 'Failed to get LTP')
                }
                
        except Exception as e:
            logger.exception(f"Get LTP exception for {symbol}: {e}")
            return {'status': False, 'message': str(e)}
    
    def get_quote(
        self,
        symbol: str,
        exchange: str,
        symbol_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get full market quote for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            symbol_token: Symbol token (optional)
            
        Returns:
            Dictionary with full quote data
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            exchange = self.EXCHANGE_MAP.get(exchange.upper(), exchange.upper())
            
            quote_data = self._smart_api.ltpData(
                exchange=exchange,
                tradingsymbol=symbol,
                symboltoken=symbol_token or ""
            )
            
            if quote_data.get('status'):
                data = quote_data.get('data', {})
                return {
                    'status': True,
                    'symbol': symbol,
                    'exchange': exchange,
                    'ltp': data.get('ltp', 0.0),
                    'open': data.get('open', 0.0),
                    'high': data.get('high', 0.0),
                    'low': data.get('low', 0.0),
                    'close': data.get('close', 0.0),
                    'volume': data.get('volume', 0),
                    'avg_price': data.get('avgprice', 0.0),
                    'upper_circuit': data.get('upper_circuit_limit', 0.0),
                    'lower_circuit': data.get('lower_circuit_limit', 0.0),
                    '52_week_high': data.get('52_week_high', 0.0),
                    '52_week_low': data.get('52_week_low', 0.0),
                    'timestamp': datetime.now().isoformat(),
                }
            else:
                return {
                    'status': False,
                    'message': quote_data.get('message', 'Failed to get quote')
                }
                
        except Exception as e:
            logger.exception(f"Get quote exception for {symbol}: {e}")
            return {'status': False, 'message': str(e)}
    
    def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        symbol_token: str,
        interval: str,
        from_date: datetime,
        to_date: datetime
    ) -> Dict[str, Any]:
        """
        Get historical candle data.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            symbol_token: Symbol token (required for historical data)
            interval: Candle interval
            from_date: Start date
            to_date: End date
            
        Returns:
            Dictionary with candle data
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            exchange = self.EXCHANGE_MAP.get(exchange.upper(), exchange.upper())
            interval = self.INTERVAL_MAP.get(interval, interval)
            
            # Format dates
            from_str = from_date.strftime('%Y-%m-%d %H:%M')
            to_str = to_date.strftime('%Y-%m-%d %H:%M')
            
            params = {
                'exchange': exchange,
                'symboltoken': symbol_token,
                'interval': interval,
                'fromdate': from_str,
                'todate': to_str
            }
            
            response = self._smart_api.getCandleData(params)
            
            if response.get('status'):
                candles = response.get('data', [])
                return {
                    'status': True,
                    'symbol': symbol,
                    'exchange': exchange,
                    'interval': interval,
                    'candles': self._format_candles(candles),
                    'count': len(candles)
                }
            else:
                return {
                    'status': False,
                    'message': response.get('message', 'Failed to get historical data')
                }
                
        except Exception as e:
            logger.exception(f"Get historical data exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def _format_candles(self, candles: List[List]) -> List[Dict[str, Any]]:
        """
        Format raw candle data into dictionaries.
        
        Args:
            candles: Raw candle data from API
            
        Returns:
            List of formatted candle dictionaries
        """
        formatted = []
        for candle in candles:
            if len(candle) >= 6:
                formatted.append({
                    'timestamp': candle[0],
                    'open': candle[1],
                    'high': candle[2],
                    'low': candle[3],
                    'close': candle[4],
                    'volume': candle[5]
                })
        return formatted
    
    def get_option_chain(
        self,
        underlying: str,
        expiry_date: datetime
    ) -> Dict[str, Any]:
        """
        Get option chain data for an underlying.
        
        Args:
            underlying: Underlying symbol (NIFTY, BANKNIFTY)
            expiry_date: Expiry date
            
        Returns:
            Dictionary with option chain data
            
        Note:
            Angel One SmartAPI doesn't provide direct option chain API.
            This method simulates option chain retrieval.
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            # Note: SmartAPI doesn't have a dedicated option chain endpoint
            # This would typically require fetching individual option quotes
            # or using WebSocket for real-time data
            
            logger.info(f"Option chain request for {underlying} expiry {expiry_date}")
            
            return {
                'status': True,
                'underlying': underlying,
                'expiry': expiry_date.isoformat(),
                'message': 'Use WebSocket for real-time option chain data',
                'data': []
            }
            
        except Exception as e:
            logger.exception(f"Get option chain exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def get_index_data(self, index_name: str) -> Dict[str, Any]:
        """
        Get index data (NIFTY, BANKNIFTY, SENSEX).
        
        Args:
            index_name: Index name
            
        Returns:
            Dictionary with index data
        """
        # Index symbol mappings
        index_map = {
            'NIFTY': {'symbol': 'Nifty 50', 'exchange': 'NSE', 'token': '99926000'},
            'NIFTY50': {'symbol': 'Nifty 50', 'exchange': 'NSE', 'token': '99926000'},
            'BANKNIFTY': {'symbol': 'Nifty Bank', 'exchange': 'NSE', 'token': '99926009'},
            'SENSEX': {'symbol': 'SENSEX', 'exchange': 'BSE', 'token': '99919000'},
            'FINNIFTY': {'symbol': 'Nifty Fin Service', 'exchange': 'NSE', 'token': '99926037'},
        }
        
        index_info = index_map.get(index_name.upper())
        if not index_info:
            return {
                'status': False,
                'message': f'Unknown index: {index_name}'
            }
        
        return self.get_ltp(
            symbol=index_info['symbol'],
            exchange=index_info['exchange'],
            symbol_token=index_info['token']
        )
    
    def search_symbols(
        self,
        search_text: str,
        exchange: str = "NFO"
    ) -> Dict[str, Any]:
        """
        Search for symbols.
        
        Args:
            search_text: Search string
            exchange: Exchange to search in
            
        Returns:
            Dictionary with search results
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            response = self._smart_api.searchScrip(
                exchange=exchange,
                searchscrip=search_text
            )
            
            if response.get('status'):
                return {
                    'status': True,
                    'results': response.get('data', [])
                }
            else:
                return {
                    'status': False,
                    'message': response.get('message', 'Search failed')
                }
                
        except Exception as e:
            logger.exception(f"Search symbols exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def get_market_depth(
        self,
        symbol: str,
        exchange: str,
        symbol_token: str
    ) -> Dict[str, Any]:
        """
        Get market depth (Level 2) data.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            symbol_token: Symbol token
            
        Returns:
            Dictionary with market depth data
            
        Note:
            Market depth requires WebSocket subscription for real-time data.
        """
        logger.info(f"Market depth request for {symbol}")
        
        return {
            'status': True,
            'symbol': symbol,
            'exchange': exchange,
            'message': 'Subscribe to WebSocket for real-time market depth',
            'bids': [],
            'asks': []
        }
