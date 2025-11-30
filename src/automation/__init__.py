"""
Automation Module for Algo Trading System.

This module provides comprehensive automation for trading execution
and data management, including:
- Trading scheduler for strategy execution
- Data pipelines for market data management
- Central automation engine for coordinating all activities
"""

from .market_hours import MarketHours, is_market_open, get_next_market_open
from .trading_scheduler import TradingScheduler
from .data_pipeline import DataPipeline
from .engine import AutomationEngine

__all__ = [
    'MarketHours',
    'is_market_open',
    'get_next_market_open',
    'TradingScheduler',
    'DataPipeline',
    'AutomationEngine',
]
