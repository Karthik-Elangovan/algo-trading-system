"""
Broker Configuration Settings.

Configuration for Angel One and paper trading brokers.

SECURITY NOTE: Sensitive credentials should be loaded from environment variables
or a separate secrets file excluded from version control (e.g., .env file).
Never commit actual API keys, passwords, or TOTP secrets to the repository.
"""

import os
from typing import Any, Dict

# Angel One SmartAPI Configuration
ANGEL_ONE_CONFIG: Dict[str, Any] = {
    "api_key": os.environ.get("ANGEL_ONE_API_KEY", ""),
    "client_id": os.environ.get("ANGEL_ONE_CLIENT_ID", ""),
    "password": os.environ.get("ANGEL_ONE_PASSWORD", ""),
    "totp_secret": os.environ.get("ANGEL_ONE_TOTP_SECRET", ""),
    "feed_token": None,
    "jwt_token": None,
    "refresh_token": None,
}

# General Broker Configuration
BROKER_CONFIG: Dict[str, Any] = {
    "mode": "paper",
    "default_exchange": "NFO",
    "default_product_type": "INTRADAY",
    "max_requests_per_second": 10,
    "max_orders_per_minute": 60,
    "max_retries": 3,
    "retry_delay_seconds": 1,
    "log_orders": True,
    "log_market_data": False,
}

# Paper Trading Configuration
PAPER_TRADING_CONFIG: Dict[str, Any] = {
    "initial_capital": 1_000_000,
    "slippage_pct": 0.005,
    "brokerage_per_order": 20,
    "stt_rate": 0.0005,
    "exchange_charges_rate": 0.00053,
    "gst_rate": 0.18,
    "sebi_charges_rate": 0.0000005,
    "stamp_duty_rate": 0.00003,
    "market_order_delay": 0.1,
    "limit_order_check_interval": 1.0,
}

# Risk Management Configuration
BROKER_RISK_CONFIG: Dict[str, Any] = {
    "max_order_value": 500_000,
    "max_quantity_per_order": 1000,
    "max_daily_loss": 50_000,
    "max_daily_trades": 100,
    "max_positions": 10,
    "max_exposure_per_symbol": 200_000,
}


def get_broker_config(mode: str = None) -> Dict[str, Any]:
    """Get broker configuration for specified mode."""
    mode = mode or BROKER_CONFIG.get("mode", "paper")
    
    config = {
        **BROKER_CONFIG,
        **BROKER_RISK_CONFIG,
    }
    
    if mode == "live":
        config.update({
            **ANGEL_ONE_CONFIG,
        })
    else:
        config.update(PAPER_TRADING_CONFIG)
    
    config["mode"] = mode
    return config


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate broker configuration."""
    required_paper = ["initial_capital", "slippage_pct"]
    required_live = ["api_key", "client_id", "password"]
    
    mode = config.get("mode", "paper")
    
    if mode == "paper":
        for key in required_paper:
            if key not in config or config[key] is None:
                raise ValueError(f"Missing required config: {key}")
    else:
        for key in required_live:
            if key not in config or not config[key]:
                raise ValueError(f"Missing required config for live trading: {key}")
    
    return True
