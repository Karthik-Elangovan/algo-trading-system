"""
Angel One (SmartAPI) Broker Integration.

This module provides integration with Angel One's SmartAPI for
live trading capabilities including authentication, market data,
order execution, and position management.
"""

from .live_broker import AngelOneBroker

__all__ = [
    'AngelOneBroker',
]
