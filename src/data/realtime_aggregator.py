"""
Real-Time Data Aggregator Module.

Aggregates tick data into OHLCV candles and provides rolling calculations.
"""

import logging
import threading
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RealTimeAggregator:
    """
    Aggregates real-time tick data into OHLCV candles.
    
    Features:
    - Aggregate ticks into multiple timeframe candles (1m, 5m, 15m, etc.)
    - Rolling window calculations (VWAP, moving averages)
    - Real-time IV calculation updates
    - Thread-safe operations
    
    Example:
        >>> aggregator = RealTimeAggregator(intervals=['1m', '5m', '15m'])
        >>> aggregator.on_tick({'token': 'NIFTY', 'ltp': 19250.0, 'volume': 1000})
        >>> candles = aggregator.get_candles('NIFTY', '1m')
    """
    
    # Interval durations in seconds
    INTERVAL_SECONDS = {
        '1m': 60,
        '3m': 180,
        '5m': 300,
        '10m': 600,
        '15m': 900,
        '30m': 1800,
        '1h': 3600,
    }
    
    def __init__(
        self,
        intervals: Optional[List[str]] = None,
        max_candles: int = 500,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the RealTimeAggregator.
        
        Args:
            intervals: List of aggregation intervals (default: ['1m', '5m', '15m'])
            max_candles: Maximum candles to keep per symbol per interval
            config: Optional configuration dictionary
        """
        self._intervals = intervals or ['1m', '5m', '15m']
        self._max_candles = max_candles
        self._config = config or {}
        
        # Validate intervals
        for interval in self._intervals:
            if interval not in self.INTERVAL_SECONDS:
                raise ValueError(f"Unsupported interval: {interval}")
        
        # Data storage: symbol -> interval -> list of candles
        self._candles: Dict[str, Dict[str, deque]] = {}
        
        # Current (incomplete) candle: symbol -> interval -> candle dict
        self._current_candles: Dict[str, Dict[str, Dict[str, Any]]] = {}
        
        # Rolling calculations: symbol -> calculation data
        self._rolling_data: Dict[str, Dict[str, Any]] = {}
        
        # VWAP calculations: symbol -> vwap data
        self._vwap_data: Dict[str, Dict[str, float]] = {}
        
        # Callbacks for candle completion
        self._candle_callbacks: List[Callable] = []
        
        # Thread safety
        self._lock = threading.Lock()
        
        logger.info(f"Initialized RealTimeAggregator with intervals: {self._intervals}")
    
    def on_tick(self, tick_data: Dict[str, Any]) -> None:
        """
        Process an incoming tick.
        
        Args:
            tick_data: Tick data dictionary with keys:
                - token: Symbol token
                - ltp: Last traded price
                - volume: Trade volume (optional)
                - timestamp: Tick timestamp (optional)
        """
        token = tick_data.get('token', '')
        if not token:
            return
        
        ltp = tick_data.get('ltp', 0.0)
        if ltp <= 0:
            return
        
        volume = tick_data.get('volume', 0)
        timestamp = tick_data.get('timestamp')
        
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except (ValueError, TypeError):
                logger.debug(f"Could not parse timestamp '{timestamp}', using current time")
                timestamp = datetime.now()
        elif timestamp is None:
            timestamp = datetime.now()
        
        with self._lock:
            self._update_candles(token, ltp, volume, timestamp)
            self._update_vwap(token, ltp, volume)
    
    def get_candles(
        self,
        symbol: str,
        interval: str,
        count: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get completed candles for a symbol.
        
        Args:
            symbol: Symbol token
            interval: Candle interval
            count: Number of candles to return (default: all)
            
        Returns:
            List of candle dictionaries with keys:
                - timestamp, open, high, low, close, volume
        """
        with self._lock:
            if symbol not in self._candles or interval not in self._candles[symbol]:
                return []
            
            candles = list(self._candles[symbol][interval])
            
            if count is not None and count < len(candles):
                candles = candles[-count:]
            
            return candles
    
    def get_current_candle(
        self,
        symbol: str,
        interval: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the current (incomplete) candle for a symbol.
        
        Args:
            symbol: Symbol token
            interval: Candle interval
            
        Returns:
            Current candle dictionary or None
        """
        with self._lock:
            if symbol not in self._current_candles:
                return None
            if interval not in self._current_candles[symbol]:
                return None
            
            return self._current_candles[symbol][interval].copy()
    
    def get_vwap(self, symbol: str) -> Optional[float]:
        """
        Get the current VWAP for a symbol.
        
        Args:
            symbol: Symbol token
            
        Returns:
            VWAP value or None
        """
        with self._lock:
            if symbol not in self._vwap_data:
                return None
            
            vwap_info = self._vwap_data[symbol]
            total_volume = vwap_info.get('total_volume', 0)
            
            if total_volume <= 0:
                return None
            
            return vwap_info.get('cumulative_pv', 0) / total_volume
    
    def get_moving_average(
        self,
        symbol: str,
        interval: str,
        period: int,
        price_type: str = 'close'
    ) -> Optional[float]:
        """
        Calculate moving average from candles.
        
        Args:
            symbol: Symbol token
            interval: Candle interval
            period: MA period
            price_type: Price to use ('open', 'high', 'low', 'close')
            
        Returns:
            Moving average value or None
        """
        candles = self.get_candles(symbol, interval, period)
        
        if len(candles) < period:
            return None
        
        prices = [c.get(price_type, 0) for c in candles[-period:]]
        return sum(prices) / len(prices)
    
    def register_candle_callback(self, callback: Callable) -> None:
        """
        Register a callback for candle completion.
        
        Args:
            callback: Callable that receives (symbol, interval, candle)
        """
        if callback not in self._candle_callbacks:
            self._candle_callbacks.append(callback)
    
    def unregister_candle_callback(self, callback: Callable) -> None:
        """
        Unregister a candle callback.
        
        Args:
            callback: Callback to remove
        """
        if callback in self._candle_callbacks:
            self._candle_callbacks.remove(callback)
    
    def reset(self, symbol: Optional[str] = None) -> None:
        """
        Reset aggregator data.
        
        Args:
            symbol: Symbol to reset (None for all symbols)
        """
        with self._lock:
            if symbol:
                self._candles.pop(symbol, None)
                self._current_candles.pop(symbol, None)
                self._rolling_data.pop(symbol, None)
                self._vwap_data.pop(symbol, None)
            else:
                self._candles.clear()
                self._current_candles.clear()
                self._rolling_data.clear()
                self._vwap_data.clear()
        
        logger.info(f"Reset aggregator data for: {symbol or 'all symbols'}")
    
    def _update_candles(
        self,
        token: str,
        ltp: float,
        volume: int,
        timestamp: datetime
    ) -> None:
        """Update candles for all intervals."""
        # Initialize data structures if needed
        if token not in self._candles:
            self._candles[token] = {}
            self._current_candles[token] = {}
            for interval in self._intervals:
                self._candles[token][interval] = deque(maxlen=self._max_candles)
                self._current_candles[token][interval] = None
        
        for interval in self._intervals:
            self._update_candle_for_interval(token, interval, ltp, volume, timestamp)
    
    def _update_candle_for_interval(
        self,
        token: str,
        interval: str,
        ltp: float,
        volume: int,
        timestamp: datetime
    ) -> None:
        """Update candle for a specific interval."""
        interval_seconds = self.INTERVAL_SECONDS[interval]
        
        # Calculate candle start time
        epoch_seconds = int(timestamp.timestamp())
        candle_start_epoch = (epoch_seconds // interval_seconds) * interval_seconds
        candle_start = datetime.fromtimestamp(candle_start_epoch)
        
        current = self._current_candles[token].get(interval)
        
        # Check if we need to start a new candle
        if current is None or current['timestamp'] != candle_start:
            # Complete previous candle if exists
            if current is not None:
                self._candles[token][interval].append(current.copy())
                self._notify_candle_complete(token, interval, current)
            
            # Start new candle
            self._current_candles[token][interval] = {
                'timestamp': candle_start,
                'open': ltp,
                'high': ltp,
                'low': ltp,
                'close': ltp,
                'volume': volume,
                'tick_count': 1,
            }
        else:
            # Update existing candle
            current['high'] = max(current['high'], ltp)
            current['low'] = min(current['low'], ltp)
            current['close'] = ltp
            current['volume'] += volume
            current['tick_count'] += 1
    
    def _update_vwap(
        self,
        token: str,
        ltp: float,
        volume: int
    ) -> None:
        """Update VWAP calculation."""
        if token not in self._vwap_data:
            self._vwap_data[token] = {
                'cumulative_pv': 0.0,
                'total_volume': 0,
                'session_start': datetime.now().date(),
            }
        
        vwap_info = self._vwap_data[token]
        
        # Reset VWAP for new trading day
        current_date = datetime.now().date()
        if vwap_info['session_start'] != current_date:
            vwap_info['cumulative_pv'] = 0.0
            vwap_info['total_volume'] = 0
            vwap_info['session_start'] = current_date
        
        # Update VWAP
        if volume > 0:
            vwap_info['cumulative_pv'] += ltp * volume
            vwap_info['total_volume'] += volume
    
    def _notify_candle_complete(
        self,
        symbol: str,
        interval: str,
        candle: Dict[str, Any]
    ) -> None:
        """Notify callbacks of completed candle."""
        for callback in self._candle_callbacks:
            try:
                callback(symbol, interval, candle)
            except Exception as e:
                logger.exception(f"Candle callback exception: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get aggregator statistics.
        
        Returns:
            Dictionary with statistics
        """
        with self._lock:
            total_symbols = len(self._candles)
            total_candles = sum(
                sum(len(candles) for candles in symbol_candles.values())
                for symbol_candles in self._candles.values()
            )
            
            return {
                'total_symbols': total_symbols,
                'total_candles': total_candles,
                'intervals': self._intervals,
                'max_candles_per_interval': self._max_candles,
            }
