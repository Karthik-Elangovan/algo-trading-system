"""
Real-Time Data Configuration Settings.

Configuration parameters for real-time data providers, managers, and aggregators.
"""

from typing import Dict, Any, List

# Real-Time Data Manager Configuration
REALTIME_CONFIG: Dict[str, Any] = {
    # Data provider to use ('angel_one' or 'mock')
    'provider': 'mock',
    
    # Maximum reconnection attempts
    'reconnect_attempts': 5,
    
    # Delay between reconnection attempts (seconds)
    'reconnect_delay': 5,
    
    # Minimum milliseconds between tick callbacks (throttling)
    'tick_throttle_ms': 100,
    
    # Default subscription mode ('ltp', 'quote', 'depth')
    'default_mode': 'quote',
    
    # Aggregation intervals for candle building
    'aggregation_intervals': ['1m', '5m', '15m'],
    
    # Maximum candles to keep per symbol per interval
    'max_candles': 500,
}


# Mock Provider Configuration
MOCK_PROVIDER_CONFIG: Dict[str, Any] = {
    # Milliseconds between tick generation
    'tick_interval_ms': 500,
    
    # Price volatility (standard deviation of returns)
    'price_volatility': 0.001,
    
    # Base prices for common instruments
    'base_prices': {
        'NIFTY': 24200.0,
        'BANKNIFTY': 52000.0,
        'SENSEX': 80000.0,
        'FINNIFTY': 23500.0,
    },
    
    # Whether to simulate market hours
    'simulate_market_hours': False,
}


# Angel One Provider Configuration
ANGEL_ONE_PROVIDER_CONFIG: Dict[str, Any] = {
    # Default exchange type (2 = NFO for options)
    'exchange_type': 2,
    
    # Connection timeout in seconds
    'connection_timeout': 10,
}


# Symbol Token Mapping (for Angel One)
SYMBOL_TOKEN_MAP: Dict[str, str] = {
    # Indices
    'NIFTY': '99926000',
    'BANKNIFTY': '99926009',
    'SENSEX': '99919000',
    'FINNIFTY': '99926037',
    
    # Add more symbol-token mappings as needed
}


# Exchange Type Mapping
EXCHANGE_TYPE_MAP: Dict[str, int] = {
    'NSE': 1,
    'NFO': 2,
    'BSE': 3,
    'BFO': 4,
    'MCX': 5,
    'CDS': 6,
}


def get_realtime_config() -> Dict[str, Any]:
    """
    Get the complete real-time configuration.
    
    Returns:
        Dictionary with all real-time configuration settings
    """
    return {
        **REALTIME_CONFIG,
        'mock_provider': MOCK_PROVIDER_CONFIG,
        'angel_one_provider': ANGEL_ONE_PROVIDER_CONFIG,
    }


def get_provider_config(provider_type: str) -> Dict[str, Any]:
    """
    Get configuration for a specific provider.
    
    Args:
        provider_type: Provider type ('mock' or 'angel_one')
        
    Returns:
        Provider-specific configuration dictionary
    """
    if provider_type == 'mock':
        return MOCK_PROVIDER_CONFIG.copy()
    elif provider_type == 'angel_one':
        return ANGEL_ONE_PROVIDER_CONFIG.copy()
    else:
        return {}


def get_token_for_symbol(symbol: str) -> str:
    """
    Get the token ID for a symbol.
    
    Args:
        symbol: Trading symbol
        
    Returns:
        Token ID string
    """
    return SYMBOL_TOKEN_MAP.get(symbol.upper(), symbol)


def get_symbol_for_token(token: str) -> str:
    """
    Get the symbol for a token ID.
    
    Args:
        token: Token ID
        
    Returns:
        Symbol string
    """
    # Reverse lookup
    for symbol, t in SYMBOL_TOKEN_MAP.items():
        if t == token:
            return symbol
    return token


def get_exchange_type(exchange: str) -> int:
    """
    Get the exchange type code.
    
    Args:
        exchange: Exchange name (NSE, NFO, BSE, etc.)
        
    Returns:
        Exchange type integer
    """
    return EXCHANGE_TYPE_MAP.get(exchange.upper(), 1)
