"""
Utility functions for broker integration.

This module provides helper functions for token generation,
symbol formatting, and other broker-related utilities.
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def generate_token_hash(symbol: str, exchange: str) -> str:
    """
    Generate a unique hash for a symbol-exchange combination.
    
    Args:
        symbol: Trading symbol
        exchange: Exchange name
        
    Returns:
        Hash string
    """
    combined = f"{exchange}:{symbol}"
    return hashlib.md5(combined.encode()).hexdigest()[:16]


def format_symbol_for_angel(
    underlying: str,
    expiry_date: datetime,
    strike: float,
    option_type: str
) -> str:
    """
    Format a symbol string for Angel One API.
    
    Args:
        underlying: Underlying symbol (NIFTY, BANKNIFTY)
        expiry_date: Expiry date
        strike: Strike price
        option_type: CE or PE
        
    Returns:
        Formatted symbol string
    """
    # Format: NIFTY23DEC21000CE
    year = expiry_date.strftime("%y")
    month = expiry_date.strftime("%b").upper()
    return f"{underlying}{year}{month}{int(strike)}{option_type.upper()}"


def parse_option_symbol(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Parse an option symbol to extract components.
    
    Args:
        symbol: Option symbol (e.g., NIFTY23DEC21000CE)
        
    Returns:
        Dictionary with underlying, expiry, strike, option_type
        or None if parsing fails
    """
    # Pattern for options: UNDERLYING + YY + MMM + STRIKE + CE/PE
    pattern = r'^([A-Z]+)(\d{2})([A-Z]{3})(\d+)(CE|PE)$'
    match = re.match(pattern, symbol)
    
    if not match:
        logger.warning(f"Could not parse option symbol: {symbol}")
        return None
    
    underlying, year, month, strike, option_type = match.groups()
    
    # Parse month
    month_map = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
        'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
        'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }
    
    try:
        expiry = datetime(
            year=2000 + int(year),
            month=month_map[month],
            day=1  # Actual expiry day would need lookup
        )
    except (ValueError, KeyError):
        return None
    
    return {
        'underlying': underlying,
        'expiry': expiry,
        'strike': float(strike),
        'option_type': option_type
    }


def calculate_slippage(
    price: float,
    transaction_type: str,
    slippage_pct: float = 0.005
) -> float:
    """
    Calculate price with slippage.
    
    Args:
        price: Original price
        transaction_type: BUY or SELL
        slippage_pct: Slippage percentage (default 0.5%)
        
    Returns:
        Price adjusted for slippage
    """
    if transaction_type.upper() == "BUY":
        return price * (1 + slippage_pct)
    else:
        return price * (1 - slippage_pct)


def calculate_transaction_costs(
    value: float,
    is_sell: bool = False,
    brokerage: float = 20.0,
    stt_rate: float = 0.0005,
    exchange_rate: float = 0.00053,
    gst_rate: float = 0.18,
    sebi_rate: float = 0.0000005,
    stamp_duty_rate: float = 0.00003
) -> Dict[str, float]:
    """
    Calculate all transaction costs.
    
    Args:
        value: Transaction value
        is_sell: True if selling (STT applies)
        brokerage: Flat brokerage per order
        stt_rate: STT rate (sell side only for options)
        exchange_rate: Exchange transaction charges rate
        gst_rate: GST rate on brokerage
        sebi_rate: SEBI charges rate
        stamp_duty_rate: Stamp duty rate (buy side)
        
    Returns:
        Dictionary with breakdown of all costs
    """
    costs = {
        'brokerage': brokerage,
        'stt': value * stt_rate if is_sell else 0.0,
        'exchange_charges': value * exchange_rate,
        'gst': 0.0,  # Will be calculated
        'sebi_charges': value * sebi_rate,
        'stamp_duty': value * stamp_duty_rate if not is_sell else 0.0,
    }
    
    # GST is on brokerage and exchange charges
    costs['gst'] = (costs['brokerage'] + costs['exchange_charges']) * gst_rate
    
    costs['total'] = sum(costs.values())
    
    return costs


def get_expiry_dates(
    underlying: str,
    count: int = 5,
    from_date: Optional[datetime] = None
) -> List[datetime]:
    """
    Get upcoming expiry dates for an underlying.
    
    Args:
        underlying: Underlying symbol
        count: Number of expiries to return
        from_date: Start date (default: today)
        
    Returns:
        List of expiry dates
    """
    from_date = from_date or datetime.now()
    expiries = []
    
    # NIFTY/BANKNIFTY expires on Thursday
    # For simplicity, returning weekly expiries
    current = from_date
    
    while len(expiries) < count:
        # Find next Thursday
        days_until_thursday = (3 - current.weekday()) % 7
        if days_until_thursday == 0 and current.hour >= 15:
            days_until_thursday = 7
        
        expiry = current + timedelta(days=days_until_thursday)
        expiry = expiry.replace(hour=15, minute=30, second=0, microsecond=0)
        
        if expiry > from_date:
            expiries.append(expiry)
        
        current = expiry + timedelta(days=1)
    
    return expiries


