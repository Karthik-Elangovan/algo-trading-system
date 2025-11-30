"""
Data Pipeline Module.

Provides automated data pipelines for:
- Real-time data fetching during market hours
- Historical EOD data download after market close
- Data aggregation into OHLCV candles
- Data storage and management
- Data validation and cleanup
"""

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .market_hours import MarketHours

logger = logging.getLogger(__name__)


@dataclass
class DataFetchJob:
    """Represents a data fetch job."""
    name: str
    symbols: List[str]
    interval: str  # e.g., '1m', '5m', '15m', '1h', '1d'
    callback: Optional[Callable] = None
    last_fetch: Optional[datetime] = None
    fetch_count: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataPipeline:
    """
    Automated data pipeline for market data management.
    
    Features:
    - Real-time data fetching at configurable intervals
    - Historical EOD data download after market close
    - Auto-aggregate tick data into OHLCV candles
    - Save data to CSV/Parquet files
    - Data validation and deduplication
    - Cleanup jobs for stale data
    
    Example:
        >>> from src.automation import DataPipeline
        >>> from src.data.providers import MockDataProvider
        >>> 
        >>> pipeline = DataPipeline(
        ...     data_directory='data/market_data',
        ...     symbols=['NIFTY', 'BANKNIFTY'],
        ... )
        >>> pipeline.start()
    """
    
    VALID_INTERVALS = ['1m', '5m', '15m', '30m', '1h', '1d']
    
    def __init__(
        self,
        data_directory: str = "data/market_data",
        symbols: Optional[List[str]] = None,
        intervals: Optional[List[str]] = None,
        data_provider: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the DataPipeline.
        
        Args:
            data_directory: Directory for storing market data
            symbols: List of symbols to fetch
            intervals: List of intervals to aggregate ('1m', '5m', etc.)
            data_provider: Data provider instance for fetching data
            config: Configuration dictionary with:
                - realtime_interval_seconds: Interval for realtime fetch (default: 5)
                - eod_update_time: Time for EOD update (default: 16:00)
                - timezone: Market timezone (default: Asia/Kolkata)
                - max_retries: Max retries for failed fetches (default: 3)
                - retry_delay_seconds: Delay between retries (default: 5)
        """
        self._data_dir = Path(data_directory)
        self._symbols = symbols or ['NIFTY', 'BANKNIFTY']
        self._intervals = intervals or ['1m', '5m', '15m', '1h', '1d']
        self._data_provider = data_provider
        self._config = config or {}
        
        # Validate intervals
        for interval in self._intervals:
            if interval not in self.VALID_INTERVALS:
                raise ValueError(f"Invalid interval: {interval}. Valid intervals: {self.VALID_INTERVALS}")
        
        # Configuration
        self._realtime_interval = self._config.get('realtime_interval_seconds', 5)
        self._eod_update_time = self._config.get('eod_update_time', '16:00')
        self._timezone = self._config.get('timezone', 'Asia/Kolkata')
        self._max_retries = self._config.get('max_retries', 3)
        self._retry_delay = self._config.get('retry_delay_seconds', 5)
        
        # Market hours
        self._market_hours = MarketHours(timezone=self._timezone)
        
        # Scheduler
        self._scheduler = BackgroundScheduler(
            timezone=self._timezone,
            job_defaults={
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 60,
            }
        )
        
        # State
        self._is_running = False
        self._jobs: Dict[str, DataFetchJob] = {}
        self._lock = threading.Lock()
        
        # Data storage
        self._tick_data: Dict[str, List[Dict[str, Any]]] = {}
        self._candle_data: Dict[str, Dict[str, pd.DataFrame]] = {}  # symbol -> interval -> df
        
        # Statistics
        self._start_time: Optional[datetime] = None
        self._total_ticks = 0
        self._total_candles = 0
        self._total_files_saved = 0
        
        # Ensure data directory exists
        self._ensure_data_directory()
        
        logger.info(f"Initialized DataPipeline with symbols: {self._symbols}, intervals: {self._intervals}")
    
    def _ensure_data_directory(self) -> None:
        """Ensure data directory structure exists."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories for different data types
        (self._data_dir / 'ticks').mkdir(exist_ok=True)
        (self._data_dir / 'candles').mkdir(exist_ok=True)
        (self._data_dir / 'eod').mkdir(exist_ok=True)
    
    @property
    def is_running(self) -> bool:
        """Check if pipeline is running."""
        return self._is_running
    
    @property
    def symbols(self) -> List[str]:
        """Get list of symbols being tracked."""
        return self._symbols.copy()
    
    @property
    def intervals(self) -> List[str]:
        """Get list of intervals being aggregated."""
        return self._intervals.copy()
    
    def start(self) -> bool:
        """
        Start the data pipeline.
        
        Returns:
            True if started successfully
        """
        if self._is_running:
            logger.warning("DataPipeline already running")
            return True
        
        logger.info("Starting DataPipeline")
        
        self._start_time = datetime.now()
        
        # Add default jobs
        self._add_realtime_job()
        self._add_eod_job()
        self._add_cleanup_job()
        
        # Start scheduler
        self._scheduler.start()
        self._is_running = True
        
        logger.info("DataPipeline started")
        return True
    
    def stop(self) -> bool:
        """
        Stop the data pipeline.
        
        Returns:
            True if stopped successfully
        """
        if not self._is_running:
            return True
        
        logger.info("Stopping DataPipeline")
        
        # Save any pending data
        self._save_all_data()
        
        # Shutdown scheduler
        self._scheduler.shutdown(wait=True)
        self._is_running = False
        
        logger.info("DataPipeline stopped")
        return True
    
    def _add_realtime_job(self) -> None:
        """Add real-time data fetching job."""
        job = DataFetchJob(
            name='realtime_fetch',
            symbols=self._symbols,
            interval='tick',
        )
        
        def fetch_wrapper():
            if self._market_hours.is_market_open():
                self._fetch_realtime_data()
        
        self._scheduler.add_job(
            fetch_wrapper,
            IntervalTrigger(seconds=self._realtime_interval),
            id='realtime_fetch',
        )
        
        self._jobs['realtime_fetch'] = job
        logger.info(f"Added realtime fetch job (interval: {self._realtime_interval}s)")
    
    def _add_eod_job(self) -> None:
        """Add EOD data download job."""
        hour, minute = map(int, self._eod_update_time.split(':'))
        
        job = DataFetchJob(
            name='eod_update',
            symbols=self._symbols,
            interval='1d',
        )
        
        def eod_wrapper():
            if self._market_hours.is_trading_day():
                self._fetch_eod_data()
        
        self._scheduler.add_job(
            eod_wrapper,
            CronTrigger(hour=hour, minute=minute, day_of_week='mon-fri'),
            id='eod_update',
        )
        
        self._jobs['eod_update'] = job
        logger.info(f"Added EOD update job (time: {self._eod_update_time})")
    
    def _add_cleanup_job(self) -> None:
        """Add data cleanup job."""
        # Run cleanup at 23:00 every day
        self._scheduler.add_job(
            self._cleanup_stale_data,
            CronTrigger(hour=23, minute=0),
            id='cleanup',
        )
        logger.info("Added cleanup job (time: 23:00)")
    
    def _fetch_realtime_data(self) -> None:
        """Fetch real-time data for all symbols."""
        if not self._data_provider:
            # Generate mock tick data for testing
            # Use configurable base prices or reasonable defaults
            mock_base_prices = self._config.get('mock_base_prices', {
                'NIFTY': 19250.0,
                'BANKNIFTY': 43500.0,
                'SENSEX': 64800.0,
            })
            default_price = self._config.get('mock_default_price', 10000.0)
            
            for symbol in self._symbols:
                base_price = mock_base_prices.get(symbol, default_price)
                # Add small random variation for more realistic mock data
                import random
                variation = base_price * random.uniform(-0.001, 0.001)
                
                self._on_tick({
                    'token': symbol,
                    'ltp': base_price + variation,
                    'volume': random.randint(100, 10000),
                    'timestamp': datetime.now(),
                })
            return
        
        for symbol in self._symbols:
            try:
                quote = self._data_provider.get_quote(symbol)
                if quote:
                    self._on_tick({
                        'token': symbol,
                        'ltp': quote.get('ltp', 0),
                        'high': quote.get('high', 0),
                        'low': quote.get('low', 0),
                        'volume': quote.get('volume', 0),
                        'timestamp': datetime.now(),
                    })
                    
            except Exception as e:
                logger.error(f"Failed to fetch data for {symbol}: {e}")
                
                job = self._jobs.get('realtime_fetch')
                if job:
                    job.error_count += 1
    
    def _fetch_eod_data(self) -> None:
        """Fetch end-of-day historical data."""
        logger.info("Starting EOD data fetch")
        
        job = self._jobs.get('eod_update')
        
        for symbol in self._symbols:
            try:
                self._fetch_historical_data(
                    symbol=symbol,
                    days_back=1,
                    interval='1d',
                )
                
                if job:
                    job.fetch_count += 1
                    job.last_fetch = datetime.now()
                    
            except Exception as e:
                logger.error(f"Failed to fetch EOD data for {symbol}: {e}")
                if job:
                    job.error_count += 1
        
        # Save EOD data
        self._save_eod_data()
        logger.info("Completed EOD data fetch")
    
    def _fetch_historical_data(
        self,
        symbol: str,
        days_back: int,
        interval: str = '1d',
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a symbol.
        
        Args:
            symbol: Trading symbol
            days_back: Number of days to fetch
            interval: Data interval
            
        Returns:
            DataFrame with historical data
        """
        if not self._data_provider:
            logger.warning("No data provider configured for historical data")
            return None
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        retries = 0
        while retries < self._max_retries:
            try:
                data = self._data_provider.get_historical_data(
                    symbol=symbol,
                    exchange='NSE',
                    interval=interval,
                    from_date=start_date,
                    to_date=end_date,
                )
                
                if data:
                    df = pd.DataFrame(data)
                    return df
                    
            except Exception as e:
                logger.warning(f"Attempt {retries + 1} failed for {symbol}: {e}")
                retries += 1
                time.sleep(self._retry_delay)
        
        logger.error(f"Failed to fetch historical data for {symbol} after {self._max_retries} attempts")
        return None
    
    def _on_tick(self, tick_data: Dict[str, Any]) -> None:
        """
        Process incoming tick data.
        
        Args:
            tick_data: Dictionary with tick data
        """
        symbol = tick_data.get('token', '')
        if not symbol:
            return
        
        with self._lock:
            if symbol not in self._tick_data:
                self._tick_data[symbol] = []
            
            self._tick_data[symbol].append(tick_data)
            self._total_ticks += 1
        
        # Aggregate into candles
        self._aggregate_tick(tick_data)
    
    def _aggregate_tick(self, tick_data: Dict[str, Any]) -> None:
        """
        Aggregate tick data into OHLCV candles.
        
        Args:
            tick_data: Dictionary with tick data
        """
        symbol = tick_data.get('token', '')
        ltp = tick_data.get('ltp', 0)
        volume = tick_data.get('volume', 0)
        timestamp = tick_data.get('timestamp', datetime.now())
        
        if not symbol or not ltp:
            return
        
        with self._lock:
            if symbol not in self._candle_data:
                self._candle_data[symbol] = {}
            
            for interval in self._intervals:
                self._update_candle(symbol, interval, ltp, volume, timestamp)
    
    def _update_candle(
        self,
        symbol: str,
        interval: str,
        ltp: float,
        volume: int,
        timestamp: datetime,
    ) -> None:
        """Update candle data for a symbol and interval."""
        interval_minutes = self._interval_to_minutes(interval)
        
        # Calculate candle timestamp (rounded to interval)
        candle_ts = timestamp.replace(
            minute=(timestamp.minute // interval_minutes) * interval_minutes,
            second=0,
            microsecond=0,
        )
        
        if interval not in self._candle_data[symbol]:
            self._candle_data[symbol][interval] = pd.DataFrame(
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
        
        df = self._candle_data[symbol][interval]
        
        # Check if candle exists
        mask = df['timestamp'] == candle_ts
        
        if mask.any():
            # Update existing candle
            idx = df[mask].index[0]
            df.loc[idx, 'high'] = max(df.loc[idx, 'high'], ltp)
            df.loc[idx, 'low'] = min(df.loc[idx, 'low'], ltp)
            df.loc[idx, 'close'] = ltp
            df.loc[idx, 'volume'] += volume
        else:
            # Create new candle
            new_candle = pd.DataFrame([{
                'timestamp': candle_ts,
                'open': ltp,
                'high': ltp,
                'low': ltp,
                'close': ltp,
                'volume': volume,
            }])
            self._candle_data[symbol][interval] = pd.concat(
                [df, new_candle], ignore_index=True
            )
            self._total_candles += 1
    
    def _interval_to_minutes(self, interval: str) -> int:
        """Convert interval string to minutes."""
        mapping = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '1d': 1440,
        }
        return mapping.get(interval, 1)
    
    def _save_all_data(self) -> None:
        """Save all pending data to files."""
        self._save_tick_data()
        self._save_candle_data()
    
    def _save_tick_data(self) -> None:
        """
        Save tick data to files.
        
        Note:
            For high-frequency data with large volumes, consider:
            - Using Parquet format for better compression and performance
            - Implementing buffered writes to reduce I/O operations
            - Using async I/O for non-blocking file operations
        """
        today = datetime.now().strftime('%Y%m%d')
        
        with self._lock:
            for symbol, ticks in self._tick_data.items():
                if not ticks:
                    continue
                
                filename = self._data_dir / 'ticks' / f"{symbol}_{today}.csv"
                
                df = pd.DataFrame(ticks)
                
                # Append if file exists, otherwise create new
                if filename.exists():
                    existing = pd.read_csv(filename)
                    df = pd.concat([existing, df], ignore_index=True)
                    df = df.drop_duplicates()
                
                df.to_csv(filename, index=False)
                self._total_files_saved += 1
                logger.debug(f"Saved tick data to {filename}")
    
    def _save_candle_data(self) -> None:
        """Save candle data to files."""
        today = datetime.now().strftime('%Y%m%d')
        
        with self._lock:
            for symbol, intervals in self._candle_data.items():
                for interval, df in intervals.items():
                    if df.empty:
                        continue
                    
                    filename = self._data_dir / 'candles' / f"{symbol}_{interval}_{today}.csv"
                    
                    # Append if file exists
                    if filename.exists():
                        existing = pd.read_csv(filename)
                        df = pd.concat([existing, df], ignore_index=True)
                        df = df.drop_duplicates(subset=['timestamp'])
                    
                    df.to_csv(filename, index=False)
                    self._total_files_saved += 1
                    logger.debug(f"Saved candle data to {filename}")
    
    def _save_eod_data(self) -> None:
        """Save EOD data to files."""
        today = datetime.now().strftime('%Y%m%d')
        
        with self._lock:
            for symbol in self._symbols:
                if symbol not in self._candle_data:
                    continue
                
                if '1d' not in self._candle_data[symbol]:
                    continue
                
                df = self._candle_data[symbol]['1d']
                if df.empty:
                    continue
                
                filename = self._data_dir / 'eod' / f"{symbol}_eod.csv"
                
                # Append if file exists
                if filename.exists():
                    existing = pd.read_csv(filename)
                    df = pd.concat([existing, df], ignore_index=True)
                    df = df.drop_duplicates(subset=['timestamp'])
                    df = df.sort_values('timestamp')
                
                df.to_csv(filename, index=False)
                self._total_files_saved += 1
                logger.info(f"Saved EOD data to {filename}")
    
    def _cleanup_stale_data(self) -> None:
        """Clean up stale data files."""
        logger.info("Starting data cleanup")
        
        retention_days = self._config.get('retention_days', 30)
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        files_deleted = 0
        
        # Clean tick data
        for filepath in (self._data_dir / 'ticks').glob('*.csv'):
            try:
                # Extract date from filename
                parts = filepath.stem.split('_')
                if len(parts) >= 2:
                    file_date = datetime.strptime(parts[-1], '%Y%m%d')
                    if file_date < cutoff_date:
                        filepath.unlink()
                        files_deleted += 1
                        logger.debug(f"Deleted stale file: {filepath}")
            except (ValueError, OSError) as e:
                logger.warning(f"Could not process file {filepath}: {e}")
        
        logger.info(f"Cleanup completed: {files_deleted} files deleted")
    
    def add_symbol(self, symbol: str) -> bool:
        """
        Add a symbol to track.
        
        Args:
            symbol: Symbol to add
            
        Returns:
            True if added successfully
        """
        if symbol in self._symbols:
            return False
        
        self._symbols.append(symbol)
        logger.info(f"Added symbol: {symbol}")
        return True
    
    def remove_symbol(self, symbol: str) -> bool:
        """
        Remove a symbol from tracking.
        
        Args:
            symbol: Symbol to remove
            
        Returns:
            True if removed successfully
        """
        if symbol not in self._symbols:
            return False
        
        self._symbols.remove(symbol)
        logger.info(f"Removed symbol: {symbol}")
        return True
    
    def get_candles(
        self,
        symbol: str,
        interval: str,
        count: Optional[int] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Get candle data for a symbol and interval.
        
        Args:
            symbol: Trading symbol
            interval: Candle interval
            count: Number of candles to return (default: all)
            
        Returns:
            DataFrame with candle data
        """
        with self._lock:
            if symbol not in self._candle_data:
                return None
            
            if interval not in self._candle_data[symbol]:
                return None
            
            df = self._candle_data[symbol][interval].copy()
            
            if count and len(df) > count:
                df = df.tail(count)
            
            return df
    
    def get_latest_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get latest tick for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with tick data
        """
        with self._lock:
            if symbol not in self._tick_data or not self._tick_data[symbol]:
                return None
            
            return self._tick_data[symbol][-1].copy()
    
    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        Validate data for completeness and accuracy.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            True if data is valid
        """
        if df.empty:
            return False
        
        required_columns = ['timestamp', 'open', 'high', 'low', 'close']
        for col in required_columns:
            if col not in df.columns:
                logger.warning(f"Missing required column: {col}")
                return False
        
        # Check for null values
        if df[required_columns].isnull().any().any():
            logger.warning("Data contains null values")
            return False
        
        # Check OHLC consistency
        valid_ohlc = (
            (df['high'] >= df['low']) &
            (df['high'] >= df['open']) &
            (df['high'] >= df['close']) &
            (df['low'] <= df['open']) &
            (df['low'] <= df['close'])
        )
        
        if not valid_ohlc.all():
            logger.warning("Invalid OHLC data detected")
            return False
        
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get pipeline status.
        
        Returns:
            Dictionary with status information
        """
        market_state = self._market_hours.get_market_state()
        
        return {
            'is_running': self._is_running,
            'market_state': market_state,
            'start_time': self._start_time.isoformat() if self._start_time else None,
            'symbols': self._symbols.copy(),
            'intervals': self._intervals.copy(),
            'job_count': len(self._jobs),
            'total_ticks': self._total_ticks,
            'total_candles': self._total_candles,
            'total_files_saved': self._total_files_saved,
            'data_directory': str(self._data_dir),
        }
    
    def get_job_status(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific job.
        
        Args:
            name: Job name
            
        Returns:
            Dictionary with job status or None if not found
        """
        job = self._jobs.get(name)
        if not job:
            return None
        
        return {
            'name': job.name,
            'symbols': job.symbols,
            'interval': job.interval,
            'last_fetch': job.last_fetch.isoformat() if job.last_fetch else None,
            'fetch_count': job.fetch_count,
            'error_count': job.error_count,
        }
