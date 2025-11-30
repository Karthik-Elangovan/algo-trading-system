"""
Tests for Automation Module.

Comprehensive tests for:
- Market hours utilities
- Trading scheduler
- Data pipeline
- Automation engine
"""

import pytest
import time
import threading
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from zoneinfo import ZoneInfo
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.automation.market_hours import (
    MarketHours,
    is_market_open,
    get_next_market_open,
    is_trading_day,
    get_market_state,
    IST,
)
from src.automation.trading_scheduler import TradingScheduler, ScheduledTask
from src.automation.data_pipeline import DataPipeline, DataFetchJob
from src.automation.engine import AutomationEngine, EngineMode, EngineState
from config.automation_config import (
    AUTOMATION_CONFIG,
    get_automation_config,
    get_trading_config,
    get_data_config,
    validate_automation_config,
    create_paper_trading_config,
    create_live_trading_config,
)


class TestMarketHours:
    """Tests for MarketHours class."""
    
    @pytest.fixture
    def market_hours(self):
        """Create MarketHours instance."""
        return MarketHours()
    
    def test_initialization(self, market_hours):
        """Test MarketHours initializes correctly."""
        assert market_hours is not None
        assert market_hours.market_open == dt_time(9, 15)
        assert market_hours.market_close == dt_time(15, 30)
        assert market_hours.pre_market == dt_time(9, 0)
        assert market_hours.post_market == dt_time(15, 45)
    
    def test_custom_market_times(self):
        """Test custom market times."""
        custom = MarketHours(
            market_open=dt_time(10, 0),
            market_close=dt_time(16, 0),
        )
        assert custom.market_open == dt_time(10, 0)
        assert custom.market_close == dt_time(16, 0)
    
    def test_is_trading_day_weekday(self, market_hours):
        """Test is_trading_day for weekdays."""
        # Monday
        monday = datetime(2024, 1, 15, tzinfo=IST)
        assert market_hours.is_trading_day(monday) is True
        
        # Friday
        friday = datetime(2024, 1, 19, tzinfo=IST)
        assert market_hours.is_trading_day(friday) is True
    
    def test_is_trading_day_weekend(self, market_hours):
        """Test is_trading_day for weekends."""
        # Saturday
        saturday = datetime(2024, 1, 13, tzinfo=IST)
        assert market_hours.is_trading_day(saturday) is False
        
        # Sunday
        sunday = datetime(2024, 1, 14, tzinfo=IST)
        assert market_hours.is_trading_day(sunday) is False
    
    def test_is_trading_day_holiday(self, market_hours):
        """Test is_trading_day for holidays."""
        # Republic Day
        republic_day = datetime(2024, 1, 26, tzinfo=IST)
        assert market_hours.is_trading_day(republic_day) is False
    
    def test_is_market_open_during_hours(self, market_hours):
        """Test is_market_open during trading hours."""
        # 10:00 AM on a Monday
        dt = datetime(2024, 1, 15, 10, 0, tzinfo=IST)
        assert market_hours.is_market_open(dt) is True
        
        # 2:00 PM on a Monday
        dt = datetime(2024, 1, 15, 14, 0, tzinfo=IST)
        assert market_hours.is_market_open(dt) is True
    
    def test_is_market_open_outside_hours(self, market_hours):
        """Test is_market_open outside trading hours."""
        # 8:00 AM - before market open
        dt = datetime(2024, 1, 15, 8, 0, tzinfo=IST)
        assert market_hours.is_market_open(dt) is False
        
        # 4:00 PM - after market close
        dt = datetime(2024, 1, 15, 16, 0, tzinfo=IST)
        assert market_hours.is_market_open(dt) is False
    
    def test_is_market_open_at_boundaries(self, market_hours):
        """Test is_market_open at boundary times."""
        # Exactly at market open (9:15)
        dt = datetime(2024, 1, 15, 9, 15, tzinfo=IST)
        assert market_hours.is_market_open(dt) is True
        
        # Exactly at market close (15:30)
        dt = datetime(2024, 1, 15, 15, 30, tzinfo=IST)
        assert market_hours.is_market_open(dt) is False
    
    def test_is_pre_market(self, market_hours):
        """Test is_pre_market detection."""
        # 9:05 AM - in pre-market
        dt = datetime(2024, 1, 15, 9, 5, tzinfo=IST)
        assert market_hours.is_pre_market(dt) is True
        
        # 10:00 AM - not in pre-market
        dt = datetime(2024, 1, 15, 10, 0, tzinfo=IST)
        assert market_hours.is_pre_market(dt) is False
    
    def test_is_post_market(self, market_hours):
        """Test is_post_market detection."""
        # 3:40 PM - in post-market
        dt = datetime(2024, 1, 15, 15, 40, tzinfo=IST)
        assert market_hours.is_post_market(dt) is True
        
        # 4:00 PM - not in post-market
        dt = datetime(2024, 1, 15, 16, 0, tzinfo=IST)
        assert market_hours.is_post_market(dt) is False
    
    def test_get_market_state(self, market_hours):
        """Test get_market_state returns correct states."""
        # Pre-market
        dt = datetime(2024, 1, 15, 9, 5, tzinfo=IST)
        assert market_hours.get_market_state(dt) == 'pre_market'
        
        # Open
        dt = datetime(2024, 1, 15, 10, 0, tzinfo=IST)
        assert market_hours.get_market_state(dt) == 'open'
        
        # Post-market
        dt = datetime(2024, 1, 15, 15, 35, tzinfo=IST)
        assert market_hours.get_market_state(dt) == 'post_market'
        
        # Closed
        dt = datetime(2024, 1, 15, 18, 0, tzinfo=IST)
        assert market_hours.get_market_state(dt) == 'closed'
    
    def test_get_next_market_open(self, market_hours):
        """Test get_next_market_open."""
        # Before market open on a trading day
        dt = datetime(2024, 1, 15, 8, 0, tzinfo=IST)
        next_open = market_hours.get_next_market_open(dt)
        assert next_open.hour == 9
        assert next_open.minute == 15
        assert next_open.date() == dt.date()
    
    def test_get_next_market_open_after_close(self, market_hours):
        """Test get_next_market_open after market close."""
        # After market close
        dt = datetime(2024, 1, 15, 16, 0, tzinfo=IST)
        next_open = market_hours.get_next_market_open(dt)
        assert next_open.date() > dt.date()
    
    def test_get_next_market_open_weekend(self, market_hours):
        """Test get_next_market_open on weekend."""
        # Saturday
        dt = datetime(2024, 1, 13, 10, 0, tzinfo=IST)
        next_open = market_hours.get_next_market_open(dt)
        # Should be Monday
        assert next_open.weekday() == 0
    
    def test_get_next_market_close(self, market_hours):
        """Test get_next_market_close."""
        # During market hours
        dt = datetime(2024, 1, 15, 10, 0, tzinfo=IST)
        next_close = market_hours.get_next_market_close(dt)
        assert next_close.hour == 15
        assert next_close.minute == 30
        assert next_close.date() == dt.date()
    
    def test_time_to_market_open(self, market_hours):
        """Test time_to_market_open."""
        # Before market open
        dt = datetime(2024, 1, 15, 8, 15, tzinfo=IST)
        time_to_open = market_hours.time_to_market_open(dt)
        assert time_to_open == timedelta(hours=1)
    
    def test_time_to_market_open_when_open(self, market_hours):
        """Test time_to_market_open when market is open."""
        # During market hours
        dt = datetime(2024, 1, 15, 10, 0, tzinfo=IST)
        time_to_open = market_hours.time_to_market_open(dt)
        assert time_to_open == timedelta(0)
    
    def test_get_trading_minutes_elapsed(self, market_hours):
        """Test get_trading_minutes_elapsed."""
        # 1 hour after market open
        dt = datetime(2024, 1, 15, 10, 15, tzinfo=IST)
        minutes = market_hours.get_trading_minutes_elapsed(dt)
        assert minutes == 60
    
    def test_get_trading_minutes_remaining(self, market_hours):
        """Test get_trading_minutes_remaining."""
        # 30 minutes before close
        dt = datetime(2024, 1, 15, 15, 0, tzinfo=IST)
        minutes = market_hours.get_trading_minutes_remaining(dt)
        assert minutes == 30
    
    def test_add_holiday(self, market_hours):
        """Test adding a custom holiday."""
        custom_holiday = datetime(2024, 7, 4)  # Random date
        market_hours.add_holiday(custom_holiday)
        assert market_hours.is_trading_day(custom_holiday) is False
    
    def test_remove_holiday(self, market_hours):
        """Test removing a holiday."""
        # Remove Republic Day
        republic_day = datetime(2024, 1, 26)
        market_hours.remove_holiday(republic_day)
        # Since it's a Friday in 2024, should now be trading day
        assert market_hours.is_trading_day(republic_day) is True


