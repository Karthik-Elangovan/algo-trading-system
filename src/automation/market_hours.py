"""
Market Hours Utilities Module.

Provides utilities for handling Indian stock market timing
(NSE: 9:15 AM - 3:30 PM IST).
"""

import logging
from datetime import datetime, time, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Indian Standard Time
IST = ZoneInfo("Asia/Kolkata")

# NSE Market Timings
MARKET_OPEN_TIME = time(9, 15)
MARKET_CLOSE_TIME = time(15, 30)
PRE_MARKET_TIME = time(9, 0)
POST_MARKET_TIME = time(15, 45)

# NSE Holidays 2024-2025 (partial list - should be updated annually)
NSE_HOLIDAYS = [
    datetime(2024, 1, 26),   # Republic Day
    datetime(2024, 3, 8),    # Maha Shivaratri
    datetime(2024, 3, 25),   # Holi
    datetime(2024, 3, 29),   # Good Friday
    datetime(2024, 4, 11),   # Id-Ul-Fitr
    datetime(2024, 4, 14),   # Ambedkar Jayanti
    datetime(2024, 4, 17),   # Ram Navami
    datetime(2024, 4, 21),   # Mahavir Jayanti
    datetime(2024, 5, 1),    # May Day
    datetime(2024, 5, 20),   # Election
    datetime(2024, 5, 23),   # Buddha Purnima
    datetime(2024, 6, 17),   # Eid ul Adha
    datetime(2024, 7, 17),   # Muharram
    datetime(2024, 8, 15),   # Independence Day
    datetime(2024, 10, 2),   # Mahatma Gandhi Jayanti
    datetime(2024, 11, 1),   # Diwali Laxmi Pujan
    datetime(2024, 11, 15),  # Guru Nanak Jayanti
    datetime(2024, 12, 25),  # Christmas
    datetime(2025, 1, 26),   # Republic Day
    datetime(2025, 2, 26),   # Maha Shivaratri
    datetime(2025, 3, 14),   # Holi
    datetime(2025, 4, 14),   # Ambedkar Jayanti
    datetime(2025, 4, 18),   # Good Friday
    datetime(2025, 8, 15),   # Independence Day
    datetime(2025, 10, 2),   # Mahatma Gandhi Jayanti
    datetime(2025, 12, 25),  # Christmas
]


