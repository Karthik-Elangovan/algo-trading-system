"""
Trading Scheduler Module.

Provides automated trading schedule management including:
- Strategy execution at configurable intervals
- Pre-market and post-market tasks
- Position monitoring with stop-loss/take-profit execution
- Support for paper and live trading modes
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .market_hours import MarketHours

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """Represents a scheduled task."""
    name: str
    callback: Callable
    interval_seconds: Optional[int] = None
    cron_expression: Optional[str] = None
    during_market_hours_only: bool = True
    enabled: bool = True
    last_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class TradingScheduler:
    """
    Trading scheduler for automated strategy execution.
    
    Features:
    - Schedule strategy execution at configurable intervals
    - Pre-market setup and post-market cleanup tasks
    - Position monitoring with automated stop-loss/take-profit
    - Support for paper and live trading modes
    - Thread-safe execution with graceful shutdown
    
    Example:
        >>> from src.automation import TradingScheduler
        >>> from src.execution.broker import BrokerFactory
        >>> 
        >>> broker = BrokerFactory.create('paper')
        >>> scheduler = TradingScheduler(broker=broker, mode='paper')
        >>> 
        >>> scheduler.add_strategy_task(my_strategy.generate_signal, interval_seconds=60)
        >>> scheduler.start()
    """
    
    def __init__(
        self,
        broker: Optional[Any] = None,
        mode: str = "paper",
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the TradingScheduler.
        
        Args:
            broker: Broker instance for order execution (optional)
            mode: Trading mode ('paper' or 'live')
            config: Configuration dictionary with:
                - strategy_interval_seconds: Strategy execution interval (default: 60)
                - position_check_interval_seconds: Position check interval (default: 30)
                - max_daily_loss_pct: Maximum daily loss percentage (default: 0.05)
                - timezone: Market timezone (default: Asia/Kolkata)
        """
        self._broker = broker
        self._mode = mode.lower()
        self._config = config or {}
        
        # Configuration
        self._strategy_interval = self._config.get('strategy_interval_seconds', 60)
        self._position_interval = self._config.get('position_check_interval_seconds', 30)
        self._max_daily_loss_pct = self._config.get('max_daily_loss_pct', 0.05)
        self._timezone = self._config.get('timezone', 'Asia/Kolkata')
        
        # Market hours
        self._market_hours = MarketHours(timezone=self._timezone)
        
        # Scheduler
        self._scheduler = BackgroundScheduler(
            timezone=self._timezone,
            job_defaults={
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 30,
            }
        )
        
        # State
        self._is_running = False
        self._is_paused = False
        self._kill_switch_active = False
        self._tasks: Dict[str, ScheduledTask] = {}
        self._strategies: List[Callable] = []
        self._lock = threading.Lock()
        
        # Statistics
        self._start_time: Optional[datetime] = None
        self._total_signals = 0
        self._total_orders = 0
        self._daily_pnl = 0.0
        self._initial_capital: Optional[float] = None
        
        logger.info(f"Initialized TradingScheduler in {self._mode} mode")
    
    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._is_running
    
    @property
    def is_paused(self) -> bool:
        """Check if scheduler is paused."""
        return self._is_paused
    
    @property
    def mode(self) -> str:
        """Get trading mode."""
        return self._mode
    
    @property
    def kill_switch_active(self) -> bool:
        """Check if kill switch is active."""
        return self._kill_switch_active
    
    def start(self) -> bool:
        """
        Start the trading scheduler.
        
        Returns:
            True if started successfully
        """
        if self._is_running:
            logger.warning("Scheduler already running")
            return True
        
        # Safety check for live mode
        if self._mode == "live" and not self._config.get('live_trading_confirmed', False):
            logger.error("Live trading requires explicit confirmation. Set 'live_trading_confirmed': True in config")
            return False
        
        logger.info("Starting TradingScheduler")
        
        # Record start time and initial capital
        self._start_time = datetime.now()
        if self._broker:
            try:
                margin = self._broker.get_margin()
                self._initial_capital = margin.get('available_margin', 0) + margin.get('used_margin', 0)
            except Exception as e:
                logger.warning(f"Could not get initial capital: {e}")
        
        # Start the APScheduler
        self._scheduler.start()
        self._is_running = True
        self._is_paused = False
        self._kill_switch_active = False
        
        logger.info("TradingScheduler started")
        return True
    
    def stop(self) -> bool:
        """
        Stop the trading scheduler.
        
        Returns:
            True if stopped successfully
        """
        if not self._is_running:
            return True
        
        logger.info("Stopping TradingScheduler")
        
        self._scheduler.shutdown(wait=True)
        self._is_running = False
        
        logger.info("TradingScheduler stopped")
        return True
    
    def pause(self) -> None:
        """Pause all scheduled tasks."""
        self._is_paused = True
        self._scheduler.pause()
        logger.info("TradingScheduler paused")
    
    def resume(self) -> None:
        """Resume all scheduled tasks."""
        self._is_paused = False
        self._scheduler.resume()
        logger.info("TradingScheduler resumed")
    
    def activate_kill_switch(self) -> None:
        """
        Activate kill switch to immediately stop all trading.
        
        This will:
        - Stop executing new orders
        - Pause all scheduled tasks
        - Log the emergency stop
        """
        logger.critical("KILL SWITCH ACTIVATED - All trading stopped")
        self._kill_switch_active = True
        self.pause()
    
    def deactivate_kill_switch(self) -> None:
        """Deactivate kill switch and resume trading."""
        logger.info("Kill switch deactivated")
        self._kill_switch_active = False
        self.resume()
    
    def add_task(
        self,
        name: str,
        callback: Callable,
        interval_seconds: Optional[int] = None,
        cron_expression: Optional[str] = None,
        during_market_hours_only: bool = True,
        **kwargs
    ) -> bool:
        """
        Add a scheduled task.
        
        Args:
            name: Task name
            callback: Function to execute
            interval_seconds: Interval in seconds (mutually exclusive with cron_expression)
            cron_expression: Cron expression for scheduling
            during_market_hours_only: Only run during market hours
            **kwargs: Additional arguments for the callback
            
        Returns:
            True if task was added successfully
        """
        if name in self._tasks:
            logger.warning(f"Task {name} already exists")
            return False
        
        task = ScheduledTask(
            name=name,
            callback=callback,
            interval_seconds=interval_seconds,
            cron_expression=cron_expression,
            during_market_hours_only=during_market_hours_only,
            metadata=kwargs,
        )
        
        # Create wrapper that respects market hours and kill switch
        def task_wrapper():
            if self._kill_switch_active:
                return
            
            if task.during_market_hours_only and not self._market_hours.is_market_open():
                return
            
            try:
                callback(**kwargs)
                task.last_run = datetime.now()
                task.run_count += 1
                logger.debug(f"Task {name} executed successfully")
            except Exception as e:
                task.error_count += 1
                logger.exception(f"Task {name} failed: {e}")
        
        # Add to scheduler
        if interval_seconds:
            trigger = IntervalTrigger(seconds=interval_seconds)
        elif cron_expression:
            trigger = CronTrigger.from_crontab(cron_expression)
        else:
            logger.error(f"Task {name} requires interval_seconds or cron_expression")
            return False
        
        job = self._scheduler.add_job(task_wrapper, trigger, id=name)
        
        self._tasks[name] = task
        logger.info(f"Added task: {name}")
        return True
    
    def remove_task(self, name: str) -> bool:
        """
        Remove a scheduled task.
        
        Args:
            name: Task name
            
        Returns:
            True if task was removed successfully
        """
        if name not in self._tasks:
            logger.warning(f"Task {name} not found")
            return False
        
        try:
            self._scheduler.remove_job(name)
        except Exception as e:
            logger.warning(f"Could not remove job {name}: {e}")
        
        del self._tasks[name]
        logger.info(f"Removed task: {name}")
        return True
    
    def add_strategy_task(
        self,
        strategy_callback: Callable,
        interval_seconds: Optional[int] = None,
        name: Optional[str] = None,
    ) -> bool:
        """
        Add a strategy execution task.
        
        Args:
            strategy_callback: Strategy's generate_signal method
            interval_seconds: Execution interval (default: from config)
            name: Task name (auto-generated if not provided)
            
        Returns:
            True if task was added successfully
        """
        task_name = name or f"strategy_{len(self._strategies)}"
        interval = interval_seconds or self._strategy_interval
        
        def strategy_wrapper():
            self._execute_strategy(strategy_callback)
        
        success = self.add_task(
            name=task_name,
            callback=strategy_wrapper,
            interval_seconds=interval,
            during_market_hours_only=True,
        )
        
        if success:
            self._strategies.append(strategy_callback)
        
        return success
    
    def add_position_monitor(
        self,
        interval_seconds: Optional[int] = None,
    ) -> bool:
        """
        Add position monitoring task.
        
        Monitors positions and executes stop-loss/take-profit orders.
        
        Args:
            interval_seconds: Check interval (default: from config)
            
        Returns:
            True if task was added successfully
        """
        interval = interval_seconds or self._position_interval
        
        return self.add_task(
            name="position_monitor",
            callback=self._check_positions,
            interval_seconds=interval,
            during_market_hours_only=True,
        )
    
    def add_pre_market_task(
        self,
        callback: Callable,
        time_str: str = "09:00",
        name: str = "pre_market",
    ) -> bool:
        """
        Add a pre-market task.
        
        Args:
            callback: Function to execute
            time_str: Time in HH:MM format (default: 09:00)
            name: Task name
            
        Returns:
            True if task was added successfully
        """
        hour, minute = map(int, time_str.split(":"))
        cron_expr = f"{minute} {hour} * * 1-5"  # Mon-Fri
        
        return self.add_task(
            name=name,
            callback=callback,
            cron_expression=cron_expr,
            during_market_hours_only=False,
        )
    
    def add_post_market_task(
        self,
        callback: Callable,
        time_str: str = "15:45",
        name: str = "post_market",
    ) -> bool:
        """
        Add a post-market task.
        
        Args:
            callback: Function to execute
            time_str: Time in HH:MM format (default: 15:45)
            name: Task name
            
        Returns:
            True if task was added successfully
        """
        hour, minute = map(int, time_str.split(":"))
        cron_expr = f"{minute} {hour} * * 1-5"  # Mon-Fri
        
        return self.add_task(
            name=name,
            callback=callback,
            cron_expression=cron_expr,
            during_market_hours_only=False,
        )
    
    def _execute_strategy(self, strategy_callback: Callable) -> None:
        """Execute a strategy and process any signals."""
        if self._kill_switch_active:
            return
        
        if not self._check_daily_loss_limit():
            logger.warning("Daily loss limit reached - skipping strategy execution")
            return
        
        try:
            # Generate signal
            signal = strategy_callback()
            
            if signal is None:
                return
            
            self._total_signals += 1
            logger.info(f"Strategy generated signal: {signal}")
            
            # Execute signal if auto-execution is enabled
            if self._config.get('auto_execute', True) and self._broker:
                self._execute_signal(signal)
            
        except Exception as e:
            logger.exception(f"Strategy execution failed: {e}")
    
    def _execute_signal(self, signal: Any) -> Optional[str]:
        """
        Execute a trading signal.
        
        Args:
            signal: Signal object with execution details
            
        Returns:
            Order ID if order was placed, None otherwise
        """
        if self._kill_switch_active:
            logger.warning("Kill switch active - signal not executed")
            return None
        
        if not self._broker:
            logger.warning("No broker configured - signal not executed")
            return None
        
        # Check rate limiting
        if not self._check_rate_limit():
            logger.warning("Rate limit reached - signal not executed")
            return None
        
        try:
            # Check if this is a dry run
            if self._config.get('dry_run', False):
                logger.info(f"DRY RUN - Would execute signal: {signal}")
                return "DRY_RUN"
            
            # Extract signal details
            # Signal object expected to have: signal_type, symbol, quantity, price, etc.
            signal_type = getattr(signal, 'signal_type', None)
            if signal_type is None:
                logger.warning("Invalid signal - missing signal_type")
                return None
            
            # Determine transaction type
            signal_type_value = signal_type.value if hasattr(signal_type, 'value') else str(signal_type)
            
            if 'ENTRY_LONG' in signal_type_value or 'BUY' in signal_type_value:
                transaction_type = "BUY"
            elif 'ENTRY_SHORT' in signal_type_value or 'EXIT_LONG' in signal_type_value or 'SELL' in signal_type_value:
                transaction_type = "SELL"
            else:
                logger.warning(f"Unknown signal type: {signal_type}")
                return None
            
            # Place order
            order_id = self._broker.place_order(
                symbol=signal.symbol,
                exchange=getattr(signal, 'exchange', 'NFO'),
                transaction_type=transaction_type,
                quantity=signal.quantity,
                order_type="MARKET",
                product_type=getattr(signal, 'product_type', 'INTRADAY'),
            )
            
            self._total_orders += 1
            logger.info(f"Order placed: {order_id} for signal {signal}")
            
            return order_id
            
        except Exception as e:
            logger.exception(f"Failed to execute signal: {e}")
            return None
    
    def _check_positions(self) -> None:
        """Check positions and execute stop-loss/take-profit if needed."""
        if not self._broker:
            return
        
        try:
            positions = self._broker.get_positions()
            
            for position in positions:
                self._check_position_limits(position)
                
        except Exception as e:
            logger.exception(f"Position check failed: {e}")
    
    def _check_position_limits(self, position: Any) -> None:
        """Check if position has hit stop-loss or take-profit."""
        # This is a simplified implementation
        # In production, you would track stop-loss/take-profit levels per position
        
        if position.pnl_percentage < -5.0:  # 5% loss
            logger.warning(f"Position {position.symbol} hit stop-loss ({position.pnl_percentage:.2f}%)")
            
            if self._config.get('auto_stop_loss', True):
                try:
                    self._broker.square_off_position(
                        symbol=position.symbol,
                        exchange=position.exchange,
                        product_type=position.product_type,
                    )
                    logger.info(f"Auto squared off position: {position.symbol}")
                except Exception as e:
                    logger.error(f"Failed to square off position: {e}")
    
    def _check_daily_loss_limit(self) -> bool:
        """
        Check if daily loss limit has been reached.
        
        Returns:
            True if trading can continue, False if limit reached
        """
        if not self._broker or not self._initial_capital:
            return True
        
        try:
            margin = self._broker.get_margin()
            current_value = margin.get('available_margin', 0) + margin.get('used_margin', 0)
            
            daily_pnl = current_value - self._initial_capital
            daily_pnl_pct = daily_pnl / self._initial_capital if self._initial_capital > 0 else 0
            
            self._daily_pnl = daily_pnl
            
            if daily_pnl_pct < -self._max_daily_loss_pct:
                logger.critical(f"Daily loss limit reached: {daily_pnl_pct:.2%}")
                self.activate_kill_switch()
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Could not check daily loss limit: {e}")
            return True
    
    def _check_rate_limit(self) -> bool:
        """
        Check if rate limit for order placement is reached.
        
        Returns:
            True if can place order, False if rate limited
        """
        max_orders_per_minute = self._config.get('max_orders_per_minute', 10)
        # Simplified implementation - in production, track order timestamps
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get scheduler status.
        
        Returns:
            Dictionary with status information
        """
        market_state = self._market_hours.get_market_state()
        
        return {
            'is_running': self._is_running,
            'is_paused': self._is_paused,
            'kill_switch_active': self._kill_switch_active,
            'mode': self._mode,
            'market_state': market_state,
            'start_time': self._start_time.isoformat() if self._start_time else None,
            'task_count': len(self._tasks),
            'strategy_count': len(self._strategies),
            'total_signals': self._total_signals,
            'total_orders': self._total_orders,
            'daily_pnl': self._daily_pnl,
        }
    
    def get_task_status(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific task.
        
        Args:
            name: Task name
            
        Returns:
            Dictionary with task status or None if not found
        """
        task = self._tasks.get(name)
        if not task:
            return None
        
        return {
            'name': task.name,
            'enabled': task.enabled,
            'last_run': task.last_run.isoformat() if task.last_run else None,
            'run_count': task.run_count,
            'error_count': task.error_count,
            'interval_seconds': task.interval_seconds,
            'during_market_hours_only': task.during_market_hours_only,
        }
    
    def get_all_task_status(self) -> List[Dict[str, Any]]:
        """Get status of all tasks."""
        return [self.get_task_status(name) for name in self._tasks]