class TestMarketHoursModuleFunctions:
    """Tests for module-level market hours functions."""
    
    def test_is_market_open_function(self):
        """Test is_market_open module function."""
        # Function should exist and be callable
        assert callable(is_market_open)
        result = is_market_open()
        assert isinstance(result, bool)
    
    def test_get_next_market_open_function(self):
        """Test get_next_market_open module function."""
        assert callable(get_next_market_open)
        result = get_next_market_open()
        assert isinstance(result, datetime)
    
    def test_is_trading_day_function(self):
        """Test is_trading_day module function."""
        assert callable(is_trading_day)
        result = is_trading_day()
        assert isinstance(result, bool)
    
    def test_get_market_state_function(self):
        """Test get_market_state module function."""
        assert callable(get_market_state)
        result = get_market_state()
        assert result in ['pre_market', 'open', 'post_market', 'closed']


class TestTradingScheduler:
    """Tests for TradingScheduler class."""
    
    @pytest.fixture
    def mock_broker(self):
        """Create mock broker."""
        broker = Mock()
        broker.login.return_value = True
        broker.get_margin.return_value = {
            'available_margin': 1_000_000,
            'used_margin': 0,
        }
        broker.get_positions.return_value = []
        broker.place_order.return_value = 'ORDER_123'
        return broker
    
    @pytest.fixture
    def scheduler(self, mock_broker):
        """Create TradingScheduler instance."""
        config = {
            'strategy_interval_seconds': 60,
            'position_check_interval_seconds': 30,
            'max_daily_loss_pct': 0.05,
            'timezone': 'Asia/Kolkata',
        }
        return TradingScheduler(broker=mock_broker, mode='paper', config=config)
    
    def test_initialization(self, scheduler):
        """Test TradingScheduler initializes correctly."""
        assert scheduler is not None
        assert scheduler.mode == 'paper'
        assert not scheduler.is_running
        assert not scheduler.is_paused
        assert not scheduler.kill_switch_active
    
    def test_start_stop(self, scheduler):
        """Test starting and stopping scheduler."""
        assert scheduler.start()
        assert scheduler.is_running
        
        assert scheduler.stop()
        assert not scheduler.is_running
    
    def test_pause_resume(self, scheduler):
        """Test pausing and resuming scheduler."""
        scheduler.start()
        
        scheduler.pause()
        assert scheduler.is_paused
        
        scheduler.resume()
        assert not scheduler.is_paused
        
        scheduler.stop()
    
    def test_kill_switch(self, scheduler):
        """Test kill switch functionality."""
        scheduler.start()
        
        scheduler.activate_kill_switch()
        assert scheduler.kill_switch_active
        assert scheduler.is_paused
        
        scheduler.deactivate_kill_switch()
        assert not scheduler.kill_switch_active
        
        scheduler.stop()
    
    def test_add_task(self, scheduler):
        """Test adding a scheduled task."""
        scheduler.start()
        
        callback = Mock()
        result = scheduler.add_task(
            name='test_task',
            callback=callback,
            interval_seconds=10,
            during_market_hours_only=False,
        )
        
        assert result is True
        
        status = scheduler.get_task_status('test_task')
        assert status is not None
        assert status['name'] == 'test_task'
        
        scheduler.stop()
    
    def test_remove_task(self, scheduler):
        """Test removing a scheduled task."""
        scheduler.start()
        
        callback = Mock()
        scheduler.add_task(
            name='test_task',
            callback=callback,
            interval_seconds=10,
            during_market_hours_only=False,
        )
        
        result = scheduler.remove_task('test_task')
        assert result is True
        
        status = scheduler.get_task_status('test_task')
        assert status is None
        
        scheduler.stop()
    
    def test_add_strategy_task(self, scheduler):
        """Test adding a strategy task."""
        scheduler.start()
        
        strategy_callback = Mock(return_value=None)
        result = scheduler.add_strategy_task(
            strategy_callback=strategy_callback,
            interval_seconds=60,
            name='test_strategy',
        )
        
        assert result is True
        
        status = scheduler.get_task_status('test_strategy')
        assert status is not None
        
        scheduler.stop()
    
    def test_add_pre_market_task(self, scheduler):
        """Test adding a pre-market task."""
        scheduler.start()
        
        callback = Mock()
        result = scheduler.add_pre_market_task(
            callback=callback,
            time_str='09:00',
            name='test_pre_market',
        )
        
        assert result is True
        
        scheduler.stop()
    
    def test_add_post_market_task(self, scheduler):
        """Test adding a post-market task."""
        scheduler.start()
        
        callback = Mock()
        result = scheduler.add_post_market_task(
            callback=callback,
            time_str='15:45',
            name='test_post_market',
        )
        
        assert result is True
        
        scheduler.stop()
    
    def test_add_position_monitor(self, scheduler):
        """Test adding position monitor task."""
        scheduler.start()
        
        result = scheduler.add_position_monitor(interval_seconds=30)
        assert result is True
        
        status = scheduler.get_task_status('position_monitor')
        assert status is not None
        
        scheduler.stop()
    
    def test_get_status(self, scheduler):
        """Test getting scheduler status."""
        scheduler.start()
        
        status = scheduler.get_status()
        
        assert 'is_running' in status
        assert 'is_paused' in status
        assert 'mode' in status
        assert 'market_state' in status
        assert status['is_running'] is True
        assert status['mode'] == 'paper'
        
        scheduler.stop()
    
    def test_get_all_task_status(self, scheduler):
        """Test getting all task statuses."""
        scheduler.start()
        
        callback = Mock()
        scheduler.add_task('task1', callback, interval_seconds=10, during_market_hours_only=False)
        scheduler.add_task('task2', callback, interval_seconds=20, during_market_hours_only=False)
        
        all_status = scheduler.get_all_task_status()
        
        assert len(all_status) == 2
        
        scheduler.stop()
    
    def test_live_mode_requires_confirmation(self):
        """Test that live mode requires explicit confirmation."""
        scheduler = TradingScheduler(
            broker=Mock(),
            mode='live',
            config={'live_trading_confirmed': False},
        )
        
        result = scheduler.start()
        assert result is False


