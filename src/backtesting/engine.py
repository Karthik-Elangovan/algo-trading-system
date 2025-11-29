"""
Backtesting Engine Module

Event-driven backtesting framework for options trading strategies.

Features:
- Realistic simulation with slippage and transaction costs
- Support for Indian market transaction fees (STT, GST, stamp duty)
- Walk-forward analysis capability
- Detailed trade logging
- Equity curve tracking
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
import logging
from copy import deepcopy

from ..strategies.base_strategy import BaseStrategy, Signal, SignalType, Trade
from .metrics import PerformanceMetrics
from .report import PerformanceReport

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """
    Configuration for backtesting.
    
    Attributes:
        initial_capital: Starting capital
        slippage_pct: Slippage as percentage of price
        brokerage_per_order: Flat brokerage fee per order
        stt_rate: Securities Transaction Tax rate
        gst_rate: GST rate on brokerage
        stamp_duty_rate: Stamp duty rate
        exchange_charges_rate: Exchange transaction charges
        sebi_charges_rate: SEBI regulatory charges
        risk_free_rate: Risk-free rate for ratio calculations
        default_bid_ask_spread_pct: Default bid-ask spread
    """
    initial_capital: float = 1_000_000
    slippage_pct: float = 0.005
    brokerage_per_order: float = 20
    stt_rate: float = 0.0005
    gst_rate: float = 0.18
    stamp_duty_rate: float = 0.00003
    exchange_charges_rate: float = 0.00053
    sebi_charges_rate: float = 0.0000005
    risk_free_rate: float = 0.07
    default_bid_ask_spread_pct: float = 0.01


@dataclass
class BacktestState:
    """
    Internal state during backtesting.
    
    Attributes:
        capital: Current available capital
        equity: Current total equity (capital + unrealized PnL)
        positions: Dictionary of open positions
        trades: List of completed trades
        equity_curve: List of equity values over time
        daily_returns: List of daily returns
    """
    capital: float
    equity: float
    positions: Dict[str, Any] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)
    daily_pnl: List[float] = field(default_factory=list)


@dataclass
class BacktestResult:
    """
    Results from a backtest run.
    
    Attributes:
        strategy_name: Name of the strategy
        start_date: Backtest start date
        end_date: Backtest end date
        initial_capital: Starting capital
        final_capital: Ending capital
        total_return: Total return percentage
        trades: List of all trades
        equity_curve: DataFrame with equity over time
        metrics: PerformanceMetrics object
        config: BacktestConfig used
    """
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return: float
    trades: List[Trade]
    equity_curve: pd.DataFrame
    metrics: PerformanceMetrics
    config: BacktestConfig
    
    @property
    def sharpe_ratio(self) -> float:
        """Get Sharpe ratio from metrics."""
        return self.metrics.sharpe_ratio
    
    @property
    def max_drawdown(self) -> float:
        """Get maximum drawdown from metrics."""
        return self.metrics.max_drawdown
    
    @property
    def win_rate(self) -> float:
        """Get win rate from metrics."""
        return self.metrics.win_rate
    
    def generate_report(self) -> str:
        """Generate a text report of the backtest results."""
        report = PerformanceReport(self)
        return report.generate_text_report()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary."""
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_return": self.total_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "total_trades": len(self.trades),
        }


