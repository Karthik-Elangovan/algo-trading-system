"""
Deployment Configuration Module

This module provides deployment-specific configurations for different
environments (development, staging, production).
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class Environment(Enum):
    """Deployment environment types."""
    DEVELOPMENT = "dev"
    STAGING = "staging"
    PRODUCTION = "prod"


@dataclass
class ResourceConfig:
    """Container resource configuration."""
    cpu: int  # CPU units (256 = 0.25 vCPU)
    memory: int  # Memory in MB
    min_instances: int = 1
    max_instances: int = 1
    desired_instances: int = 1


@dataclass
class DatabaseConfig:
    """Database configuration."""
    instance_class: str = "db.t3.micro"
    allocated_storage: int = 20  # GB
    max_allocated_storage: int = 100  # GB
    multi_az: bool = False
    backup_retention_days: int = 7
    delete_protection: bool = False


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    retention_days: int = 30
    enable_debug: bool = False


@dataclass
class ScalingConfig:
    """Auto-scaling configuration."""
    enabled: bool = False
    target_cpu_utilization: int = 70
    target_memory_utilization: int = 80
    scale_in_cooldown: int = 300
    scale_out_cooldown: int = 60


@dataclass
class EnvironmentConfig:
    """Complete environment configuration."""
    name: str
    environment: Environment
    aws_region: str = "ap-south-1"
    
    # Service configurations
    trading_resources: ResourceConfig = field(default_factory=lambda: ResourceConfig(cpu=256, memory=512))
    dashboard_resources: ResourceConfig = field(default_factory=lambda: ResourceConfig(cpu=256, memory=512))
    data_service_resources: ResourceConfig = field(default_factory=lambda: ResourceConfig(cpu=256, memory=512))
    
    # Database
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    
    # Logging
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # Scaling
    scaling: ScalingConfig = field(default_factory=ScalingConfig)
    
    # Feature flags
    paper_trading: bool = True
    enable_monitoring: bool = True
    enable_alerting: bool = False
    
    # Limits
    max_daily_trades: int = 10
    max_position_size: float = 100000.0
    max_portfolio_risk: float = 0.02


# Environment-specific configurations
DEVELOPMENT_CONFIG = EnvironmentConfig(
    name="development",
    environment=Environment.DEVELOPMENT,
    trading_resources=ResourceConfig(cpu=256, memory=512, min_instances=1, max_instances=2),
    dashboard_resources=ResourceConfig(cpu=256, memory=512),
    data_service_resources=ResourceConfig(cpu=256, memory=512),
    database=DatabaseConfig(
        instance_class="db.t3.micro",
        allocated_storage=20,
        multi_az=False,
        backup_retention_days=7,
        delete_protection=False
    ),
    logging=LoggingConfig(level="DEBUG", retention_days=7, enable_debug=True),
    scaling=ScalingConfig(enabled=False),
    paper_trading=True,
    enable_monitoring=True,
    enable_alerting=False,
    max_daily_trades=50,
    max_position_size=50000.0,
    max_portfolio_risk=0.05
)

STAGING_CONFIG = EnvironmentConfig(
    name="staging",
    environment=Environment.STAGING,
    trading_resources=ResourceConfig(cpu=512, memory=1024, min_instances=1, max_instances=2),
    dashboard_resources=ResourceConfig(cpu=256, memory=512),
    data_service_resources=ResourceConfig(cpu=256, memory=512),
    database=DatabaseConfig(
        instance_class="db.t3.small",
        allocated_storage=50,
        multi_az=False,
        backup_retention_days=7,
        delete_protection=False
    ),
    logging=LoggingConfig(level="DEBUG", retention_days=14, enable_debug=True),
    scaling=ScalingConfig(enabled=True, target_cpu_utilization=70),
    paper_trading=True,
    enable_monitoring=True,
    enable_alerting=True,
    max_daily_trades=20,
    max_position_size=75000.0,
    max_portfolio_risk=0.03
)

PRODUCTION_CONFIG = EnvironmentConfig(
    name="production",
    environment=Environment.PRODUCTION,
    trading_resources=ResourceConfig(
        cpu=1024, 
        memory=2048, 
        min_instances=2, 
        max_instances=5,
        desired_instances=2
    ),
    dashboard_resources=ResourceConfig(cpu=512, memory=1024),
    data_service_resources=ResourceConfig(cpu=512, memory=1024),
    database=DatabaseConfig(
        instance_class="db.t3.medium",
        allocated_storage=100,
        max_allocated_storage=500,
        multi_az=True,
        backup_retention_days=30,
        delete_protection=True
    ),
    logging=LoggingConfig(level="INFO", retention_days=90, enable_debug=False),
    scaling=ScalingConfig(
        enabled=True, 
        target_cpu_utilization=70,
        target_memory_utilization=80,
        scale_in_cooldown=300,
        scale_out_cooldown=60
    ),
    paper_trading=False,
    enable_monitoring=True,
    enable_alerting=True,
    max_daily_trades=10,
    max_position_size=100000.0,
    max_portfolio_risk=0.02
)

# Configuration mapping
CONFIGS: Dict[str, EnvironmentConfig] = {
    "dev": DEVELOPMENT_CONFIG,
    "development": DEVELOPMENT_CONFIG,
    "staging": STAGING_CONFIG,
    "prod": PRODUCTION_CONFIG,
    "production": PRODUCTION_CONFIG,
}


def get_config(environment: Optional[str] = None) -> EnvironmentConfig:
    """
    Get configuration for the specified environment.
    
    Args:
        environment: Environment name (dev, staging, prod).
                    If not specified, reads from ENVIRONMENT env var.
    
    Returns:
        EnvironmentConfig for the specified environment.
    
    Raises:
        ValueError: If environment is invalid.
    """
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "dev")
    
    env_lower = environment.lower()
    
    if env_lower not in CONFIGS:
        valid_envs = list(CONFIGS.keys())
        raise ValueError(
            f"Invalid environment: {environment}. "
            f"Valid environments: {valid_envs}"
        )
    
    return CONFIGS[env_lower]


def get_current_environment() -> Environment:
    """Get the current deployment environment."""
    config = get_config()
    return config.environment


def is_production() -> bool:
    """Check if running in production environment."""
    return get_current_environment() == Environment.PRODUCTION


def is_development() -> bool:
    """Check if running in development environment."""
    return get_current_environment() == Environment.DEVELOPMENT


# Export convenience functions and classes
__all__ = [
    "Environment",
    "ResourceConfig",
    "DatabaseConfig",
    "LoggingConfig",
    "ScalingConfig",
    "EnvironmentConfig",
    "get_config",
    "get_current_environment",
    "is_production",
    "is_development",
    "DEVELOPMENT_CONFIG",
    "STAGING_CONFIG",
    "PRODUCTION_CONFIG",
]