class TestDataPipeline:
    """Tests for DataPipeline class."""
    
    @pytest.fixture
    def data_dir(self, tmp_path):
        """Create temporary data directory."""
        return str(tmp_path / 'market_data')
    
    @pytest.fixture
    def pipeline(self, data_dir):
        """Create DataPipeline instance."""
        config = {
            'realtime_interval_seconds': 5,
            'timezone': 'Asia/Kolkata',
            'max_retries': 3,
        }
        return DataPipeline(
            data_directory=data_dir,
            symbols=['NIFTY', 'BANKNIFTY'],
            intervals=['1m', '5m'],
            config=config,
        )
    
    def test_initialization(self, pipeline):
        """Test DataPipeline initializes correctly."""
        assert pipeline is not None
        assert not pipeline.is_running
        assert 'NIFTY' in pipeline.symbols
        assert 'BANKNIFTY' in pipeline.symbols
        assert '1m' in pipeline.intervals
        assert '5m' in pipeline.intervals
    
    def test_start_stop(self, pipeline):
        """Test starting and stopping pipeline."""
        assert pipeline.start()
        assert pipeline.is_running
        
        assert pipeline.stop()
        assert not pipeline.is_running
    
    def test_add_symbol(self, pipeline):
        """Test adding a symbol."""
        result = pipeline.add_symbol('SENSEX')
        assert result is True
        assert 'SENSEX' in pipeline.symbols
    
    def test_add_duplicate_symbol(self, pipeline):
        """Test adding a duplicate symbol."""
        result = pipeline.add_symbol('NIFTY')
        assert result is False
    
    def test_remove_symbol(self, pipeline):
        """Test removing a symbol."""
        result = pipeline.remove_symbol('NIFTY')
        assert result is True
        assert 'NIFTY' not in pipeline.symbols
    
    def test_remove_nonexistent_symbol(self, pipeline):
        """Test removing a nonexistent symbol."""
        result = pipeline.remove_symbol('NOTEXIST')
        assert result is False
    
    def test_invalid_interval(self, data_dir):
        """Test invalid interval raises error."""
        with pytest.raises(ValueError):
            DataPipeline(
                data_directory=data_dir,
                intervals=['invalid'],
            )
    
    def test_get_status(self, pipeline):
        """Test getting pipeline status."""
        pipeline.start()
        
        status = pipeline.get_status()
        
        assert 'is_running' in status
        assert 'symbols' in status
        assert 'intervals' in status
        assert 'total_ticks' in status
        assert status['is_running'] is True
        
        pipeline.stop()
    
    def test_get_job_status(self, pipeline):
        """Test getting job status."""
        pipeline.start()
        
        status = pipeline.get_job_status('realtime_fetch')
        
        assert status is not None
        assert status['name'] == 'realtime_fetch'
        
        pipeline.stop()
    
    def test_data_directory_creation(self, pipeline, data_dir):
        """Test data directory is created."""
        assert Path(data_dir).exists()
        assert (Path(data_dir) / 'ticks').exists()
        assert (Path(data_dir) / 'candles').exists()
        assert (Path(data_dir) / 'eod').exists()
    
    def test_validate_data_valid(self, pipeline):
        """Test data validation with valid data."""
        import pandas as pd
        
        df = pd.DataFrame({
            'timestamp': [datetime.now()],
            'open': [100.0],
            'high': [105.0],
            'low': [95.0],
            'close': [102.0],
        })
        
        assert pipeline.validate_data(df) is True
    
    def test_validate_data_invalid(self, pipeline):
        """Test data validation with invalid data."""
        import pandas as pd
        
        # High is less than low
        df = pd.DataFrame({
            'timestamp': [datetime.now()],
            'open': [100.0],
            'high': [90.0],
            'low': [95.0],
            'close': [102.0],
        })
        
        assert pipeline.validate_data(df) is False
    
    def test_validate_data_empty(self, pipeline):
        """Test data validation with empty data."""
        import pandas as pd
        
        df = pd.DataFrame()
        assert pipeline.validate_data(df) is False


