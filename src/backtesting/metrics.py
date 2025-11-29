"""
Performance Metrics Module

Calculates comprehensive performance metrics for backtesting results.

Metrics Include:
- Returns: Total return, CAGR, monthly returns
- Risk Metrics: Sharpe Ratio, Sortino Ratio, Calmar Ratio
- Drawdown: Maximum drawdown, average drawdown, recovery time
- Trade Statistics: Win rate, profit factor, average win/loss
- Risk-adjusted: Information ratio, Treynor ratio
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class DrawdownInfo:
    """
    Information about a drawdown period.
    
    Attributes:
        start_date: When drawdown started
        end_date: When drawdown ended (or None if ongoing)
        recovery_date: When equity recovered (or None if not recovered)
        max_drawdown: Maximum drawdown percentage during this period
        duration_days: Number of days in drawdown
        recovery_days: Number of days to recover (or None)
    """
    start_date: datetime
    end_date: Optional[datetime] = None
    recovery_date: Optional[datetime] = None
    max_drawdown: float = 0.0
    duration_days: int = 0
    recovery_days: Optional[int] = None


@dataclass
class PerformanceMetrics:
    """
    Comprehensive performance metrics for a backtest.
    
    Attributes:
        # Return Metrics
        total_return: Total return as decimal
        cagr: Compound Annual Growth Rate
        monthly_returns: Series of monthly returns
        
        # Risk Metrics
        sharpe_ratio: Sharpe Ratio (annualized)
        sortino_ratio: Sortino Ratio (annualized)
        calmar_ratio: Calmar Ratio
        
        # Drawdown Metrics
        max_drawdown: Maximum drawdown as decimal
        avg_drawdown: Average drawdown
        max_drawdown_duration: Maximum drawdown duration in days
        
        # Trade Statistics
        total_trades: Total number of trades
        winning_trades: Number of winning trades
        losing_trades: Number of losing trades
        win_rate: Win rate as decimal
        profit_factor: Profit factor (gross profit / gross loss)
        avg_win: Average winning trade
        avg_loss: Average losing trade
        max_win: Largest winning trade
        max_loss: Largest losing trade
        avg_trade: Average trade return
        max_consecutive_wins: Maximum consecutive wins
        max_consecutive_losses: Maximum consecutive losses
        
        # Risk-adjusted Metrics
        information_ratio: Information ratio
        treynor_ratio: Treynor ratio
        volatility: Annualized volatility
        downside_deviation: Downside deviation
    """
    # Return Metrics
    total_return: float = 0.0
    cagr: float = 0.0
    monthly_returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    
    # Risk Metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    # Drawdown Metrics
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    drawdown_series: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    
    # Trade Statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    avg_trade: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    # Risk-adjusted Metrics
    information_ratio: float = 0.0
    treynor_ratio: float = 0.0
    volatility: float = 0.0
    downside_deviation: float = 0.0
    
    # Additional
    risk_free_rate: float = 0.07
    trading_days: int = 252
    
    @classmethod
    def from_returns(
        cls,
        returns: pd.Series,
        equity_curve: pd.Series,
        trades: List[Any],
        risk_free_rate: float = 0.07,
        benchmark_returns: Optional[pd.Series] = None,
        trading_days: int = 252
    ) -> "PerformanceMetrics":
        """
        Calculate all metrics from returns series.
        
        Args:
            returns: Daily returns series
            equity_curve: Equity curve series
            trades: List of Trade objects
            risk_free_rate: Annual risk-free rate
            benchmark_returns: Optional benchmark returns for IR
            trading_days: Trading days per year
        
        Returns:
            PerformanceMetrics instance with all metrics calculated
        """
        metrics = cls(
            risk_free_rate=risk_free_rate,
            trading_days=trading_days
        )
        
        # Filter out NaN values
        returns = returns.dropna()
        equity_curve = equity_curve.dropna()
        
        if len(returns) == 0 or len(equity_curve) == 0:
            return metrics
        
        # Calculate return metrics
        metrics.total_return = cls._calculate_total_return(equity_curve)
        metrics.cagr = cls._calculate_cagr(equity_curve, trading_days)
        metrics.monthly_returns = cls._calculate_monthly_returns(returns, equity_curve)
        
        # Calculate risk metrics
        metrics.volatility = cls._calculate_volatility(returns, trading_days)
        metrics.downside_deviation = cls._calculate_downside_deviation(returns, trading_days)
        metrics.sharpe_ratio = cls._calculate_sharpe_ratio(returns, risk_free_rate, trading_days)
        metrics.sortino_ratio = cls._calculate_sortino_ratio(returns, risk_free_rate, trading_days)
        
        # Calculate drawdown metrics
        dd_series = cls._calculate_drawdown_series(equity_curve)
        metrics.drawdown_series = dd_series
        metrics.max_drawdown = abs(dd_series.min()) if len(dd_series) > 0 else 0
        metrics.avg_drawdown = abs(dd_series[dd_series < 0].mean()) if len(dd_series[dd_series < 0]) > 0 else 0
        metrics.max_drawdown_duration = cls._calculate_max_drawdown_duration(dd_series)
        
        # Calculate Calmar ratio
        metrics.calmar_ratio = metrics.cagr / metrics.max_drawdown if metrics.max_drawdown > 0 else 0
        
        # Calculate trade statistics
        if trades:
            metrics._calculate_trade_statistics(trades)
        
        # Calculate information ratio if benchmark provided
        if benchmark_returns is not None and len(benchmark_returns) > 0:
            metrics.information_ratio = cls._calculate_information_ratio(
                returns, benchmark_returns, trading_days
            )
        
        return metrics
    
    @staticmethod
    def _calculate_total_return(equity_curve: pd.Series) -> float:
        """Calculate total return from equity curve."""
        if len(equity_curve) < 2:
            return 0.0
        return (equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0]
    
    @staticmethod
    def _calculate_cagr(
        equity_curve: pd.Series,
        trading_days: int = 252
    ) -> float:
        """
        Calculate Compound Annual Growth Rate.
        
        Formula: CAGR = (Final Value / Initial Value)^(1/years) - 1
        """
        if len(equity_curve) < 2:
            return 0.0
        
        initial_value = equity_curve.iloc[0]
        final_value = equity_curve.iloc[-1]
        
        if initial_value <= 0:
            return 0.0
        
        num_years = len(equity_curve) / trading_days
        
        if num_years <= 0:
            return 0.0
        
        if final_value <= 0:
            return -1.0
        
        return (final_value / initial_value) ** (1 / num_years) - 1
    
    @staticmethod
    def _calculate_monthly_returns(
        returns: pd.Series,
        equity_curve: pd.Series
    ) -> pd.Series:
        """Calculate monthly returns."""
        if len(equity_curve) < 2:
            return pd.Series(dtype=float)
        
        # If equity_curve has datetime index
        if isinstance(equity_curve.index, pd.DatetimeIndex):
            monthly = equity_curve.resample('ME').last()
            monthly_returns = monthly.pct_change().dropna()
            return monthly_returns
        
        return pd.Series(dtype=float)
    
    @staticmethod
    def _calculate_volatility(
        returns: pd.Series,
        trading_days: int = 252
    ) -> float:
        """
        Calculate annualized volatility.
        
        Formula: Volatility = std(returns) * sqrt(trading_days)
        """
        if len(returns) < 2:
            return 0.0
        return returns.std() * np.sqrt(trading_days)
    
    @staticmethod
    def _calculate_downside_deviation(
        returns: pd.Series,
        trading_days: int = 252,
        threshold: float = 0.0
    ) -> float:
        """
        Calculate downside deviation (semi-deviation).
        
        Only considers returns below the threshold.
        
        Formula: DD = std(returns[returns < threshold]) * sqrt(trading_days)
        """
        if len(returns) < 2:
            return 0.0
        
        downside_returns = returns[returns < threshold]
        
        if len(downside_returns) < 2:
            return 0.0
        
        return downside_returns.std() * np.sqrt(trading_days)
    
    @staticmethod
    def _calculate_sharpe_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.07,
        trading_days: int = 252
    ) -> float:
        """
        Calculate Sharpe Ratio.
        
        Formula: Sharpe = (Mean Return - Risk Free Rate) / Std(Returns) * sqrt(trading_days)
        
        Where returns and risk-free rate are both daily.
        """
        if len(returns) < 2:
            return 0.0
        
        daily_rf = risk_free_rate / trading_days
        excess_returns = returns - daily_rf
        
        std = excess_returns.std()
        if std <= 0:
            return 0.0
        
        return (excess_returns.mean() / std) * np.sqrt(trading_days)
    
    @staticmethod
    def _calculate_sortino_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.07,
        trading_days: int = 252
    ) -> float:
        """
        Calculate Sortino Ratio.
        
        Like Sharpe, but uses downside deviation instead of standard deviation.
        
        Formula: Sortino = (Mean Return - Risk Free Rate) / Downside Deviation * sqrt(trading_days)
        """
        if len(returns) < 2:
            return 0.0
        
        daily_rf = risk_free_rate / trading_days
        excess_returns = returns - daily_rf
        
        # Calculate downside deviation
        downside_returns = excess_returns[excess_returns < 0]
        if len(downside_returns) < 2:
            return 0.0
        
        downside_std = downside_returns.std()
        if downside_std <= 0:
            return 0.0
        
        return (excess_returns.mean() / downside_std) * np.sqrt(trading_days)
    
    @staticmethod
    def _calculate_drawdown_series(equity_curve: pd.Series) -> pd.Series:
        """
        Calculate drawdown series.
        
        Drawdown = (Current Value - Peak Value) / Peak Value
        """
        if len(equity_curve) < 2:
            return pd.Series(dtype=float)
        
        rolling_max = equity_curve.expanding().max()
        drawdown = (equity_curve - rolling_max) / rolling_max
        
        return drawdown
    
    @staticmethod
    def _calculate_max_drawdown_duration(drawdown_series: pd.Series) -> int:
        """
        Calculate maximum drawdown duration in days.
        
        Counts consecutive days in drawdown.
        """
        if len(drawdown_series) < 2:
            return 0
        
        # Find periods where we're in drawdown (drawdown < 0)
        in_drawdown = drawdown_series < 0
        
        # Count consecutive drawdown periods
        max_duration = 0
        current_duration = 0
        
        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0
        
        return max_duration
    
    @staticmethod
    def _calculate_information_ratio(
        returns: pd.Series,
        benchmark_returns: pd.Series,
        trading_days: int = 252
    ) -> float:
        """
        Calculate Information Ratio.
        
        Formula: IR = (Portfolio Return - Benchmark Return) / Tracking Error
        """
        if len(returns) < 2 or len(benchmark_returns) < 2:
            return 0.0
        
        # Align returns
        aligned_returns = returns.align(benchmark_returns, join='inner')
        if len(aligned_returns[0]) < 2:
            return 0.0
        
        excess_returns = aligned_returns[0] - aligned_returns[1]
        tracking_error = excess_returns.std() * np.sqrt(trading_days)
        
        if tracking_error <= 0:
            return 0.0
        
        return (excess_returns.mean() * trading_days) / tracking_error
    
    def _calculate_trade_statistics(self, trades: List[Any]) -> None:
        """
        Calculate trade-level statistics.
        
        Args:
            trades: List of Trade objects
        """
        if not trades:
            return
        
        self.total_trades = len(trades)
        
        # Separate winning and losing trades
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        
        self.winning_trades = len(wins)
        self.losing_trades = len(losses)
        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        
        # Calculate averages
        if wins:
            self.avg_win = sum(t.pnl for t in wins) / len(wins)
            self.max_win = max(t.pnl for t in wins)
        
        if losses:
            self.avg_loss = sum(t.pnl for t in losses) / len(losses)
            self.max_loss = min(t.pnl for t in losses)
        
        self.avg_trade = sum(t.pnl for t in trades) / len(trades)
        
        # Profit factor
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        self.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
        
        # Consecutive wins/losses
        self.max_consecutive_wins, self.max_consecutive_losses = self._calculate_consecutive_trades(trades)
    
    @staticmethod
    def _calculate_consecutive_trades(trades: List[Any]) -> tuple:
        """Calculate maximum consecutive wins and losses."""
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0
        
        for trade in trades:
            if trade.pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif trade.pnl < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
            else:
                # Breakeven trade
                current_wins = 0
                current_losses = 0
        
        return max_wins, max_losses
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_return": self.total_return,
            "cagr": self.cagr,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "avg_drawdown": self.avg_drawdown,
            "max_drawdown_duration": self.max_drawdown_duration,
            "volatility": self.volatility,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "max_win": self.max_win,
            "max_loss": self.max_loss,
            "avg_trade": self.avg_trade,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
        }
    
    def summary(self) -> str:
        """Generate a summary string of key metrics."""
        return (
            f"Performance Summary:\n"
            f"  Total Return: {self.total_return:.2%}\n"
            f"  CAGR: {self.cagr:.2%}\n"
            f"  Sharpe Ratio: {self.sharpe_ratio:.2f}\n"
            f"  Sortino Ratio: {self.sortino_ratio:.2f}\n"
            f"  Max Drawdown: {self.max_drawdown:.2%}\n"
            f"  Calmar Ratio: {self.calmar_ratio:.2f}\n"
            f"  Volatility: {self.volatility:.2%}\n"
            f"  Win Rate: {self.win_rate:.2%}\n"
            f"  Profit Factor: {self.profit_factor:.2f}\n"
            f"  Total Trades: {self.total_trades}\n"
        )


def calculate_rolling_sharpe(
    returns: pd.Series,
    window: int = 252,
    risk_free_rate: float = 0.07
) -> pd.Series:
    """
    Calculate rolling Sharpe ratio.
    
    Args:
        returns: Daily returns series
        window: Rolling window size
        risk_free_rate: Annual risk-free rate
    
    Returns:
        Series of rolling Sharpe ratios
    """
    daily_rf = risk_free_rate / 252
    excess_returns = returns - daily_rf
    
    rolling_mean = excess_returns.rolling(window=window).mean()
    rolling_std = excess_returns.rolling(window=window).std()
    
    rolling_sharpe = (rolling_mean / rolling_std) * np.sqrt(252)
    
    return rolling_sharpe


def calculate_var(
    returns: pd.Series,
    confidence: float = 0.95,
    method: str = "historical"
) -> float:
    """
    Calculate Value at Risk (VaR).
    
    Args:
        returns: Daily returns series
        confidence: Confidence level (e.g., 0.95 for 95% VaR)
        method: 'historical' or 'parametric'
    
    Returns:
        VaR as a positive number (loss amount)
    """
    if len(returns) < 10:
        return 0.0
    
    if method == "historical":
        var = np.percentile(returns, (1 - confidence) * 100)
    else:  # parametric
        mean = returns.mean()
        std = returns.std()
        from scipy.stats import norm
        z_score = norm.ppf(1 - confidence)
        var = mean + z_score * std
    
    return abs(var)


def calculate_cvar(
    returns: pd.Series,
    confidence: float = 0.95
) -> float:
    """
    Calculate Conditional Value at Risk (CVaR / Expected Shortfall).
    
    CVaR is the expected loss given that the loss exceeds VaR.
    
    Args:
        returns: Daily returns series
        confidence: Confidence level
    
    Returns:
        CVaR as a positive number
    """
    if len(returns) < 10:
        return 0.0
    
    var = calculate_var(returns, confidence, method="historical")
    tail_returns = returns[returns <= -var]
    
    if len(tail_returns) == 0:
        return var
    
    return abs(tail_returns.mean())
