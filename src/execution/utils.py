"""
Utility functions for broker integration.
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import uuid

logger = logging.getLogger(__name__)


def generate_order_id() -> str:
    """Generate a unique order ID for paper trading."""
    return f"PAPER_{uuid.uuid4().hex[:12].upper()}"


def calculate_slippage(
    price: float,
    transaction_type: str,
    slippage_pct: float = 0.005
) -> float:
    """Calculate price with slippage."""
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
    """Calculate all transaction costs."""
    costs = {
        'brokerage': brokerage,
        'stt': value * stt_rate if is_sell else 0.0,
        'exchange_charges': value * exchange_rate,
        'gst': 0.0,
        'sebi_charges': value * sebi_rate,
        'stamp_duty': value * stamp_duty_rate if not is_sell else 0.0,
    }
    costs['gst'] = (costs['brokerage'] + costs['exchange_charges']) * gst_rate
    costs['total'] = sum(costs.values())
    return costs


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
    """Validate order parameters."""
    if not symbol:
        return False, "Symbol is required"
    if not exchange:
        return False, "Exchange is required"
    if transaction_type.upper() not in ['BUY', 'SELL']:
        return False, f"Invalid transaction type: {transaction_type}"
    if quantity <= 0:
        return False, f"Quantity must be positive: {quantity}"
    valid_order_types = ['MARKET', 'LIMIT', 'STOPLOSS', 'STOPLOSS_MARKET']
    if order_type.upper() not in valid_order_types:
        return False, f"Invalid order type: {order_type}"
    valid_product_types = ['INTRADAY', 'DELIVERY', 'CARRYFORWARD']
    if product_type.upper() not in valid_product_types:
        return False, f"Invalid product type: {product_type}"
    if order_type.upper() == 'LIMIT' and price <= 0:
        return False, "Price required for LIMIT orders"
    if order_type.upper() in ['STOPLOSS', 'STOPLOSS_MARKET'] and trigger_price <= 0:
        return False, "Trigger price required for STOPLOSS orders"
    return True, ""


def format_symbol_for_angel(
    underlying: str,
    expiry_date: datetime,
    strike: float,
    option_type: str
) -> str:
    """Format a symbol string for Angel One API."""
    year = expiry_date.strftime("%y")
    month = expiry_date.strftime("%b").upper()
    return f"{underlying}{year}{month}{int(strike)}{option_type.upper()}"


def parse_option_symbol(symbol: str) -> Optional[Dict[str, Any]]:
    """Parse an option symbol to extract components."""
    pattern = r'^([A-Z]+)(\d{2})([A-Z]{3})(\d+)(CE|PE)$'
    match = re.match(pattern, symbol)
    if not match:
        return None
    underlying, year, month, strike, option_type = match.groups()
    month_map = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
        'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
        'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }
    try:
        expiry = datetime(year=2000 + int(year), month=month_map[month], day=1)
    except (ValueError, KeyError):
        return None
    return {
        'underlying': underlying,
        'expiry': expiry,
        'strike': float(strike),
        'option_type': option_type
    }


def get_lot_size(symbol: str, exchange: str = "NFO") -> int:
    """Get lot size for a symbol."""
    lot_sizes = {
        'NIFTY': 50, 'BANKNIFTY': 15, 'FINNIFTY': 40,
        'MIDCPNIFTY': 75, 'SENSEX': 10, 'BANKEX': 15,
    }
    for underlying, lot_size in lot_sizes.items():
        if symbol.startswith(underlying):
            return lot_size
    return 1


def round_to_tick(price: float, tick_size: float = 0.05) -> float:
    """Round price to nearest tick size."""
    return round(round(price / tick_size) * tick_size, 2)


def is_market_open(exchange: str = "NSE") -> bool:
    """Check if market is currently open."""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close