class TestAutomationEngine:
    """Tests for AutomationEngine class."""
    
    @pytest.fixture
    def config(self, tmp_path):
        """Create test configuration."""
        return {
            'trading': {
                'enabled': True,
                'mode': 'paper',
                'strategy_interval_seconds': 60,
                'position_check_interval_seconds': 30,
                'timezone': 'Asia/Kolkata',
            },
            'data': {
                'enabled': True,
                'data_directory': str(tmp_path / 'market_data'),
                'symbols': ['NIFTY'],
                'intervals': ['1m'],
            },
            'notifications': {
                'enabled': False,
            },
        }
    
    @pytest.fixture
    def engine(self, config):
        """Create AutomationEngine instance."""
        return AutomationEngine(mode='paper', config=config)
    
    def test_initialization(self, engine):
        """Test AutomationEngine initializes correctly."""
        assert engine is not None
        assert engine.mode == 'paper'
        assert engine.state == 'stopped'
        assert not engine.is_running
    
    def test_start_stop(self, engine):
        """Test starting and stopping engine."""
        assert engine.start()
        assert engine.is_running
        assert engine.state == 'running'
        
        assert engine.stop()
        assert not engine.is_running
        assert engine.state == 'stopped'
    
    def test_pause_resume(self, engine):
        """Test pausing and resuming engine."""
        engine.start()
        
        assert engine.pause()
        assert engine.is_paused
        assert engine.state == 'paused'
        
        assert engine.resume()
        assert not engine.is_paused
        assert engine.state == 'running'
        
        engine.stop()
    
    def test_kill_switch(self, engine):
        """Test kill switch functionality."""
        engine.start()
        
        engine.activate_kill_switch()
        # Kill switch should pause the trading scheduler
        
        engine.deactivate_kill_switch()
        
        engine.stop()
    
    def test_add_strategy(self, engine):
        """Test adding a strategy."""
        engine.start()
        
        mock_strategy = Mock()
        mock_strategy.generate_signal = Mock(return_value=None)
        mock_strategy.name = 'test_strategy'
        
        result = engine.add_strategy(mock_strategy)
        assert result is True
        
        engine.stop()
    
    def test_add_strategy_callable(self, engine):
        """Test adding a callable as strategy."""
        engine.start()
        
        callback = Mock(return_value=None)
        result = engine.add_strategy(callback, name='callable_strategy')
        assert result is True
        
        engine.stop()
    
    def test_add_symbol(self, engine):
        """Test adding a symbol."""
        engine.start()
        
        result = engine.add_symbol('BANKNIFTY')
        assert result is True
        
        engine.stop()
    
    def test_health_check(self, engine):
        """Test health check."""
        engine.start()
        
        health = engine.health_check()
        
        assert 'healthy' in health
        assert 'checks' in health
        assert 'timestamp' in health
        
        engine.stop()
    
    def test_get_status(self, engine):
        """Test getting engine status."""
        engine.start()
        
        status = engine.get_status()
        
        assert 'mode' in status
        assert 'state' in status
        assert 'market_state' in status
        assert status['mode'] == 'paper'
        assert status['state'] == 'running'
        
        engine.stop()
    
    def test_register_notification_handler(self, engine):
        """Test registering notification handler."""
        handler = Mock()
        engine.register_notification_handler(handler)
        
        # Enable notifications
        engine._notifications_enabled = True
        
        engine.start()
        # Handler should be called for engine_started event
        
        engine.stop()
    
    def test_live_mode_requires_confirmation(self, config):
        """Test that live mode requires confirmation."""
        config['trading']['mode'] = 'live'
        config['trading']['live_trading_confirmed'] = False
        
        engine = AutomationEngine(mode='live', config=config)
        result = engine.start()
        
        assert result is False
        assert engine.state == 'error'
    
    def test_modes(self, config):
        """Test different engine modes."""
        for mode in ['paper', 'backtest']:
            engine = AutomationEngine(mode=mode, config=config)
            assert engine.mode == mode


