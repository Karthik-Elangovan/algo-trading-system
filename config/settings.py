"""
Configuration settings for the algorithmic trading system.

This module contains all configurable parameters for strategies,
backtesting, and risk management.
"""

from typing import Dict, Any, Tuple

# Strategy Parameters for Premium Selling (Short Strangle)
PREMIUM_SELLING_CONFIG: Dict[str, Any] = {
    # Entry signal: IV Rank threshold (0-100)
    # Only enter when IV Rank > this value (high implied volatility)
    "iv_rank_entry_threshold": 70,
    
    # Delta range for strike selection (15-20 delta)
    # Short strangle uses OTM options at these delta values
    "delta_range": (0.15, 0.20),
    
    # Take profit at 50% of premium collected
    # Example: If collected ₹100 premium, exit when can buy back for ₹50
    "profit_target_pct": 0.50,
    
    # Stop loss at 150% of premium (2.5x initial credit)
    # Example: If collected ₹100 premium, stop loss when premium reaches ₹250
    "stop_loss_pct": 1.50,
    
    # Close positions 2-3 days before expiry to avoid gamma risk
    "days_before_expiry_exit": 3,
    
    # Risk 1-2% of capital per trade
    "position_size_pct": 0.02,
    
    # Minimum days to expiry for entry (avoid short-dated options)
    "min_days_to_expiry": 7,
    
    # Maximum days to expiry for entry (avoid far-dated options)
    "max_days_to_expiry": 45,
    
    # Underlying assets to trade
    "underlyings": ["NIFTY", "BANKNIFTY", "SENSEX"],
    
    # Lot sizes for different instruments
    "lot_sizes": {
        "NIFTY": 50,
        "BANKNIFTY": 15,
        "SENSEX": 10,
    },
}

# Backtesting Parameters
BACKTEST_CONFIG: Dict[str, Any] = {
    # Initial capital in INR (10 Lakhs)
    "initial_capital": 1_000_000,
    
    # Slippage as percentage of price (0.5% for options)
    "slippage_pct": 0.005,
    
    # Brokerage per order (flat fee)
    "brokerage_per_order": 20,
    
    # Securities Transaction Tax (STT) on sell side for options
    # Current rate: 0.05% on premium for options
    "stt_rate": 0.0005,
    
    # GST on brokerage (18%)
    "gst_rate": 0.18,
    
    # Stamp duty rate (varies by state, using typical value)
    "stamp_duty_rate": 0.00003,
    
    # Exchange transaction charges
    "exchange_charges_rate": 0.00053,
    
    # SEBI charges
    "sebi_charges_rate": 0.0000005,
    
    # Default bid-ask spread for options (in percentage)
    "default_bid_ask_spread_pct": 0.01,
    
    # Risk-free rate for Sharpe ratio calculation (7% for India)
    "risk_free_rate": 0.07,
    
    # Trading days per year for annualization
    "trading_days_per_year": 252,
    
    # Commission structure type ('flat', 'percentage', 'tiered')
    "commission_type": "flat",
}

# Risk Management Parameters
RISK_CONFIG: Dict[str, Any] = {
    # Maximum position size as percentage of capital
    "max_position_size_pct": 0.02,
    
    # Maximum total portfolio risk (sum of all position risks)
    "max_portfolio_risk_pct": 0.10,
    
    # Daily loss limit as percentage of capital
    # Stop trading for the day if this limit is breached
    "daily_loss_limit_pct": 0.05,
    
    # Weekly loss limit as percentage of capital
    "weekly_loss_limit_pct": 0.10,
    
    # Maximum number of concurrent positions
    "max_concurrent_positions": 5,
    
    # Maximum exposure to single underlying
    "max_single_underlying_exposure_pct": 0.05,
    
    # Margin requirement as percentage of notional value
    "margin_requirement_pct": 0.15,
    
    # Minimum capital buffer to keep (not for trading)
    "capital_buffer_pct": 0.20,
}

# Data Configuration
DATA_CONFIG: Dict[str, Any] = {
    # Default lookback period for IV Rank calculation (days)
    "iv_rank_lookback_30d": 30,
    "iv_rank_lookback_252d": 252,
    
    # Historical volatility calculation window (days)
    "hv_window": 20,
    
    # Data frequency
    "data_frequency": "1D",  # Daily data
    
    # Minimum data points required for calculations
    "min_data_points": 30,
}

# Instrument Configuration
INSTRUMENT_CONFIG: Dict[str, Dict[str, Any]] = {
    "NIFTY": {
        "lot_size": 50,
        "strike_interval": 50,
        "symbol": "NIFTY",
        "exchange": "NSE",
    },
    "BANKNIFTY": {
        "lot_size": 15,
        "strike_interval": 100,
        "symbol": "BANKNIFTY",
        "exchange": "NSE",
    },
    "SENSEX": {
        "lot_size": 10,
        "strike_interval": 100,
        "symbol": "SENSEX",
        "exchange": "BSE",
    },
}
