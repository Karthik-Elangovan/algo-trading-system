# Automation Module

This document describes the comprehensive automation system for trading execution and data management in the algo-trading-system.

## Overview

The automation module provides:
- **Trading Scheduler**: Automated strategy execution at configurable intervals
- **Data Pipeline**: Automated market data fetching and management
- **Automation Engine**: Central coordinator for all automated activities

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   AutomationEngine                           │
│  ┌────────────────────┐    ┌────────────────────────────┐   │
│  │  TradingScheduler  │    │      DataPipeline          │   │
│  │  ┌──────────────┐  │    │  ┌────────────────────┐    │   │
│  │  │ Strategy     │  │    │  │ Real-time Fetcher  │    │   │
│  │  │ Execution    │  │    │  └────────────────────┘    │   │
│  │  └──────────────┘  │    │  ┌────────────────────┐    │   │
│  │  ┌──────────────┐  │    │  │ EOD Updater        │    │   │
│  │  │ Position     │  │    │  └────────────────────┘    │   │
│  │  │ Monitor      │  │    │  ┌────────────────────┐    │   │
│  │  └──────────────┘  │    │  │ Data Aggregator    │    │   │
│  │  ┌──────────────┐  │    │  └────────────────────┘    │   │
│  │  │ Pre/Post     │  │    │  ┌────────────────────┐    │   │
│  │  │ Market Tasks │  │    │  │ Cleanup Jobs       │    │   │
│  │  └──────────────┘  │    │  └────────────────────┘    │   │
│  └────────────────────┘    └────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  MarketHours    │
                    │  (IST Timing)   │
                    └─────────────────┘
```

## Quick Start

### Basic Usage

```python
from src.automation import AutomationEngine
from config.automation_config import AUTOMATION_CONFIG

# Create engine with default configuration
engine = AutomationEngine(mode='paper', config=AUTOMATION_CONFIG)

# Start automation
engine.start()

# Check status
print(engine.get_status())

# Stop automation
engine.stop()
```

### Adding a Strategy

```python
from src.strategies.premium_selling import PremiumSellingStrategy

# Create strategy instance
strategy = PremiumSellingStrategy()

# Add to automation engine
engine.add_strategy(strategy, interval_seconds=60)
```

### Running Forever

```python
# Run until interrupted (Ctrl+C)
engine.run_forever()
```

## Configuration

### Configuration File

The main configuration is in `config/automation_config.py`:

```python
AUTOMATION_CONFIG = {
    "trading": {
        "enabled": True,
        "mode": "paper",  # "paper" or "live"
        "live_trading_confirmed": False,  # Must be True for live trading
        "strategy_interval_seconds": 60,
        "position_check_interval_seconds": 30,
        "pre_market_time": "09:00",
        "market_open_time": "09:15",
        "market_close_time": "15:30",
        "post_market_time": "15:45",
        "timezone": "Asia/Kolkata",
        "max_daily_loss_pct": 0.05,
        "auto_execute": True,
        "dry_run": False,
    },
    "data": {
        "enabled": True,
        "realtime_interval_seconds": 5,
        "eod_update_time": "16:00",
        "symbols": ["NIFTY", "BANKNIFTY"],
        "intervals": ["1m", "5m", "15m", "1h", "1d"],
        "data_directory": "data/market_data",
    },
    "notifications": {
        "enabled": False,
        "on_trade": True,
        "on_error": True,
    },
}
```

### Configuration Options

#### Trading Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | `True` | Enable/disable trading automation |
| `mode` | str | `"paper"` | Trading mode: `"paper"` or `"live"` |
| `live_trading_confirmed` | bool | `False` | Must be `True` for live trading |
| `strategy_interval_seconds` | int | `60` | Strategy execution interval |
| `position_check_interval_seconds` | int | `30` | Position monitoring interval |
| `max_daily_loss_pct` | float | `0.05` | Maximum daily loss before kill switch |
| `auto_execute` | bool | `True` | Auto-execute strategy signals |
| `dry_run` | bool | `False` | Log signals without executing |

#### Data Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | `True` | Enable/disable data automation |
| `realtime_interval_seconds` | int | `5` | Real-time data fetch interval |
| `eod_update_time` | str | `"16:00"` | Time for EOD data download |
| `symbols` | list | `["NIFTY", "BANKNIFTY"]` | Symbols to track |
| `intervals` | list | `["1m", "5m", "15m", "1h", "1d"]` | Candle intervals |
| `data_directory` | str | `"data/market_data"` | Directory for data storage |

## Components

### MarketHours

Handles Indian stock market timing (NSE: 9:15 AM - 3:30 PM IST).

```python
from src.automation import MarketHours, is_market_open

# Using class
market_hours = MarketHours()
print(market_hours.is_market_open())
print(market_hours.get_market_state())  # 'pre_market', 'open', 'post_market', 'closed'
print(market_hours.get_next_market_open())

# Using module functions
print(is_market_open())
```

### TradingScheduler

Manages strategy execution and position monitoring.

```python
from src.automation import TradingScheduler
from src.execution.broker import BrokerFactory

broker = BrokerFactory.create('paper')
scheduler = TradingScheduler(broker=broker, mode='paper')