class TestAutomationConfig:
    """Tests for automation configuration."""
    
    def test_automation_config_structure(self):
        """Test AUTOMATION_CONFIG has expected structure."""
        assert 'trading' in AUTOMATION_CONFIG
        assert 'data' in AUTOMATION_CONFIG
        assert 'notifications' in AUTOMATION_CONFIG
        assert 'safety' in AUTOMATION_CONFIG
    
    def test_get_automation_config(self):
        """Test get_automation_config function."""
        config = get_automation_config()
        assert 'trading' in config
        assert 'data' in config
    
    def test_get_trading_config(self):
        """Test get_trading_config function."""
        config = get_trading_config()
        assert 'enabled' in config
        assert 'mode' in config
        assert 'strategy_interval_seconds' in config
    
    def test_get_data_config(self):
        """Test get_data_config function."""
        config = get_data_config()
        assert 'enabled' in config
        assert 'symbols' in config
        assert 'intervals' in config
    
    def test_validate_automation_config_valid(self):
        """Test config validation with valid config."""
        config = get_automation_config()
        assert validate_automation_config(config) is True
    
    def test_validate_automation_config_invalid_mode(self):
        """Test config validation with invalid mode."""
        config = get_automation_config()
        config['trading']['mode'] = 'invalid'
        
        with pytest.raises(ValueError):
            validate_automation_config(config)
    
    def test_validate_automation_config_invalid_interval(self):
        """Test config validation with invalid interval."""
        config = get_automation_config()
        config['data']['intervals'] = ['invalid']
        
        with pytest.raises(ValueError):
            validate_automation_config(config)
    
    def test_validate_automation_config_live_unconfirmed(self):
        """Test config validation for unconfirmed live trading."""
        config = get_automation_config()
        config['trading']['mode'] = 'live'
        config['trading']['live_trading_confirmed'] = False
        
        with pytest.raises(ValueError):
            validate_automation_config(config)
    
    def test_create_paper_trading_config(self):
        """Test create_paper_trading_config function."""
        config = create_paper_trading_config()
        assert config['trading']['mode'] == 'paper'
        assert config['trading']['live_trading_confirmed'] is False
    
    def test_create_live_trading_config(self):
        """Test create_live_trading_config function."""
        config = create_live_trading_config(confirmed=True)
        assert config['trading']['mode'] == 'live'
        assert config['trading']['live_trading_confirmed'] is True


