"""
Automation Configuration Module.

Configuration settings for automated trading and data management.
"""

from typing import Any, Dict

# Automation configuration
AUTOMATION_CONFIG: Dict[str, Any] = {
    # Trading automation settings
    "trading": {
        # Enable/disable trading automation
        "enabled": True,
        
        # Trading mode: "paper" for simulation, "live" for real trading
        "mode": "paper",
        
        # IMPORTANT: Must be set to True for live trading
        # This is a safety check to prevent accidental live trading
        "live_trading_confirmed": False,
        
        # Strategy execution interval in seconds
        "strategy_interval_seconds": 60,
        
        # Position check interval for stop-loss/take-profit monitoring
        "position_check_interval_seconds": 30,
        
        # Pre-market setup time (IST)
        "pre_market_time": "09:00",
        
        # Market open time (IST)
        "market_open_time": "09:15",
        
        # Market close time (IST)
        "market_close_time": "15:30",
        
        # Post-market cleanup time (IST)
        "post_market_time": "15:45",
        
        # Timezone for market hours
        "timezone": "Asia/Kolkata",
        
        # Maximum daily loss percentage before kill switch activates
        "max_daily_loss_pct": 0.05,
        
        # Maximum orders per minute (rate limiting)
        "max_orders_per_minute": 10,
        
        # Enable auto-execution of signals
        "auto_execute": True,
        
        # Enable auto stop-loss execution
        "auto_stop_loss": True,
        
        # Dry run mode (log signals without executing)
        "dry_run": False,
    },
    
    # Data pipeline settings
    "data": {
        # Enable/disable data automation
        "enabled": True,
        
        # Real-time data fetch interval in seconds
        "realtime_interval_seconds": 5,
        
        # Time to run EOD data update (IST)
        "eod_update_time": "16:00",
        
        # Symbols to track
        "symbols": ["NIFTY", "BANKNIFTY"],
        
        # Candle intervals to aggregate
        "intervals": ["1m", "5m", "15m", "1h", "1d"],
        
        # Directory for storing market data
        "data_directory": "data/market_data",
        
        # Timezone for data timestamps
        "timezone": "Asia/Kolkata",
        
        # Maximum retries for failed data fetches
        "max_retries": 3,
        
        # Delay between retries in seconds
        "retry_delay_seconds": 5,
        
        # Data retention period in days
        "retention_days": 30,
    },
    
    # Notification settings
    "notifications": {
        # Enable/disable notifications
        "enabled": False,
        
        # Notify on trade execution
        "on_trade": True,
        
        # Notify on errors
        "on_error": True,
        
        # Notify on engine state changes
        "on_state_change": True,
        
        # Notify on daily summary
        "on_daily_summary": True,
    },
    
    # Safety settings
    "safety": {
        # Maximum position size as percentage of capital
        "max_position_size_pct": 0.02,
        
        # Maximum concurrent positions
        "max_concurrent_positions": 5,
        
        # Daily loss limit percentage
        "daily_loss_limit_pct": 0.05,
        
        # Weekly loss limit percentage
        "weekly_loss_limit_pct": 0.10,
        
        # Require confirmation for live trading
        "require_live_confirmation": True,
    },
}


def get_automation_config() -> Dict[str, Any]:
    """
    Get the full automation configuration.
    
    Returns:
        Dictionary with automation configuration
    """
    return AUTOMATION_CONFIG.copy()


def get_trading_config() -> Dict[str, Any]:
    """
    Get trading automation configuration.
    
    Returns:
        Dictionary with trading configuration
    """
    return AUTOMATION_CONFIG.get("trading", {}).copy()


def get_data_config() -> Dict[str, Any]:
    """
    Get data pipeline configuration.
    
    Returns:
        Dictionary with data configuration
    """
    return AUTOMATION_CONFIG.get("data", {}).copy()


def get_notification_config() -> Dict[str, Any]:
    """
    Get notification configuration.
    
    Returns:
        Dictionary with notification configuration
    """
    return AUTOMATION_CONFIG.get("notifications", {}).copy()


def get_safety_config() -> Dict[str, Any]:
    """
    Get safety configuration.
    
    Returns:
        Dictionary with safety configuration
    """
    return AUTOMATION_CONFIG.get("safety", {}).copy()


def validate_automation_config(config: Dict[str, Any]) -> bool:
    """
    Validate automation configuration.
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        True if configuration is valid
        
    Raises:
        ValueError: If configuration is invalid
    """
    # Validate trading config
    trading = config.get("trading", {})
    if trading.get("enabled", False):
        if trading.get("mode") not in ["paper", "live"]:
            raise ValueError("Trading mode must be 'paper' or 'live'")
        
        if trading.get("strategy_interval_seconds", 0) < 1:
            raise ValueError("Strategy interval must be at least 1 second")
        
        if trading.get("mode") == "live" and not trading.get("live_trading_confirmed"):
            raise ValueError("Live trading requires 'live_trading_confirmed' to be True")
    
    # Validate data config
    data = config.get("data", {})
    if data.get("enabled", False):
        valid_intervals = ["1m", "5m", "15m", "30m", "1h", "1d"]
        for interval in data.get("intervals", []):
            if interval not in valid_intervals:
                raise ValueError(f"Invalid interval: {interval}")
        
        if data.get("realtime_interval_seconds", 0) < 1:
            raise ValueError("Realtime interval must be at least 1 second")
    
    return True


def create_paper_trading_config() -> Dict[str, Any]:
    """
    Create a configuration for paper trading.
    
    Returns:
        Dictionary with paper trading configuration
    """
    config = get_automation_config()
    config["trading"]["mode"] = "paper"
    config["trading"]["live_trading_confirmed"] = False
    return config


def create_live_trading_config(confirmed: bool = False) -> Dict[str, Any]:
    """
    Create a configuration for live trading.
    
    Args:
        confirmed: Whether live trading is confirmed
        
    Returns:
        Dictionary with live trading configuration
    """
    config = get_automation_config()
    config["trading"]["mode"] = "live"
    config["trading"]["live_trading_confirmed"] = confirmed
    return config
