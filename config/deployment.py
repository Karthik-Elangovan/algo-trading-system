"""
Deployment Configuration for Algo Trading System

This module contains all deployment-related configurations including
environment settings, feature flags, and operational parameters.
"""

import os
from typing import Dict, Any
from enum import Enum


class Environment(Enum):
    """Deployment environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


def get_environment() -> Environment:
    """Get the current environment from environment variable."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    return Environment(env) if env in [e.value for e in Environment] else Environment.DEVELOPMENT


# =============================================================================
# Deployment Configuration
# =============================================================================
DEPLOYMENT_CONFIG: Dict[str, Any] = {
    # Environment settings
    "environment": os.getenv("ENVIRONMENT", "development"),
    "log_level": os.getenv("LOG_LEVEL", "INFO"),
    
    # Feature flags
    "trading_enabled": os.getenv("TRADING_ENABLED", "true").lower() == "true",
    "paper_trading": os.getenv("PAPER_TRADING", "true").lower() == "true",
    
    # Trading limits
    "max_daily_trades": int(os.getenv("MAX_DAILY_TRADES", "50")),
    "max_daily_loss": float(os.getenv("MAX_DAILY_LOSS", "50000")),  # INR
    
    # Health check settings
    "health_check_interval": int(os.getenv("HEALTH_CHECK_INTERVAL", "60")),
    "health_check_timeout": int(os.getenv("HEALTH_CHECK_TIMEOUT", "30")),
    
    # API settings
    "api_rate_limit": int(os.getenv("API_RATE_LIMIT", "10")),  # requests per second
    "api_timeout": int(os.getenv("API_TIMEOUT", "30")),  # seconds
    
    # Data settings
    "data_retention_days": int(os.getenv("DATA_RETENTION_DAYS", "365")),
    "backtest_result_retention_days": int(os.getenv("BACKTEST_RETENTION_DAYS", "90")),
}

# =============================================================================
# Service Configuration
# =============================================================================
SERVICE_CONFIG: Dict[str, Any] = {
    "trading_engine": {
        "enabled": True,
        "port": int(os.getenv("TRADING_PORT", "8000")),
        "workers": int(os.getenv("TRADING_WORKERS", "1")),
        "graceful_shutdown_timeout": 30,
    },
    "dashboard": {
        "enabled": True,
        "port": int(os.getenv("DASHBOARD_PORT", "8501")),
        "host": os.getenv("DASHBOARD_HOST", "0.0.0.0"),
    },
    "data_service": {
        "enabled": True,
        "port": int(os.getenv("DATA_SERVICE_PORT", "8080")),
        "cache_ttl": int(os.getenv("DATA_CACHE_TTL", "300")),
    },
}

# =============================================================================
# Broker Configuration
# =============================================================================
BROKER_CONFIG: Dict[str, Any] = {
    "name": "angel_one",
    "api_key": os.getenv("ANGEL_ONE_API_KEY", ""),
    "client_id": os.getenv("ANGEL_ONE_CLIENT_ID", ""),
    "password": os.getenv("ANGEL_ONE_PASSWORD", ""),
    "totp_secret": os.getenv("ANGEL_ONE_TOTP_SECRET", ""),
    
    # Connection settings
    "timeout": int(os.getenv("BROKER_TIMEOUT", "30")),
    "retry_attempts": int(os.getenv("BROKER_RETRY_ATTEMPTS", "3")),
    "retry_delay": int(os.getenv("BROKER_RETRY_DELAY", "5")),
    
    # Trading session times (IST)
    "market_open": "09:15",
    "market_close": "15:30",
    "pre_open_start": "09:00",
    "post_close_end": "16:00",
}

# =============================================================================
# Database Configuration
# =============================================================================
DATABASE_CONFIG: Dict[str, Any] = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "name": os.getenv("DB_NAME", "algotrading"),
    "user": os.getenv("DB_USER", "admin"),
    "password": os.getenv("DB_PASSWORD", ""),
    
    # Connection pool settings
    "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
    "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
    "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
}

# =============================================================================
# AWS Configuration
# =============================================================================
AWS_CONFIG: Dict[str, Any] = {
    "region": os.getenv("AWS_DEFAULT_REGION", "ap-south-1"),
    "s3_bucket": os.getenv("S3_BUCKET", ""),
    "cloudwatch_log_group": os.getenv("CLOUDWATCH_LOG_GROUP", "/aws/ecs/algo-trading"),
    
    # Secrets Manager
    "secrets_arn": os.getenv("SECRETS_ARN", ""),
}

# =============================================================================
# Monitoring Configuration
# =============================================================================
MONITORING_CONFIG: Dict[str, Any] = {
    # Metrics
    "metrics_enabled": os.getenv("METRICS_ENABLED", "true").lower() == "true",
    "metrics_namespace": "AlgoTrading",
    "metrics_interval": int(os.getenv("METRICS_INTERVAL", "60")),
    
    # Logging
    "log_format": os.getenv("LOG_FORMAT", "json"),
    "log_level": os.getenv("LOG_LEVEL", "INFO"),
    
    # Alerting
    "alerts_enabled": os.getenv("ALERTS_ENABLED", "true").lower() == "true",
    "alert_email": os.getenv("ALERT_EMAIL", ""),
    "slack_webhook": os.getenv("SLACK_WEBHOOK", ""),
}

# =============================================================================
# Environment-specific Overrides
# =============================================================================
ENVIRONMENT_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "development": {
        "log_level": "DEBUG",
        "paper_trading": True,
        "max_daily_trades": 10,
        "trading_enabled": True,
    },
    "staging": {
        "log_level": "DEBUG",
        "paper_trading": True,
        "max_daily_trades": 25,
        "trading_enabled": True,
    },
    "production": {
        "log_level": "INFO",
        "paper_trading": False,
        "max_daily_trades": 50,
        "trading_enabled": True,
    },
}


def get_config() -> Dict[str, Any]:
    """
    Get the complete configuration with environment-specific overrides.
    
    Returns:
        Dictionary containing all configuration settings
    """
    env = get_environment().value
    config = {
        "deployment": DEPLOYMENT_CONFIG.copy(),
        "services": SERVICE_CONFIG.copy(),
        "broker": BROKER_CONFIG.copy(),
        "database": DATABASE_CONFIG.copy(),
        "aws": AWS_CONFIG.copy(),
        "monitoring": MONITORING_CONFIG.copy(),
    }
    
    # Apply environment-specific overrides
    if env in ENVIRONMENT_OVERRIDES:
        for key, value in ENVIRONMENT_OVERRIDES[env].items():
            if key in config["deployment"]:
                config["deployment"][key] = value
    
    return config


def validate_config() -> tuple[bool, list[str]]:
    """
    Validate the configuration for required settings.
    
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    config = get_config()
    
    # Check required broker settings for production
    if config["deployment"]["environment"] == "production":
        if not config["deployment"]["paper_trading"]:
            if not config["broker"]["api_key"]:
                errors.append("ANGEL_ONE_API_KEY is required for live trading")
            if not config["broker"]["client_id"]:
                errors.append("ANGEL_ONE_CLIENT_ID is required for live trading")
    
    # Check database settings
    if not config["database"]["host"]:
        errors.append("DB_HOST is required")
    
    return len(errors) == 0, errors
