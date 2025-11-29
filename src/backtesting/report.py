"""
Performance Report Module

Generates comprehensive reports for backtesting results.

Report Formats:
- Text report (console output)
- JSON format (for API/storage)
- Trade-by-trade analysis
- Monthly/yearly breakdown
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime
import json
import logging

if TYPE_CHECKING:
    from .engine import BacktestResult

# Configure logging
logger = logging.getLogger(__name__)


class PerformanceReport:
    """
    Generate performance reports from backtest results.
    
    Provides multiple report formats:
    - Text summary for console output
    - JSON for programmatic access
    - Detailed trade analysis
    - Time-based breakdowns
    """
    
    def __init__(self, result: "BacktestResult"):
        """
        Initialize report generator.
        
        Args:
            result: BacktestResult from backtesting engine
        """
        self.result = result
        self.metrics = result.metrics
    
    def generate_text_report(self) -> str:
        """
        Generate a comprehensive text report.
        
        Returns:
            Formatted text report string
        """
        lines = []
        
        # Header
        lines.append("=" * 70)
        lines.append(f"BACKTEST PERFORMANCE REPORT - {self.result.strategy_name}")
        lines.append("=" * 70)
        lines.append("")
        
        # Summary Section
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Period: {self._format_date(self.result.start_date)} to {self._format_date(self.result.end_date)}")
        lines.append(f"Initial Capital: ₹{self.result.initial_capital:,.2f}")
        lines.append(f"Final Capital: ₹{self.result.final_capital:,.2f}")
        lines.append(f"Total Return: {self.result.total_return:.2%}")
        lines.append(f"CAGR: {self.metrics.cagr:.2%}")
        lines.append("")
        
        # Risk Metrics
        lines.append("RISK METRICS")
        lines.append("-" * 40)
        lines.append(f"Sharpe Ratio: {self.metrics.sharpe_ratio:.2f}")
        lines.append(f"Sortino Ratio: {self.metrics.sortino_ratio:.2f}")
        lines.append(f"Calmar Ratio: {self.metrics.calmar_ratio:.2f}")
        lines.append(f"Volatility (Ann.): {self.metrics.volatility:.2%}")
        lines.append(f"Max Drawdown: {self.metrics.max_drawdown:.2%}")
        lines.append(f"Avg Drawdown: {self.metrics.avg_drawdown:.2%}")
        lines.append(f"Max DD Duration: {self.metrics.max_drawdown_duration} days")
        lines.append("")
        
        # Trade Statistics
        lines.append("TRADE STATISTICS")
        lines.append("-" * 40)
        lines.append(f"Total Trades: {self.metrics.total_trades}")
        lines.append(f"Winning Trades: {self.metrics.winning_trades}")
        lines.append(f"Losing Trades: {self.metrics.losing_trades}")
        lines.append(f"Win Rate: {self.metrics.win_rate:.2%}")
        lines.append(f"Profit Factor: {self.metrics.profit_factor:.2f}")
        lines.append(f"Average Win: ₹{self.metrics.avg_win:,.2f}")
        lines.append(f"Average Loss: ₹{self.metrics.avg_loss:,.2f}")
        lines.append(f"Max Win: ₹{self.metrics.max_win:,.2f}")
        lines.append(f"Max Loss: ₹{self.metrics.max_loss:,.2f}")
        lines.append(f"Average Trade: ₹{self.metrics.avg_trade:,.2f}")
        lines.append(f"Max Consecutive Wins: {self.metrics.max_consecutive_wins}")
        lines.append(f"Max Consecutive Losses: {self.metrics.max_consecutive_losses}")
        lines.append("")
        
        # Monthly Returns Table
        if not self.metrics.monthly_returns.empty:
            lines.append("MONTHLY RETURNS")
            lines.append("-" * 40)
            monthly_table = self._generate_monthly_table()
            lines.append(monthly_table)
            lines.append("")
        
        # Transaction Costs
        lines.append("TRANSACTION COSTS")
        lines.append("-" * 40)
        lines.append(f"Slippage: {self.result.config.slippage_pct:.2%}")
        lines.append(f"Brokerage per Order: ₹{self.result.config.brokerage_per_order:.2f}")
        lines.append(f"STT Rate: {self.result.config.stt_rate:.4%}")
        lines.append("")
        
        # Footer
        lines.append("=" * 70)
        lines.append(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> str:
        """
        Generate report in JSON format.
        
        Returns:
            JSON string with report data
        """
        report_data = {
            "strategy_name": self.result.strategy_name,
            "period": {
                "start_date": self._format_date(self.result.start_date),
                "end_date": self._format_date(self.result.end_date),
            },
            "capital": {
                "initial": self.result.initial_capital,
                "final": self.result.final_capital,
                "total_return": self.result.total_return,
            },
            "metrics": self.metrics.to_dict(),
            "configuration": {
                "slippage_pct": self.result.config.slippage_pct,
                "brokerage_per_order": self.result.config.brokerage_per_order,
                "stt_rate": self.result.config.stt_rate,
            },
            "trades_summary": {
                "total": len(self.result.trades),
                "by_exit_reason": self._group_trades_by_exit_reason(),
            },
            "generated_at": datetime.now().isoformat(),
        }
        
        return json.dumps(report_data, indent=2, default=str)
    
    def generate_trade_list(self, limit: Optional[int] = None) -> str:
        """
        Generate trade-by-trade analysis.
        
        Args:
            limit: Maximum number of trades to include
        
        Returns:
            Formatted trade list string
        """
        lines = []
        lines.append("TRADE-BY-TRADE ANALYSIS")
        lines.append("=" * 100)
        
        # Header
        headers = ["#", "Entry Date", "Exit Date", "Direction", "P&L", "Return %", "Days", "Exit Reason"]
        header_line = f"{headers[0]:<5}{headers[1]:<15}{headers[2]:<15}{headers[3]:<10}{headers[4]:<15}{headers[5]:<12}{headers[6]:<8}{headers[7]}"
        lines.append(header_line)
        lines.append("-" * 100)
        
        trades = self.result.trades[:limit] if limit else self.result.trades
        
        for i, trade in enumerate(trades, 1):
            entry_date = self._format_date(trade.entry_date) if trade.entry_date else "N/A"
            exit_date = self._format_date(trade.exit_date) if trade.exit_date else "N/A"
            
            line = (
                f"{i:<5}"
                f"{entry_date:<15}"
                f"{exit_date:<15}"
                f"{trade.direction:<10}"
                f"₹{trade.pnl:>12,.2f}"
                f"{trade.return_pct:>10.2%}"
                f"{trade.holding_period:>6}"
                f"  {trade.exit_reason}"
            )
            lines.append(line)
        
        lines.append("-" * 100)
        lines.append(f"Total: {len(self.result.trades)} trades")
        
        return "\n".join(lines)
    
    def get_equity_curve_data(self) -> pd.DataFrame:
        """
        Get equity curve data for plotting.
        
        Returns:
            DataFrame with date and equity columns
        """
        return self.result.equity_curve.copy()
    
    def get_monthly_returns_table(self) -> pd.DataFrame:
        """
        Get monthly returns in a year/month matrix format.
        
        Returns:
            DataFrame with years as rows, months as columns
        """
        if self.result.equity_curve.empty:
            return pd.DataFrame()
        
        equity = self.result.equity_curve.copy()
        
        if "date" in equity.columns:
            equity["date"] = pd.to_datetime(equity["date"])
            equity = equity.set_index("date")
        
        if "equity" not in equity.columns:
            return pd.DataFrame()
        
        # Resample to monthly
        monthly = equity["equity"].resample("ME").last()
        monthly_returns = monthly.pct_change()
        
        # Create year/month matrix
        monthly_df = pd.DataFrame({
            "year": monthly_returns.index.year,
            "month": monthly_returns.index.month,
            "return": monthly_returns.values
        })
        
        pivot = monthly_df.pivot(index="year", columns="month", values="return")
        pivot.columns = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        
        # Add yearly total
        pivot["Total"] = pivot.sum(axis=1)
        
        return pivot
    
    def get_yearly_returns(self) -> Dict[int, float]:
        """
        Get returns by year.
        
        Returns:
            Dictionary mapping year to return
        """
        if self.result.equity_curve.empty:
            return {}
        
        equity = self.result.equity_curve.copy()
        
        if "date" in equity.columns:
            equity["date"] = pd.to_datetime(equity["date"])
            equity = equity.set_index("date")
        
        if "equity" not in equity.columns:
            return {}
        
        # Resample to yearly
        yearly = equity["equity"].resample("YE").last()
        yearly_returns = yearly.pct_change().dropna()
        
        return {date.year: ret for date, ret in yearly_returns.items()}
    
    def _generate_monthly_table(self) -> str:
        """Generate ASCII table of monthly returns."""
        pivot = self.get_monthly_returns_table()
        
        if pivot.empty:
            return "No monthly data available"
        
        lines = []
        
        # Header
        header = "Year  " + "  ".join([f"{m:>6}" for m in pivot.columns])
        lines.append(header)
        lines.append("-" * len(header))
        
        # Data rows
        for year, row in pivot.iterrows():
            values = []
            for val in row:
                if pd.isna(val):
                    values.append(f"{'---':>6}")
                else:
                    values.append(f"{val:>6.1%}")
            line = f"{year}  " + "  ".join(values)
            lines.append(line)
        
        return "\n".join(lines)
    
    def _group_trades_by_exit_reason(self) -> Dict[str, int]:
        """Group trades by exit reason."""
        reasons = {}
        for trade in self.result.trades:
            reason = trade.exit_reason or "Unknown"
            reasons[reason] = reasons.get(reason, 0) + 1
        return reasons
    
    @staticmethod
    def _format_date(date: Optional[datetime]) -> str:
        """Format date for display."""
        if date is None:
            return "N/A"
        if isinstance(date, str):
            return date
        return date.strftime("%Y-%m-%d")


class ReportExporter:
    """
    Export reports to various formats.
    """
    
    @staticmethod
    def to_csv(result: "BacktestResult", filepath: str) -> None:
        """
        Export trades to CSV file.
        
        Args:
            result: BacktestResult object
            filepath: Output file path
        """
        trades_data = []
        for trade in result.trades:
            trades_data.append({
                "entry_date": trade.entry_date,
                "exit_date": trade.exit_date,
                "symbol": trade.symbol,
                "direction": trade.direction,
                "quantity": trade.quantity,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "pnl": trade.pnl,
                "return_pct": trade.return_pct,
                "holding_period": trade.holding_period,
                "exit_reason": trade.exit_reason,
            })
        
        df = pd.DataFrame(trades_data)
        df.to_csv(filepath, index=False)
        logger.info(f"Trades exported to {filepath}")
    
    @staticmethod
    def equity_curve_to_csv(result: "BacktestResult", filepath: str) -> None:
        """
        Export equity curve to CSV file.
        
        Args:
            result: BacktestResult object
            filepath: Output file path
        """
        result.equity_curve.to_csv(filepath, index=False)
        logger.info(f"Equity curve exported to {filepath}")


def generate_comparison_report(
    results: List["BacktestResult"],
    names: Optional[List[str]] = None
) -> str:
    """
    Generate comparison report for multiple backtest results.
    
    Args:
        results: List of BacktestResult objects
        names: Optional list of names for each result
    
    Returns:
        Formatted comparison table
    """
    if not results:
        return "No results to compare"
    
    if names is None:
        names = [r.strategy_name for r in results]
    
    lines = []
    lines.append("STRATEGY COMPARISON")
    lines.append("=" * 80)
    
    # Header
    header = f"{'Metric':<25}" + "".join([f"{n:<15}" for n in names])
    lines.append(header)
    lines.append("-" * 80)
    
    # Metrics to compare
    metrics_list = [
        ("Total Return", lambda r: f"{r.total_return:.2%}"),
        ("CAGR", lambda r: f"{r.metrics.cagr:.2%}"),
        ("Sharpe Ratio", lambda r: f"{r.metrics.sharpe_ratio:.2f}"),
        ("Sortino Ratio", lambda r: f"{r.metrics.sortino_ratio:.2f}"),
        ("Max Drawdown", lambda r: f"{r.metrics.max_drawdown:.2%}"),
        ("Calmar Ratio", lambda r: f"{r.metrics.calmar_ratio:.2f}"),
        ("Volatility", lambda r: f"{r.metrics.volatility:.2%}"),
        ("Win Rate", lambda r: f"{r.metrics.win_rate:.2%}"),
        ("Profit Factor", lambda r: f"{r.metrics.profit_factor:.2f}"),
        ("Total Trades", lambda r: f"{r.metrics.total_trades}"),
        ("Avg Trade", lambda r: f"₹{r.metrics.avg_trade:,.0f}"),
    ]
    
    for metric_name, metric_func in metrics_list:
        values = [metric_func(r) for r in results]
        line = f"{metric_name:<25}" + "".join([f"{v:<15}" for v in values])
        lines.append(line)
    
    lines.append("=" * 80)
    
    return "\n".join(lines)