# Add tasks
scheduler.add_strategy_task(my_strategy.generate_signal, interval_seconds=60)
scheduler.add_position_monitor(interval_seconds=30)
scheduler.add_pre_market_task(pre_market_setup, time_str="09:00")
scheduler.add_post_market_task(post_market_cleanup, time_str="15:45")

# Control
scheduler.start()
scheduler.pause()
scheduler.resume()
scheduler.stop()

# Emergency stop
scheduler.activate_kill_switch()
```

### DataPipeline

Manages market data fetching and storage.

```python
from src.automation import DataPipeline

pipeline = DataPipeline(
    data_directory='data/market_data',
    symbols=['NIFTY', 'BANKNIFTY'],
    intervals=['1m', '5m', '15m'],
)

# Control
pipeline.start()
pipeline.stop()

# Get data
candles = pipeline.get_candles('NIFTY', '5m', count=100)
latest_tick = pipeline.get_latest_tick('NIFTY')
```

### AutomationEngine

Central coordinator for all automation components.

```python
from src.automation import AutomationEngine

engine = AutomationEngine(
    mode='paper',
    config=AUTOMATION_CONFIG,
    broker=my_broker,
    data_provider=my_provider,
)

# Lifecycle
engine.start()
engine.pause()
engine.resume()
engine.stop()

# Add components
engine.add_strategy(my_strategy)
engine.add_symbol('SENSEX')
engine.add_pre_market_task(setup_func)
engine.add_post_market_task(cleanup_func)

# Monitoring
status = engine.get_status()
health = engine.health_check()

# Emergency
engine.activate_kill_switch()
engine.deactivate_kill_switch()
```

## Safety Features

### Kill Switch

The kill switch immediately stops all automated trading:

```python
# Activate kill switch
engine.activate_kill_switch()

# Deactivate when ready
engine.deactivate_kill_switch()
```

### Daily Loss Limit

Automatically activates kill switch when daily loss exceeds threshold:

```python
config = {
    'trading': {
        'max_daily_loss_pct': 0.05,  # 5% daily loss limit
    }
}
```

### Live Trading Confirmation

Live trading requires explicit confirmation:

```python
config = {
    'trading': {
        'mode': 'live',
        'live_trading_confirmed': True,  # Must be True for live trading
    }
}
```

### Dry Run Mode

Test signals without actual execution:

```python
config = {
    'trading': {
        'dry_run': True,  # Log signals but don't execute
    }
}
```

### Rate Limiting

Prevent excessive order placement:

```python
config = {
    'trading': {
        'max_orders_per_minute': 10,
    }
}
```

## Market Hours

The system respects Indian market timing:

| Session | Time (IST) |
|---------|------------|
| Pre-Market | 09:00 - 09:15 |
| Market Open | 09:15 - 15:30 |
| Post-Market | 15:30 - 15:45 |

NSE holidays are automatically handled.

## Data Storage

Data is stored in the following structure:

```
data/market_data/
├── ticks/
│   ├── NIFTY_20240115.csv
│   └── BANKNIFTY_20240115.csv
├── candles/
│   ├── NIFTY_1m_20240115.csv
│   ├── NIFTY_5m_20240115.csv
│   └── ...
└── eod/
    ├── NIFTY_eod.csv
    └── BANKNIFTY_eod.csv
```

## Notifications

Register custom notification handlers:

```python
def my_notification_handler(event_type, data):
    if event_type == 'engine_started':
        print(f"Engine started: {data}")
    elif event_type == 'engine_error':
        send_alert(data['error'])

engine.register_notification_handler(my_notification_handler)
```

Notification events:
- `engine_started`
- `engine_stopped`
- `engine_paused`
- `engine_resumed`
- `engine_error`
- `kill_switch_activated`
- `kill_switch_deactivated`

## Commands

### Start Automation

```bash
# Paper trading
python -c "
from src.automation import AutomationEngine
from config.automation_config import AUTOMATION_CONFIG
engine = AutomationEngine(mode='paper', config=AUTOMATION_CONFIG)
engine.run_forever()
"
```

### Check Status

```python
from src.automation import AutomationEngine
engine = AutomationEngine(mode='paper')
engine.start()
print(engine.get_status())
print(engine.health_check())
```

## Testing

Run automation tests:

```bash
pytest tests/test_automation.py -v
```

## Best Practices

1. **Always start with paper trading** before going live
2. **Set conservative loss limits** initially
3. **Monitor health checks** regularly
4. **Use dry_run mode** to test strategy signals
5. **Keep notifications enabled** for important events
6. **Review logs** for any errors or warnings
7. **Test kill switch** functionality before live trading

## Troubleshooting

### Engine Won't Start

- Check if `live_trading_confirmed` is `True` for live mode
- Verify broker is authenticated
- Check for configuration errors

### No Signals Generated

- Verify market hours
- Check strategy configuration
- Review strategy logs

### Data Not Saving

- Check data directory permissions
- Verify disk space
- Check for data validation errors

## API Reference

See the module docstrings for detailed API documentation:
- `src/automation/market_hours.py`
- `src/automation/trading_scheduler.py`
- `src/automation/data_pipeline.py`
- `src/automation/engine.py`