class TestScheduledTask:
    """Tests for ScheduledTask dataclass."""
    
    def test_scheduled_task_creation(self):
        """Test ScheduledTask creation."""
        callback = Mock()
        task = ScheduledTask(
            name='test_task',
            callback=callback,
            interval_seconds=60,
            during_market_hours_only=True,
        )
        
        assert task.name == 'test_task'
        assert task.callback == callback
        assert task.interval_seconds == 60
        assert task.during_market_hours_only is True
        assert task.enabled is True
        assert task.run_count == 0
        assert task.error_count == 0


class TestDataFetchJob:
    """Tests for DataFetchJob dataclass."""
    
    def test_data_fetch_job_creation(self):
        """Test DataFetchJob creation."""
        job = DataFetchJob(
            name='test_job',
            symbols=['NIFTY'],
            interval='1m',
        )
        
        assert job.name == 'test_job'
        assert job.symbols == ['NIFTY']
        assert job.interval == '1m'
        assert job.fetch_count == 0
        assert job.error_count == 0


class TestEngineEnums:
    """Tests for engine enums."""
    
    def test_engine_mode_values(self):
        """Test EngineMode enum values."""
        assert EngineMode.LIVE.value == 'live'
        assert EngineMode.PAPER.value == 'paper'
        assert EngineMode.BACKTEST.value == 'backtest'
    
    def test_engine_state_values(self):
        """Test EngineState enum values."""
        assert EngineState.STOPPED.value == 'stopped'
        assert EngineState.STARTING.value == 'starting'
        assert EngineState.RUNNING.value == 'running'
        assert EngineState.PAUSED.value == 'paused'
        assert EngineState.STOPPING.value == 'stopping'
        assert EngineState.ERROR.value == 'error'


