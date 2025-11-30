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

# Iron Condor Strategy Configuration
IRON_CONDOR_CONFIG: Dict[str, Any] = {
    # Entry signal: IV Rank threshold (0-100)
    # Only enter when IV Rank > this value (moderate to high IV)
    "iv_rank_entry_threshold": 50,
    
    # Delta range for short strike selection (15-20 delta)
    "short_delta_range": (0.15, 0.20),
    
    # Wing width for protection (points from short strikes)
    "wing_width": {"NIFTY": 50, "BANKNIFTY": 100, "SENSEX": 100},
    
    # Take profit at 50% of credit received
    "profit_target_pct": 0.50,
    
    # Stop loss at 200% of credit (or when short strike is breached)
    "stop_loss_pct": 2.00,
    
    # Close positions 5-7 days before expiry
    "days_before_expiry_exit": 7,
    
    # Minimum days to expiry for entry
    "min_days_to_expiry": 14,
    
    # Maximum days to expiry for entry
    "max_days_to_expiry": 45,
    
    # Risk 2% of capital per trade based on max loss
    "position_size_pct": 0.02,
    
    # Lot sizes for different instruments
    "lot_sizes": {
        "NIFTY": 50,
        "BANKNIFTY": 15,
        "SENSEX": 10,
    },
    
    # Maximum concurrent positions
    "max_positions": 3,
}

# Calendar Spread Strategy Configuration
CALENDAR_SPREAD_CONFIG: Dict[str, Any] = {
    # Entry signal: IV Rank threshold (0-100)
    # Enter when IV Rank < this value (low IV - expecting IV expansion)
    "iv_rank_entry_threshold": 30,
    
    # Entry condition: Enter when IV Rank < threshold (low IV environment)
    "iv_rank_entry_below": True,
    
    # Strike selection: "ATM" or "OTM"
    "strike_selection": "ATM",
    
    # Near expiry: 7-14 days
    "near_expiry_days_range": (7, 14),
    
    # Far expiry: 30-45 days
    "far_expiry_days_range": (30, 45),
    
    # Take profit at 25-50% of debit paid (using middle value)
    "profit_target_pct": 0.35,
    
    # Stop loss at 50% of debit paid
    "stop_loss_pct": 0.50,
    
    # Close when near-term option has 2-3 days to expiry
    "days_before_near_expiry_exit": 3,
    
    # Risk 1.5% of capital per trade
    "position_size_pct": 0.015,
    
    # Lot sizes for different instruments
    "lot_sizes": {
        "NIFTY": 50,
        "BANKNIFTY": 15,
        "SENSEX": 10,
    },
    
    # Maximum concurrent positions
    "max_positions": 3,
}

# Ratio Spread Strategy Configuration
RATIO_SPREAD_CONFIG: Dict[str, Any] = {
    # Entry signal: IV Rank threshold (0-100)
    # Only enter when IV Rank > this value (high IV for selling extra options)
    "iv_rank_entry_threshold": 60,
    
    # Ratio: Buy 1, Sell 2 (can adjust to 1:3 in very high IV)
    "ratio": (1, 2),
    
    # Long option delta: 0.50 = ATM
    "long_delta": 0.50,
    
    # Short option delta range: 20-25 delta
    "short_delta_range": (0.20, 0.25),
    
    # Take profit at 75% of max profit
    "profit_target_pct": 0.75,
    
    # Exit if underlying moves 2% beyond short strike
    "stop_loss_breach_pct": 0.02,
    
    # Close 7 days before expiry
    "days_before_expiry_exit": 7,
    
    # Minimum days to expiry for entry
    "min_days_to_expiry": 21,
    
    # Maximum days to expiry for entry
    "max_days_to_expiry": 45,
    
    # Risk 1% of capital per trade (lower due to higher risk)
    "position_size_pct": 0.01,
    
    # Lot sizes for different instruments
    "lot_sizes": {
        "NIFTY": 50,
        "BANKNIFTY": 15,
        "SENSEX": 10,
    },
    
    # Maximum concurrent positions
    "max_positions": 2,
}
