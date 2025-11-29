"""
Dashboard Components Package

Contains reusable UI components for the trading dashboard:
- sidebar: Strategy controls, theme toggle, export functionality
- charts: P&L charts, drawdown visualization
- tables: Position tables, order log
- metrics: Risk metrics, market data display
- alerts: Alert system and notifications
"""

from .sidebar import render_sidebar
from .charts import render_pnl_chart, render_drawdown_chart
from .tables import render_position_table, render_order_log
from .metrics import render_risk_metrics, render_market_data
from .alerts import render_alerts, AlertManager

__all__ = [
    "render_sidebar",
    "render_pnl_chart",
    "render_drawdown_chart",
    "render_position_table",
    "render_order_log",
    "render_risk_metrics",
    "render_market_data",
    "render_alerts",
    "AlertManager",
]