class TestIntegration:
    """Integration tests for automation components."""
    
    @pytest.fixture
    def full_config(self, tmp_path):
        """Create full test configuration."""
        return {
            'trading': {
                'enabled': True,
                'mode': 'paper',
                'strategy_interval_seconds': 10,
                'position_check_interval_seconds': 10,
                'timezone': 'Asia/Kolkata',
            },
            'data': {
                'enabled': True,
                'data_directory': str(tmp_path / 'market_data'),
                'symbols': ['NIFTY'],
                'intervals': ['1m'],
                'realtime_interval_seconds': 5,
            },
            'notifications': {
                'enabled': False,
            },
        }
    
    def test_engine_with_scheduler_and_pipeline(self, full_config):
        """Test engine coordinates scheduler and pipeline."""
        engine = AutomationEngine(mode='paper', config=full_config)
        
        assert engine.start()
        assert engine.is_running
        
        # Check components are running
        status = engine.get_status()
        assert status['trading_scheduler']['is_running'] is True
        assert status['data_pipeline']['is_running'] is True
        
        engine.stop()
        
        # Check components are stopped
        assert not engine.is_running
    
    def test_engine_lifecycle(self, full_config):
        """Test full engine lifecycle."""
        engine = AutomationEngine(mode='paper', config=full_config)
        
        # Start
        engine.start()
        assert engine.state == 'running'
        
        # Pause
        engine.pause()
        assert engine.state == 'paused'
        
        # Resume
        engine.resume()
        assert engine.state == 'running'
        
        # Kill switch
        engine.activate_kill_switch()
        
        # Deactivate kill switch
        engine.deactivate_kill_switch()
        
        # Stop
        engine.stop()
        assert engine.state == 'stopped'
    
    def test_thread_safety(self, full_config):
        """Test thread safety of engine operations."""
        engine = AutomationEngine(mode='paper', config=full_config)
        errors = []
        
        def status_checker():
            try:
                for _ in range(10):
                    engine.get_status()
                    engine.health_check()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)
        
        engine.start()
        
        threads = [threading.Thread(target=status_checker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        
        engine.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
