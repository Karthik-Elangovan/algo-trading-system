"""
Automation Engine Module.

Central automation engine that coordinates:
- Trading scheduler
- Data pipelines
- Lifecycle management (start, stop, pause, resume)
- Status and health checks
- Error handling with notifications
"""

import logging
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .data_pipeline import DataPipeline
from .market_hours import MarketHours
from .trading_scheduler import TradingScheduler

logger = logging.getLogger(__name__)


class EngineMode(Enum):
    """Engine operation modes."""
    LIVE = "live"
    PAPER = "paper"
    BACKTEST = "backtest"


class EngineState(Enum):
    """Engine states."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class HealthStatus:
    """Health check status."""
    component: str
    healthy: bool
    message: str = ""
    last_check: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)


class AutomationEngine:
    """
    Central automation engine for coordinating all automated trading activities.
    
    Features:
    - Coordinates trading scheduler and data pipelines
    - Manages lifecycle (start, stop, pause, resume)
    - Provides status and health checks
    - Handles errors gracefully with notifications
    - Supports different modes: live, paper, backtest
    
    Example:
        >>> from src.automation import AutomationEngine
        >>> from config.automation_config import AUTOMATION_CONFIG
        >>> 
        >>> engine = AutomationEngine(config=AUTOMATION_CONFIG)
        >>> engine.start()
        >>> 
        >>> # Add a strategy
        >>> engine.add_strategy(my_strategy)
        >>> 
        >>> # Check status
        >>> print(engine.get_status())
        >>> 
        >>> # Stop engine
        >>> engine.stop()
    """
    
    def __init__(
        self,
        mode: str = "paper",
        config: Optional[Dict[str, Any]] = None,
        broker: Optional[Any] = None,
        data_provider: Optional[Any] = None,
    ):
        """
        Initialize the AutomationEngine.
        
        Args:
            mode: Operation mode ('live', 'paper', or 'backtest')
            config: Configuration dictionary
            broker: Broker instance for order execution
            data_provider: Data provider instance for market data
        """
        self._mode = EngineMode(mode.lower())
        self._config = config or {}
        self._broker = broker
        self._data_provider = data_provider
        
        # State
        self._state = EngineState.STOPPED
        self._state_lock = threading.Lock()
        
        # Configuration
        trading_config = self._config.get('trading', {})
        data_config = self._config.get('data', {})
        notification_config = self._config.get('notifications', {})
        
        # Market hours
        timezone = trading_config.get('timezone', 'Asia/Kolkata')
        self._market_hours = MarketHours(timezone=timezone)
        
        # Initialize components
        self._trading_scheduler: Optional[TradingScheduler] = None
        self._data_pipeline: Optional[DataPipeline] = None
        
        if trading_config.get('enabled', True):
            self._trading_scheduler = TradingScheduler(
                broker=broker,
                mode=mode,
                config=trading_config,
            )
        
        if data_config.get('enabled', True):
            self._data_pipeline = DataPipeline(
                data_directory=data_config.get('data_directory', 'data/market_data'),
                symbols=data_config.get('symbols', ['NIFTY', 'BANKNIFTY']),
                intervals=data_config.get('intervals', ['1m', '5m', '15m', '1h', '1d']),
                data_provider=data_provider,
                config=data_config,
            )
        
        # Notification handlers
        self._notification_handlers: List[Callable] = []
        self._notifications_enabled = notification_config.get('enabled', False)
        
        # Statistics
        self._start_time: Optional[datetime] = None
        self._error_count = 0
        self._last_error: Optional[str] = None
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        logger.info(f"Initialized AutomationEngine in {self._mode.value} mode")
    
    @property
    def mode(self) -> str:
        """Get engine mode."""
        return self._mode.value
    
    @property
    def state(self) -> str:
        """Get engine state."""
        with self._state_lock:
            return self._state.value
    
    @property
    def is_running(self) -> bool:
        """Check if engine is running."""
        with self._state_lock:
            return self._state == EngineState.RUNNING
    
    @property
    def is_paused(self) -> bool:
        """Check if engine is paused."""
        with self._state_lock:
            return self._state == EngineState.PAUSED
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        # Use a flag to request shutdown rather than calling sys.exit directly
        self._shutdown_requested = False
        
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, requesting shutdown...")
            self._shutdown_requested = True
            # Initiate graceful shutdown in a separate thread to avoid
            # blocking the signal handler
            shutdown_thread = threading.Thread(target=self._graceful_shutdown, daemon=True)
            shutdown_thread.start()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _graceful_shutdown(self) -> None:
        """Perform graceful shutdown of all components."""
        logger.info("Performing graceful shutdown...")
        self.stop()
        logger.info("Graceful shutdown complete")
    
    def _set_state(self, state: EngineState) -> None:
        """Set engine state with thread safety."""
        with self._state_lock:
            old_state = self._state
            self._state = state
            logger.info(f"Engine state changed: {old_state.value} -> {state.value}")
    
    def start(self) -> bool:
        """
        Start the automation engine.
        
        Returns:
            True if started successfully
        """
        with self._state_lock:
            if self._state == EngineState.RUNNING:
                logger.warning("Engine already running")
                return True
            
            if self._state not in [EngineState.STOPPED, EngineState.ERROR]:
                logger.warning(f"Cannot start engine in state: {self._state.value}")
                return False
        
        self._set_state(EngineState.STARTING)
        
        try:
            # Safety check for live mode
            if self._mode == EngineMode.LIVE:
                trading_config = self._config.get('trading', {})
                if not trading_config.get('live_trading_confirmed', False):
                    logger.error("Live trading requires explicit confirmation")
                    self._set_state(EngineState.ERROR)
                    return False
            
            logger.info("Starting AutomationEngine")
            self._start_time = datetime.now()
            
            # Start data pipeline first
            if self._data_pipeline:
                if not self._data_pipeline.start():
                    raise RuntimeError("Failed to start data pipeline")
                logger.info("Data pipeline started")
            
            # Start trading scheduler
            if self._trading_scheduler:
                if not self._trading_scheduler.start():
                    raise RuntimeError("Failed to start trading scheduler")
                logger.info("Trading scheduler started")
            
            self._set_state(EngineState.RUNNING)
            logger.info("AutomationEngine started successfully")
            
            self._notify('engine_started', {
                'mode': self._mode.value,
                'start_time': self._start_time.isoformat(),
            })
            
            return True
            
        except Exception as e:
            logger.exception(f"Failed to start engine: {e}")
            self._error_count += 1
            self._last_error = str(e)
            self._set_state(EngineState.ERROR)
            
            self._notify('engine_error', {
                'error': str(e),
                'component': 'startup',
            })
            
            return False
    
    def stop(self) -> bool:
        """
        Stop the automation engine.
        
        Returns:
            True if stopped successfully
        """
        with self._state_lock:
            if self._state == EngineState.STOPPED:
                return True
            
            if self._state == EngineState.STOPPING:
                logger.warning("Engine already stopping")
                return True
        
        self._set_state(EngineState.STOPPING)
        
        try:
            logger.info("Stopping AutomationEngine")
            
            # Stop trading scheduler first
            if self._trading_scheduler:
                self._trading_scheduler.stop()
                logger.info("Trading scheduler stopped")
            
            # Stop data pipeline
            if self._data_pipeline:
                self._data_pipeline.stop()
                logger.info("Data pipeline stopped")
            
            self._set_state(EngineState.STOPPED)
            logger.info("AutomationEngine stopped successfully")
            
            self._notify('engine_stopped', {
                'stop_time': datetime.now().isoformat(),
                'uptime_seconds': (datetime.now() - self._start_time).total_seconds() if self._start_time else 0,
            })
            
            return True
            
        except Exception as e:
            logger.exception(f"Error stopping engine: {e}")
            self._set_state(EngineState.ERROR)
            return False
    
    def pause(self) -> bool:
        """
        Pause the automation engine.
        
        Returns:
            True if paused successfully
        """
        with self._state_lock:
            if self._state != EngineState.RUNNING:
                logger.warning(f"Cannot pause engine in state: {self._state.value}")
                return False
        
        logger.info("Pausing AutomationEngine")
        
        if self._trading_scheduler:
            self._trading_scheduler.pause()
        
        self._set_state(EngineState.PAUSED)
        
        self._notify('engine_paused', {
            'pause_time': datetime.now().isoformat(),
        })
        
        return True
    
    def resume(self) -> bool:
        """
        Resume the automation engine.
        
        Returns:
            True if resumed successfully
        """
        with self._state_lock:
            if self._state != EngineState.PAUSED:
                logger.warning(f"Cannot resume engine in state: {self._state.value}")
                return False
        
        logger.info("Resuming AutomationEngine")
        
        if self._trading_scheduler:
            self._trading_scheduler.resume()
        
        self._set_state(EngineState.RUNNING)
        
        self._notify('engine_resumed', {
            'resume_time': datetime.now().isoformat(),
        })
        
        return True
    
    def activate_kill_switch(self) -> None:
        """Activate emergency kill switch to stop all trading."""
        logger.critical("KILL SWITCH ACTIVATED")
        
        if self._trading_scheduler:
            self._trading_scheduler.activate_kill_switch()
        
        self._notify('kill_switch_activated', {
            'time': datetime.now().isoformat(),
        })
    
    def deactivate_kill_switch(self) -> None:
        """Deactivate kill switch."""
        logger.info("Kill switch deactivated")
        
        if self._trading_scheduler:
            self._trading_scheduler.deactivate_kill_switch()
        
        self._notify('kill_switch_deactivated', {
            'time': datetime.now().isoformat(),
        })
    
    def add_strategy(
        self,
        strategy: Any,
        interval_seconds: Optional[int] = None,
        name: Optional[str] = None,
    ) -> bool:
        """
        Add a strategy to the trading scheduler.
        
        Args:
            strategy: Strategy instance with generate_signal method
            interval_seconds: Execution interval
            name: Strategy name
            
        Returns:
            True if added successfully
        """
        if not self._trading_scheduler:
            logger.warning("Trading scheduler not configured")
            return False
        
        # Get the generate_signal method
        if hasattr(strategy, 'generate_signal'):
            callback = strategy.generate_signal
        elif callable(strategy):
            callback = strategy
        else:
            logger.error("Strategy must have generate_signal method or be callable")
            return False
        
        task_name = name or getattr(strategy, 'name', f'strategy_{id(strategy)}')
        
        return self._trading_scheduler.add_strategy_task(
            strategy_callback=callback,
            interval_seconds=interval_seconds,
            name=task_name,
        )
    
    def add_pre_market_task(
        self,
        callback: Callable,
        time_str: str = "09:00",
        name: str = "pre_market",
    ) -> bool:
        """Add a pre-market task."""
        if not self._trading_scheduler:
            logger.warning("Trading scheduler not configured")
            return False
        
        return self._trading_scheduler.add_pre_market_task(callback, time_str, name)
    
    def add_post_market_task(
        self,
        callback: Callable,
        time_str: str = "15:45",
        name: str = "post_market",
    ) -> bool:
        """Add a post-market task."""
        if not self._trading_scheduler:
            logger.warning("Trading scheduler not configured")
            return False
        
        return self._trading_scheduler.add_post_market_task(callback, time_str, name)
    
    def add_symbol(self, symbol: str) -> bool:
        """Add a symbol to track in data pipeline."""
        if not self._data_pipeline:
            logger.warning("Data pipeline not configured")
            return False
        
        return self._data_pipeline.add_symbol(symbol)
    
    def remove_symbol(self, symbol: str) -> bool:
        """Remove a symbol from data pipeline."""
        if not self._data_pipeline:
            logger.warning("Data pipeline not configured")
            return False
        
        return self._data_pipeline.remove_symbol(symbol)
    
    def register_notification_handler(self, handler: Callable) -> None:
        """
        Register a notification handler.
        
        Args:
            handler: Callable that takes (event_type, data) arguments
        """
        self._notification_handlers.append(handler)
        handler_name = getattr(handler, '__name__', str(handler))
        logger.info(f"Registered notification handler: {handler_name}")
    
    def _notify(self, event_type: str, data: Dict[str, Any]) -> None:
        """Send notification for an event."""
        if not self._notifications_enabled:
            return
        
        for handler in self._notification_handlers:
            try:
                handler(event_type, data)
            except Exception as e:
                logger.error(f"Notification handler failed: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all components.
        
        Returns:
            Dictionary with health check results
        """
        checks: List[HealthStatus] = []
        
        # Check engine state
        checks.append(HealthStatus(
            component='engine',
            healthy=self._state in [EngineState.RUNNING, EngineState.PAUSED],
            message=f'State: {self._state.value}',
        ))
        
        # Check trading scheduler
        if self._trading_scheduler:
            scheduler_status = self._trading_scheduler.get_status()
            checks.append(HealthStatus(
                component='trading_scheduler',
                healthy=scheduler_status.get('is_running', False) or scheduler_status.get('is_paused', False),
                message=f"Running: {scheduler_status.get('is_running')}, Tasks: {scheduler_status.get('task_count')}",
                details=scheduler_status,
            ))
        
        # Check data pipeline
        if self._data_pipeline:
            pipeline_status = self._data_pipeline.get_status()
            checks.append(HealthStatus(
                component='data_pipeline',
                healthy=pipeline_status.get('is_running', False),
                message=f"Running: {pipeline_status.get('is_running')}, Symbols: {len(pipeline_status.get('symbols', []))}",
                details=pipeline_status,
            ))
        
        # Check market hours
        market_state = self._market_hours.get_market_state()
        checks.append(HealthStatus(
            component='market_hours',
            healthy=True,
            message=f'Market state: {market_state}',
        ))
        
        # Overall health
        overall_healthy = all(check.healthy for check in checks)
        
        return {
            'healthy': overall_healthy,
            'mode': self._mode.value,
            'state': self._state.value,
            'checks': [
                {
                    'component': c.component,
                    'healthy': c.healthy,
                    'message': c.message,
                    'last_check': c.last_check.isoformat(),
                }
                for c in checks
            ],
            'timestamp': datetime.now().isoformat(),
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive engine status.
        
        Returns:
            Dictionary with status information
        """
        status = {
            'mode': self._mode.value,
            'state': self._state.value,
            'start_time': self._start_time.isoformat() if self._start_time else None,
            'uptime_seconds': (datetime.now() - self._start_time).total_seconds() if self._start_time else 0,
            'error_count': self._error_count,
            'last_error': self._last_error,
            'market_state': self._market_hours.get_market_state(),
        }
        
        # Add component status
        if self._trading_scheduler:
            status['trading_scheduler'] = self._trading_scheduler.get_status()
        
        if self._data_pipeline:
            status['data_pipeline'] = self._data_pipeline.get_status()
        
        return status
    
    def get_trading_status(self) -> Optional[Dict[str, Any]]:
        """Get trading scheduler status."""
        if not self._trading_scheduler:
            return None
        return self._trading_scheduler.get_status()
    
    def get_data_status(self) -> Optional[Dict[str, Any]]:
        """Get data pipeline status."""
        if not self._data_pipeline:
            return None
        return self._data_pipeline.get_status()
    
    def run_forever(self) -> None:
        """
        Run the engine forever until interrupted.
        
        This method blocks and runs the engine until a signal is received
        or shutdown is requested.
        """
        if not self.start():
            logger.error("Failed to start engine")
            return
        
        logger.info("Engine running. Press Ctrl+C to stop.")
        
        try:
            while (self.is_running or self.is_paused) and not self._shutdown_requested:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            if not self._shutdown_requested:
                self.stop()