def generate_order_id() -> str:
    """
    Generate a unique order ID for paper trading.
    
    Returns:
        Unique order ID string
    """
    import uuid
    return f"PAPER_{uuid.uuid4().hex[:12].upper()}"


def validate_order_params(
    symbol: str,
    exchange: str,
    transaction_type: str,
    quantity: int,
    order_type: str,
    product_type: str,
    price: float = 0.0,
    trigger_price: float = 0.0
) -> Tuple[bool, str]:
    """
    Validate order parameters.
    
    Args:
        symbol: Trading symbol
        exchange: Exchange
        transaction_type: BUY or SELL
        quantity: Order quantity
        order_type: Order type
        product_type: Product type
        price: Limit price
        trigger_price: Trigger price
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check required fields
    if not symbol:
        return False, "Symbol is required"
    
    if not exchange:
        return False, "Exchange is required"
    
    # Check transaction type
    if transaction_type.upper() not in ['BUY', 'SELL']:
        return False, f"Invalid transaction type: {transaction_type}"
    
    # Check quantity
    if quantity <= 0:
        return False, f"Quantity must be positive: {quantity}"
    
    # Check order type
    valid_order_types = ['MARKET', 'LIMIT', 'STOPLOSS', 'STOPLOSS_MARKET']
    if order_type.upper() not in valid_order_types:
        return False, f"Invalid order type: {order_type}"
    
    # Check product type
    valid_product_types = ['INTRADAY', 'DELIVERY', 'CARRYFORWARD']
    if product_type.upper() not in valid_product_types:
        return False, f"Invalid product type: {product_type}"
    
    # Check price for limit orders
    if order_type.upper() == 'LIMIT' and price <= 0:
        return False, "Price required for LIMIT orders"
    
    # Check trigger price for stop loss orders
    if order_type.upper() in ['STOPLOSS', 'STOPLOSS_MARKET'] and trigger_price <= 0:
        return False, "Trigger price required for STOPLOSS orders"
    
    return True, ""


def round_to_tick(price: float, tick_size: float = 0.05) -> float:
    """
    Round price to nearest tick size.
    
    Args:
        price: Original price
        tick_size: Minimum price increment
        
    Returns:
        Price rounded to tick size
    """
    return round(round(price / tick_size) * tick_size, 2)


def get_lot_size(symbol: str, exchange: str = "NFO") -> int:
    """
    Get lot size for a symbol.
    
    Args:
        symbol: Trading symbol
        exchange: Exchange
        
    Returns:
        Lot size
    """
    # Standard lot sizes (as of 2024)
    lot_sizes = {
        'NIFTY': 50,
        'BANKNIFTY': 15,
        'FINNIFTY': 40,
        'MIDCPNIFTY': 75,
        'SENSEX': 10,
        'BANKEX': 15,
    }
    
    # Extract underlying from option symbol
    for underlying, lot_size in lot_sizes.items():
        if symbol.startswith(underlying):
            return lot_size
    
    # Default lot size
    return 1


def format_currency(amount: float, currency: str = "INR") -> str:
    """
    Format amount as currency string.
    
    Args:
        amount: Amount to format
        currency: Currency code
        
    Returns:
        Formatted currency string
    """
    if currency == "INR":
        if abs(amount) >= 10000000:  # 1 Crore
            return f"₹{amount / 10000000:.2f} Cr"
        elif abs(amount) >= 100000:  # 1 Lakh
            return f"₹{amount / 100000:.2f} L"
        else:
            return f"₹{amount:,.2f}"
    return f"{amount:,.2f}"


def is_market_open(exchange: str = "NSE") -> bool:
    """
    Check if market is currently open.
    
    Args:
        exchange: Exchange to check
        
    Returns:
        True if market is open
    """
    now = datetime.now()
    
    # Check if weekend
    if now.weekday() >= 5:
        return False
    
    # Market hours (9:15 AM to 3:30 PM IST)
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    return market_open <= now <= market_close


def get_instrument_token_map() -> Dict[str, int]:
    """
    Get mapping of symbols to instrument tokens.
    
    Note: In production, this should be loaded from broker's
    instrument master file.
    
    Returns:
        Dictionary mapping symbol to token
    """
    # Common indices and their tokens (for reference)
    return {
        'NIFTY': 26000,
        'BANKNIFTY': 26009,
        'SENSEX': 1,
        'FINNIFTY': 26037,
    }