class BacktestEngine:
    """
    Event-driven backtesting engine for trading strategies.
    
    Simulates strategy execution with realistic market conditions including:
    - Slippage modeling
    - Transaction costs (brokerage, taxes, fees)
    - Position management
    - Equity curve tracking
    
    Usage:
        engine = BacktestEngine(initial_capital=1000000)
        results = engine.run(strategy, data)
        print(results.generate_report())
    """
    
    def __init__(
        self,
        initial_capital: float = 1_000_000,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the BacktestEngine.
        
        Args:
            initial_capital: Starting capital for backtesting
            config: Configuration dictionary (overrides defaults)
        """
        config_dict = config or {}
        config_dict["initial_capital"] = initial_capital
        
        self.config = BacktestConfig(**{
            k: v for k, v in config_dict.items() 
            if k in BacktestConfig.__dataclass_fields__
        })
        
        self.state: Optional[BacktestState] = None
        self._strategy: Optional[BaseStrategy] = None
    
    def run(
        self,
        strategy: BaseStrategy,
        data: pd.DataFrame,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> BacktestResult:
        """
        Run backtest for a strategy on given data.
        
        Args:
            strategy: Strategy instance to backtest
            data: DataFrame with historical options data
            start_date: Optional start date filter
            end_date: Optional end date filter
        
        Returns:
            BacktestResult with all metrics and trades
        """
        # Validate data
        if data.empty:
            raise ValueError("Data cannot be empty")
        
        # Filter data by date range
        data = self._filter_data_by_date(data, start_date, end_date)
        
        # Initialize state
        self.state = BacktestState(
            capital=self.config.initial_capital,
            equity=self.config.initial_capital
        )
        self._strategy = deepcopy(strategy)
        self._strategy.reset()
        
        # Initialize strategy
        self._strategy.initialize(data)
        
        # Get trading days
        trading_days = sorted(pd.to_datetime(data["date"]).unique())
        
        logger.info(
            f"Starting backtest: {strategy.name}, "
            f"Period: {trading_days[0]} to {trading_days[-1]}, "
            f"Capital: {self.config.initial_capital:,.0f}"
        )
        
        # Main backtest loop
        for timestamp in trading_days:
            self._process_day(data, timestamp)
        
        # Close any remaining positions at end
        self._close_all_positions(data, trading_days[-1])
        
        # Calculate final metrics
        result = self._generate_result(strategy.name, trading_days[0], trading_days[-1])
        
        logger.info(
            f"Backtest complete: Return={result.total_return:.2%}, "
            f"Sharpe={result.sharpe_ratio:.2f}, "
            f"MaxDD={result.max_drawdown:.2%}, "
            f"Trades={len(result.trades)}"
        )
        
        return result
    
    def _filter_data_by_date(
        self,
        data: pd.DataFrame,
        start_date: Optional[str],
        end_date: Optional[str]
    ) -> pd.DataFrame:
        """Filter data by date range."""
        data = data.copy()
        data["date"] = pd.to_datetime(data["date"])
        
        if start_date:
            data = data[data["date"] >= pd.to_datetime(start_date)]
        if end_date:
            data = data[data["date"] <= pd.to_datetime(end_date)]
        
        return data
    
    def _process_day(self, data: pd.DataFrame, timestamp: datetime) -> None:
        """
        Process a single trading day.
        
        Args:
            data: Full dataset
            timestamp: Current day timestamp
        """
        # Get data up to current day
        historical_data = data[data["date"] <= timestamp]
        current_data = data[data["date"] == timestamp]
        
        if current_data.empty:
            return
        
        # Update positions with current prices
        self._update_positions(current_data, timestamp)
        
        # Generate and process signals
        signal = self._strategy.on_bar(historical_data, timestamp, self.state.capital)
        
        if signal:
            self._process_signal(signal, current_data, timestamp)
        
        # Record equity
        self._record_equity(timestamp)
    
    def _update_positions(
        self,
        current_data: pd.DataFrame,
        timestamp: datetime
    ) -> None:
        """Update all positions with current prices."""
        # For strangle positions in the strategy
        if hasattr(self._strategy, "strangle_positions"):
            for pos_id, strangle in self._strategy.strangle_positions.items():
                # Get current prices for the strangle legs
                call_data = current_data[
                    (current_data["strike"] == strangle.call_strike) &
                    (current_data["option_type"] == "CE") &
                    (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(strangle.expiry))
                ]
                put_data = current_data[
                    (current_data["strike"] == strangle.put_strike) &
                    (current_data["option_type"] == "PE") &
                    (pd.to_datetime(current_data["expiry"]) == pd.to_datetime(strangle.expiry))
                ]
                
                if not call_data.empty:
                    strangle.call_current_price = call_data["ltp"].iloc[0]
                if not put_data.empty:
                    strangle.put_current_price = put_data["ltp"].iloc[0]
    
    def _process_signal(
        self,
        signal: Signal,
        current_data: pd.DataFrame,
        timestamp: datetime
    ) -> None:
        """
        Process a trading signal.
        
        Args:
            signal: Signal to process
            current_data: Current day's data
            timestamp: Current timestamp
        """
        if signal.signal_type == SignalType.ENTRY_SHORT:
            self._process_entry_signal(signal, current_data, timestamp)
        elif signal.signal_type in [SignalType.EXIT_SHORT, SignalType.EXIT_LONG]:
            self._process_exit_signal(signal, current_data, timestamp)
    
    def _process_entry_signal(
        self,
        signal: Signal,
        current_data: pd.DataFrame,
        timestamp: datetime
    ) -> None:
        """Process an entry signal."""
        if signal.metadata.get("strategy") == "short_strangle":
            self._enter_strangle(signal, current_data, timestamp)
    
    def _enter_strangle(
        self,
        signal: Signal,
        current_data: pd.DataFrame,
        timestamp: datetime
    ) -> None:
        """Enter a short strangle position."""
        metadata = signal.metadata
        
        # Calculate position size
        quantity = self._strategy.calculate_position_size(
            self.state.capital,
            metadata["total_premium"],
            signal
        )
        
        if quantity <= 0:
            logger.debug("Position size zero, skipping entry")
            return
        
        # Apply slippage to entry
        call_premium = metadata["call_premium"] * (1 - self.config.slippage_pct)
        put_premium = metadata["put_premium"] * (1 - self.config.slippage_pct)
        total_premium = call_premium + put_premium
        
        # Calculate transaction costs
        lot_size = self._strategy.config.get("lot_sizes", {}).get(metadata["underlying"], 50)
        transaction_cost = self._calculate_transaction_cost(
            total_premium * lot_size * quantity,
            is_sell=True  # Selling options
        )
        
        # Update signal metadata with adjusted premiums
        signal.metadata["call_premium"] = call_premium
        signal.metadata["put_premium"] = put_premium
        signal.metadata["total_premium"] = total_premium
        
        # Open position in strategy
        self._strategy.open_strangle(signal, quantity)
        
        # Update capital (receive premium, pay transaction costs)
        premium_received = total_premium * lot_size * quantity
        self.state.capital += premium_received - transaction_cost
        
        logger.debug(
            f"Entered strangle: Premium={premium_received:.2f}, "
            f"Cost={transaction_cost:.2f}, Qty={quantity}"
        )
    
    def _process_exit_signal(
        self,
        signal: Signal,
        current_data: pd.DataFrame,
        timestamp: datetime
    ) -> None:
        """Process an exit signal."""
        pos_id = signal.symbol
        
        if hasattr(self._strategy, "strangle_positions") and pos_id in self._strategy.strangle_positions:
            self._exit_strangle(pos_id, signal, timestamp)
    
    def _exit_strangle(
        self,
        pos_id: str,
        signal: Signal,
        timestamp: datetime
    ) -> None:
        """Exit a short strangle position."""
        strangle = self._strategy.strangle_positions[pos_id]
        
        # Apply slippage to exit (buying back, so price goes up)
        call_exit = strangle.call_current_price * (1 + self.config.slippage_pct)
        put_exit = strangle.put_current_price * (1 + self.config.slippage_pct)
        
        strangle.call_current_price = call_exit
        strangle.put_current_price = put_exit
        
        # Calculate transaction costs
        lot_size = self._strategy.config.get("lot_sizes", {}).get(strangle.underlying, 50)
        exit_cost = (call_exit + put_exit) * lot_size * strangle.quantity
        transaction_cost = self._calculate_transaction_cost(exit_cost, is_sell=False)
        
        # Close position in strategy (this adds to trades)
        trade = self._strategy.close_strangle(pos_id, signal)
        
        # Update capital (pay to close, pay transaction costs)
        self.state.capital -= exit_cost + transaction_cost
        
        # Add trade to state
        self.state.trades.append(trade)
        
        logger.debug(
            f"Exited strangle: ExitCost={exit_cost:.2f}, "
            f"TransactionCost={transaction_cost:.2f}, PnL={trade.pnl:.2f}"
        )
    
    def _calculate_transaction_cost(
        self,
        value: float,
        is_sell: bool = True
    ) -> float:
        """
        Calculate total transaction costs for Indian markets.
        
        Components:
        - Brokerage (flat fee per order)
        - STT (Securities Transaction Tax) - only on sell for options
        - Exchange charges
        - GST on brokerage
        - SEBI charges
        - Stamp duty
        
        Args:
            value: Transaction value
            is_sell: Whether this is a sell transaction
        
        Returns:
            Total transaction cost
        """
        # Brokerage (2 legs for strangle)
        brokerage = self.config.brokerage_per_order * 2
        
        # STT only on sell side for options
        stt = value * self.config.stt_rate if is_sell else 0
        
        # Exchange charges
        exchange_charges = value * self.config.exchange_charges_rate
        
        # GST on brokerage and exchange charges
        gst = (brokerage + exchange_charges) * self.config.gst_rate
        
        # SEBI charges
        sebi_charges = value * self.config.sebi_charges_rate
        
        # Stamp duty
        stamp_duty = value * self.config.stamp_duty_rate if not is_sell else 0
        
        total = brokerage + stt + exchange_charges + gst + sebi_charges + stamp_duty
        
        return total
    
    def _close_all_positions(
        self,
        data: pd.DataFrame,
        timestamp: datetime
    ) -> None:
        """Close all remaining positions at end of backtest."""
        if hasattr(self._strategy, "strangle_positions"):
            for pos_id in list(self._strategy.strangle_positions.keys()):
                exit_signal = Signal(
                    signal_type=SignalType.EXIT_SHORT,
                    symbol=pos_id,
                    timestamp=timestamp,
                    reason="End of backtest"
                )
                self._exit_strangle(pos_id, exit_signal, timestamp)
    
    def _record_equity(self, timestamp: datetime) -> None:
        """Record current equity value."""
        # Calculate unrealized PnL from open positions
        unrealized_pnl = 0.0
        
        if hasattr(self._strategy, "strangle_positions"):
            lot_sizes = self._strategy.config.get("lot_sizes", {})
            for strangle in self._strategy.strangle_positions.values():
                lot_size = lot_sizes.get(strangle.underlying, 50)
                pnl = strangle.get_unrealized_pnl() * lot_size
                unrealized_pnl += pnl
        
        current_equity = self.state.capital + unrealized_pnl
        
        # Calculate daily return
        if self.state.equity_curve:
            prev_equity = self.state.equity_curve[-1]["equity"]
            daily_return = (current_equity - prev_equity) / prev_equity if prev_equity > 0 else 0
            daily_pnl = current_equity - prev_equity
        else:
            daily_return = 0.0
            daily_pnl = 0.0
        
        self.state.equity = current_equity
        self.state.equity_curve.append({
            "date": timestamp,
            "equity": current_equity,
            "capital": self.state.capital,
            "unrealized_pnl": unrealized_pnl,
            "daily_return": daily_return,
        })
        self.state.daily_returns.append(daily_return)
        self.state.daily_pnl.append(daily_pnl)
    
    def _generate_result(
        self,
        strategy_name: str,
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResult:
        """Generate backtest result with metrics."""
        # Create equity curve DataFrame
        equity_df = pd.DataFrame(self.state.equity_curve)
        
        # Calculate metrics
        returns = pd.Series(self.state.daily_returns)
        
        metrics = PerformanceMetrics.from_returns(
            returns=returns,
            equity_curve=equity_df["equity"] if not equity_df.empty else pd.Series([self.config.initial_capital]),
            trades=self.state.trades,
            risk_free_rate=self.config.risk_free_rate
        )
        
        # Calculate total return
        final_equity = self.state.equity if self.state.equity else self.config.initial_capital
        total_return = (final_equity - self.config.initial_capital) / self.config.initial_capital
        
        return BacktestResult(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.config.initial_capital,
            final_capital=final_equity,
            total_return=total_return,
            trades=self.state.trades,
            equity_curve=equity_df,
            metrics=metrics,
            config=self.config
        )
    
    def run_walk_forward(
        self,
        strategy: BaseStrategy,
        data: pd.DataFrame,
        train_period_days: int = 252,
        test_period_days: int = 63,
        step_days: int = 21,
        optimization_func: Optional[Callable] = None
    ) -> List[BacktestResult]:
        """
        Run walk-forward analysis.
        
        Walk-forward divides data into rolling train/test periods,
        allowing out-of-sample validation of strategy performance.
        
        Args:
            strategy: Strategy instance to test
            data: Full historical dataset
            train_period_days: Days in training period (default 1 year)
            test_period_days: Days in testing period (default 3 months)
            step_days: Days to step forward (default 1 month)
            optimization_func: Optional function to optimize strategy parameters
        
        Returns:
            List of BacktestResult for each test period
        """
        results = []
        
        trading_days = sorted(pd.to_datetime(data["date"]).unique())
        
        total_days = len(trading_days)
        min_required = train_period_days + test_period_days
        
        if total_days < min_required:
            logger.warning(
                f"Insufficient data for walk-forward: {total_days} days < {min_required} required"
            )
            return results
        
        current_start = 0
        
        while current_start + min_required <= total_days:
            train_end = current_start + train_period_days
            test_start = train_end
            test_end = min(test_start + test_period_days, total_days)
            
            train_start_date = trading_days[current_start]
            train_end_date = trading_days[train_end - 1]
            test_start_date = trading_days[test_start]
            test_end_date = trading_days[test_end - 1]
            
            logger.info(
                f"Walk-forward period: Train {train_start_date} to {train_end_date}, "
                f"Test {test_start_date} to {test_end_date}"
            )
            
            # Optionally optimize on training data
            if optimization_func:
                strategy = optimization_func(
                    strategy,
                    data,
                    str(train_start_date),
                    str(train_end_date)
                )
            
            # Run backtest on test period
            result = self.run(
                strategy,
                data,
                start_date=str(test_start_date),
                end_date=str(test_end_date)
            )
            
            results.append(result)
            
            # Step forward
            current_start += step_days
        
        return results