class MarketHours:
    """
    Utility class for handling market hours.
    
    Provides methods to check if market is open, get time to market open/close,
    and other market timing related utilities.
    """
    
    def __init__(
        self,
        timezone: str = "Asia/Kolkata",
        market_open: Optional[time] = None,
        market_close: Optional[time] = None,
        pre_market: Optional[time] = None,
        post_market: Optional[time] = None,
    ):
        """
        Initialize MarketHours.
        
        Args:
            timezone: Market timezone (default: Asia/Kolkata)
            market_open: Market open time (default: 9:15 AM)
            market_close: Market close time (default: 3:30 PM)
            pre_market: Pre-market session start time (default: 9:00 AM)
            post_market: Post-market session end time (default: 3:45 PM)
        """
        self.timezone = ZoneInfo(timezone)
        self.market_open = market_open or MARKET_OPEN_TIME
        self.market_close = market_close or MARKET_CLOSE_TIME
        self.pre_market = pre_market or PRE_MARKET_TIME
        self.post_market = post_market or POST_MARKET_TIME
        self._holidays = set(h.date() for h in NSE_HOLIDAYS)
    
    def now(self) -> datetime:
        """Get current time in market timezone."""
        return datetime.now(self.timezone)
    
    def is_trading_day(self, date: Optional[datetime] = None) -> bool:
        """
        Check if a given date is a trading day.
        
        Args:
            date: Date to check (default: today)
            
        Returns:
            True if trading day, False otherwise
        """
        if date is None:
            date = self.now()
        
        # Convert to date if datetime
        check_date = date.date() if isinstance(date, datetime) else date
        
        # Check if weekend (Saturday=5, Sunday=6)
        if check_date.weekday() >= 5:
            return False
        
        # Check if holiday
        if check_date in self._holidays:
            return False
        
        return True
    
    def is_market_open(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if market is currently open.
        
        Args:
            dt: Datetime to check (default: now)
            
        Returns:
            True if market is open, False otherwise
        """
        if dt is None:
            dt = self.now()
        
        # Check if trading day
        if not self.is_trading_day(dt):
            return False
        
        # Check if within trading hours
        current_time = dt.time()
        return self.market_open <= current_time < self.market_close
    
    def is_pre_market(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if currently in pre-market session.
        
        Args:
            dt: Datetime to check (default: now)
            
        Returns:
            True if in pre-market session
        """
        if dt is None:
            dt = self.now()
        
        if not self.is_trading_day(dt):
            return False
        
        current_time = dt.time()
        return self.pre_market <= current_time < self.market_open
    
    def is_post_market(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if currently in post-market session.
        
        Args:
            dt: Datetime to check (default: now)
            
        Returns:
            True if in post-market session
        """
        if dt is None:
            dt = self.now()
        
        if not self.is_trading_day(dt):
            return False
        
        current_time = dt.time()
        return self.market_close <= current_time <= self.post_market
    
    def get_market_state(self, dt: Optional[datetime] = None) -> str:
        """
        Get current market state.
        
        Args:
            dt: Datetime to check (default: now)
            
        Returns:
            One of: 'pre_market', 'open', 'post_market', 'closed'
        """
        if dt is None:
            dt = self.now()
        
        if self.is_market_open(dt):
            return 'open'
        elif self.is_pre_market(dt):
            return 'pre_market'
        elif self.is_post_market(dt):
            return 'post_market'
        else:
            return 'closed'
    
    def get_next_market_open(self, dt: Optional[datetime] = None) -> datetime:
        """
        Get the next market open datetime.
        
        Args:
            dt: Start datetime (default: now)
            
        Returns:
            Datetime of next market open
        """
        if dt is None:
            dt = self.now()
        
        # If market is currently open, return current open time
        if self.is_market_open(dt):
            return dt.replace(
                hour=self.market_open.hour,
                minute=self.market_open.minute,
                second=0,
                microsecond=0
            )
        
        # Start checking from current date
        check_date = dt.date()
        current_time = dt.time()
        
        # If we're before market open on a trading day, return today
        if self.is_trading_day(dt) and current_time < self.market_open:
            return dt.replace(
                hour=self.market_open.hour,
                minute=self.market_open.minute,
                second=0,
                microsecond=0
            )
        
        # Otherwise, find next trading day
        check_date = check_date + timedelta(days=1)
        while True:
            check_dt = datetime(
                check_date.year,
                check_date.month,
                check_date.day,
                self.market_open.hour,
                self.market_open.minute,
                tzinfo=self.timezone
            )
            
            if self.is_trading_day(check_dt):
                return check_dt
            
            check_date = check_date + timedelta(days=1)
            
            # Safety: don't loop forever
            if (check_date - dt.date()).days > 30:
                raise RuntimeError("Could not find next trading day within 30 days")
    
    def get_next_market_close(self, dt: Optional[datetime] = None) -> datetime:
        """
        Get the next market close datetime.
        
        Args:
            dt: Start datetime (default: now)
            
        Returns:
            Datetime of next market close
        """
        if dt is None:
            dt = self.now()
        
        # If market is currently open, return today's close time
        if self.is_market_open(dt):
            return dt.replace(
                hour=self.market_close.hour,
                minute=self.market_close.minute,
                second=0,
                microsecond=0
            )
        
        # Otherwise, get next open and then calculate close
        next_open = self.get_next_market_open(dt)
        return next_open.replace(
            hour=self.market_close.hour,
            minute=self.market_close.minute
        )
    
    def time_to_market_open(self, dt: Optional[datetime] = None) -> timedelta:
        """
        Get time remaining until market opens.
        
        Args:
            dt: Current datetime (default: now)
            
        Returns:
            Timedelta until market opens (zero if already open)
        """
        if dt is None:
            dt = self.now()
        
        if self.is_market_open(dt):
            return timedelta(0)
        
        next_open = self.get_next_market_open(dt)
        return next_open - dt
    
    def time_to_market_close(self, dt: Optional[datetime] = None) -> timedelta:
        """
        Get time remaining until market closes.
        
        Args:
            dt: Current datetime (default: now)
            
        Returns:
            Timedelta until market closes
        """
        if dt is None:
            dt = self.now()
        
        next_close = self.get_next_market_close(dt)
        return next_close - dt
    
    def get_trading_minutes_elapsed(self, dt: Optional[datetime] = None) -> int:
        """
        Get number of trading minutes elapsed since market open.
        
        Args:
            dt: Current datetime (default: now)
            
        Returns:
            Minutes elapsed since market open (0 if market not open)
        """
        if dt is None:
            dt = self.now()
        
        if not self.is_market_open(dt):
            return 0
        
        market_open_dt = dt.replace(
            hour=self.market_open.hour,
            minute=self.market_open.minute,
            second=0,
            microsecond=0
        )
        
        delta = dt - market_open_dt
        return int(delta.total_seconds() / 60)
    
    def get_trading_minutes_remaining(self, dt: Optional[datetime] = None) -> int:
        """
        Get number of trading minutes remaining until market close.
        
        Args:
            dt: Current datetime (default: now)
            
        Returns:
            Minutes remaining until market close (0 if market not open)
        """
        if dt is None:
            dt = self.now()
        
        if not self.is_market_open(dt):
            return 0
        
        market_close_dt = dt.replace(
            hour=self.market_close.hour,
            minute=self.market_close.minute,
            second=0,
            microsecond=0
        )
        
        delta = market_close_dt - dt
        return max(0, int(delta.total_seconds() / 60))
    
    def add_holiday(self, date: datetime) -> None:
        """Add a holiday to the list."""
        self._holidays.add(date.date() if isinstance(date, datetime) else date)
    
    def remove_holiday(self, date: datetime) -> None:
        """Remove a holiday from the list."""
        check_date = date.date() if isinstance(date, datetime) else date
        self._holidays.discard(check_date)


# Module-level convenience functions
_default_market_hours = MarketHours()


def is_market_open(dt: Optional[datetime] = None) -> bool:
    """Check if market is currently open."""
    return _default_market_hours.is_market_open(dt)


def get_next_market_open(dt: Optional[datetime] = None) -> datetime:
    """Get the next market open datetime."""
    return _default_market_hours.get_next_market_open(dt)


def is_trading_day(date: Optional[datetime] = None) -> bool:
    """Check if a given date is a trading day."""
    return _default_market_hours.is_trading_day(date)


def get_market_state(dt: Optional[datetime] = None) -> str:
    """Get current market state."""
    return _default_market_hours.get_market_state(dt)
