"""
Execution modules for broker integration.

This module provides broker integration for live and paper trading,
including Angel One SmartAPI integration.

Components:
- broker: Abstract broker interface and factory
- paper_broker: Paper trading simulation broker
- angel_one: Angel One SmartAPI integration modules
- utils: Helper functions for broker operations
"""

from .broker import (
    BaseBroker,
    BrokerFactory,
    Order,
    Position,
    Holding,
    Quote,
    AccountInfo,
    OrderType,
    TransactionType,
    ProductType,
    Exchange,
    OrderStatus,
    BrokerError,
    AuthenticationError,
    OrderError,
)

from .paper_broker import PaperBroker

from .utils import (
    generate_order_id,
    calculate_slippage,
    calculate_transaction_costs,
    validate_order_params,
    format_symbol_for_angel,
    parse_option_symbol,
    get_lot_size,
    round_to_tick,
    is_market_open,
)

# Import angel_one module to register the live broker
from . import angel_one

__all__ = [
    # Broker classes
    'BaseBroker',
    'BrokerFactory',
    'PaperBroker',
    
    # Data classes
    'Order',
    'Position',
    'Holding',
    'Quote',
    'AccountInfo',
    
    # Enums
    'OrderType',
    'TransactionType',
    'ProductType',
    'Exchange',
    'OrderStatus',
    
    # Exceptions
    'BrokerError',
    'AuthenticationError',
    'OrderError',
    
    # Utility functions
    'generate_order_id',
    'calculate_slippage',
    'calculate_transaction_costs',
    'validate_order_params',
    'format_symbol_for_angel',
    'parse_option_symbol',
    'get_lot_size',
    'round_to_tick',
    'is_market_open',
    
    # Submodules
    'angel_one',
]
