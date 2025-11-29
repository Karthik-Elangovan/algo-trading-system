"""
Chart Components Module

Provides chart components for the trading dashboard including:
- Real-time P&L chart
- Drawdown visualization
- Equity curve
- Historical performance graphs
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from ..utils.theme import ThemeManager


def render_pnl_chart(
    pnl_data: pd.DataFrame,
    height: int = 400,
    show_daily: bool = True,
    show_cumulative: bool = True,
) -> None:
    """
    Render a real-time P&L chart with daily and cumulative views.
    
    Args:
        pnl_data: DataFrame with P&L history (columns: date, daily_pnl, cumulative_pnl)
        height: Chart height in pixels
        show_daily: Show daily P&L bars
        show_cumulative: Show cumulative P&L line
    """
    if pnl_data.empty:
        st.info("No P&L data available")
        return
    
    colors = ThemeManager.get_chart_colors()
    template = ThemeManager.get_plotly_template()
    
    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Ensure date column is datetime
    if 'date' in pnl_data.columns:
        dates = pd.to_datetime(pnl_data['date'])
    else:
        dates = pnl_data.index
    
    # Add daily P&L bars
    if show_daily and 'daily_pnl' in pnl_data.columns:
        daily_pnl = pnl_data['daily_pnl']
        bar_colors = [colors["profit"] if v >= 0 else colors["loss"] for v in daily_pnl]
        
        fig.add_trace(
            go.Bar(
                x=dates,
                y=daily_pnl,
                name="Daily P&L",
                marker_color=bar_colors,
                opacity=0.7,
                hovertemplate="Date: %{x}<br>Daily P&L: ₹%{y:,.2f}<extra></extra>"
            ),
            secondary_y=False,
        )
    
    # Add cumulative P&L line
    if show_cumulative and 'cumulative_pnl' in pnl_data.columns:
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=pnl_data['cumulative_pnl'],
                name="Cumulative P&L",
                mode="lines",
                line=dict(color=colors["primary"], width=2),
                hovertemplate="Date: %{x}<br>Cumulative P&L: ₹%{y:,.2f}<extra></extra>"
            ),
            secondary_y=True,
        )
    
    # Update layout
    fig.update_layout(
        template=template,
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode="x unified",
    )
    
    # Update axes
    fig.update_yaxes(title_text="Daily P&L (₹)", secondary_y=False, tickformat=",")
    fig.update_yaxes(title_text="Cumulative P&L (₹)", secondary_y=True, tickformat=",")
    
    # Add range slider
    fig.update_xaxes(
        rangeslider_visible=True,
        rangeselector=dict(
            buttons=list([
                dict(count=7, label="1W", step="day", stepmode="backward"),
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=3, label="3M", step="month", stepmode="backward"),
                dict(step="all", label="All")
            ])
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_drawdown_chart(
    equity_data: pd.DataFrame,
    height: int = 300,
) -> None:
    """
    Render a drawdown visualization chart.
    
    Args:
        equity_data: DataFrame with equity curve (columns: date, equity, drawdown)
        height: Chart height in pixels
    """
    if equity_data.empty:
        st.info("No equity data available")
        return
    
    colors = ThemeManager.get_chart_colors()
    template = ThemeManager.get_plotly_template()
    
    # Ensure date column
    if 'date' in equity_data.columns:
        dates = pd.to_datetime(equity_data['date'])
    else:
        dates = equity_data.index
    
    # Calculate drawdown if not present
    if 'drawdown' not in equity_data.columns:
        equity = equity_data['equity']
        peak = equity.expanding().max()
        drawdown = (equity - peak) / peak
    else:
        drawdown = equity_data['drawdown']
    
    fig = go.Figure()
    
    # Add drawdown area
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=drawdown * 100,  # Convert to percentage
            fill='tozeroy',
            mode='lines',
            name="Drawdown",
            line=dict(color=colors["loss"], width=1),
            fillcolor=f"rgba(255, 82, 82, 0.3)",
            hovertemplate="Date: %{x}<br>Drawdown: %{y:.2f}%<extra></extra>"
        )
    )
    
    # Update layout
    fig.update_layout(
        template=template,
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        yaxis=dict(
            title="Drawdown (%)",
            tickformat=".1f",
            autorange="reversed",  # Negative values at bottom
        ),
        hovermode="x unified",
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_equity_curve(
    equity_data: pd.DataFrame,
    height: int = 350,
    show_benchmark: bool = False,
    benchmark_data: Optional[pd.DataFrame] = None,
) -> None:
    """
    Render an equity curve chart.
    
    Args:
        equity_data: DataFrame with equity curve
        height: Chart height in pixels
        show_benchmark: Whether to show benchmark comparison
        benchmark_data: Optional benchmark data for comparison
    """
    if equity_data.empty:
        st.info("No equity data available")
        return
    
    colors = ThemeManager.get_chart_colors()
    template = ThemeManager.get_plotly_template()
    
    fig = go.Figure()
    
    # Ensure date column
    if 'date' in equity_data.columns:
        dates = pd.to_datetime(equity_data['date'])
    else:
        dates = equity_data.index
    
    # Add equity curve
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=equity_data['equity'],
            name="Portfolio",
            mode="lines",
            line=dict(color=colors["primary"], width=2),
            hovertemplate="Date: %{x}<br>Equity: ₹%{y:,.2f}<extra></extra>"
        )
    )
    
    # Add peak line
    if 'peak' in equity_data.columns:
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=equity_data['peak'],
                name="Peak",
                mode="lines",
                line=dict(color=colors["profit"], width=1, dash="dot"),
                hovertemplate="Date: %{x}<br>Peak: ₹%{y:,.2f}<extra></extra>"
            )
        )
    
    # Add benchmark if provided
    if show_benchmark and benchmark_data is not None:
        fig.add_trace(
            go.Scatter(
                x=benchmark_data.index,
                y=benchmark_data.values,
                name="Benchmark",
                mode="lines",
                line=dict(color="#888888", width=1, dash="dash"),
            )
        )
    
    # Update layout
    fig.update_layout(
        template=template,
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        yaxis=dict(title="Equity (₹)", tickformat=","),
        hovermode="x unified",
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_greeks_chart(
    positions: List[Any],
    height: int = 300,
) -> None:
    """
    Render a chart showing portfolio Greeks exposure.
    
    Args:
        positions: List of position objects with Greek values
        height: Chart height in pixels
    """
    if not positions:
        st.info("No positions to display Greeks")
        return
    
    colors = ThemeManager.get_chart_colors()
    template = ThemeManager.get_plotly_template()
    
    # Aggregate Greeks
    total_delta = sum(p.delta * p.quantity for p in positions)
    total_gamma = sum(p.gamma * p.quantity for p in positions)
    total_theta = sum(p.theta * p.quantity for p in positions)
    total_vega = sum(p.vega * p.quantity for p in positions)
    
    greeks = ["Delta", "Gamma", "Theta", "Vega"]
    values = [total_delta, total_gamma * 100, total_theta, total_vega]  # Scale gamma for visibility
    
    # Create color based on positive/negative
    bar_colors = [colors["profit"] if v >= 0 else colors["loss"] for v in values]
    
    fig = go.Figure(
        data=[
            go.Bar(
                x=greeks,
                y=values,
                marker_color=bar_colors,
                text=[f"{v:,.2f}" for v in values],
                textposition="outside",
                hovertemplate="%{x}: %{y:,.4f}<extra></extra>"
            )
        ]
    )
    
    fig.update_layout(
        template=template,
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        yaxis=dict(title="Exposure"),
        xaxis=dict(title="Greek"),
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_performance_chart(
    metrics: Dict[str, float],
    height: int = 300,
) -> None:
    """
    Render a performance metrics radar chart.
    
    Args:
        metrics: Dictionary of performance metrics
        height: Chart height in pixels
    """
    colors = ThemeManager.get_chart_colors()
    template = ThemeManager.get_plotly_template()
    
    # Define metrics to display (normalized to 0-100 scale)
    metric_names = ["Win Rate", "Profit Factor", "Sharpe", "Recovery", "Consistency"]
    
    # Get or calculate values (demo values)
    values = [
        metrics.get("win_rate", 0.6) * 100,
        min(metrics.get("profit_factor", 1.5) * 20, 100),
        min(max(metrics.get("sharpe_ratio", 1.0) * 25, 0), 100),
        max(100 - metrics.get("max_drawdown", 10), 0),
        metrics.get("consistency", 70),
    ]
    
    fig = go.Figure(
        data=go.Scatterpolar(
            r=values,
            theta=metric_names,
            fill="toself",
            fillcolor=f"rgba(255, 75, 75, 0.3)",
            line=dict(color=colors["primary"], width=2),
            name="Performance"
        )
    )
    
    fig.update_layout(
        template=template,
        height=height,
        margin=dict(l=40, r=40, t=40, b=40),
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
            )
        ),
        showlegend=False,
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_iv_chart(
    iv_data: pd.DataFrame,
    height: int = 300,
) -> None:
    """
    Render an IV and IV Rank chart.
    
    Args:
        iv_data: DataFrame with IV history
        height: Chart height in pixels
    """
    if iv_data.empty:
        st.info("No IV data available")
        return
    
    colors = ThemeManager.get_chart_colors()
    template = ThemeManager.get_plotly_template()
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Add IV line
    if 'iv' in iv_data.columns:
        fig.add_trace(
            go.Scatter(
                x=iv_data.index,
                y=iv_data['iv'] * 100,
                name="IV",
                mode="lines",
                line=dict(color=colors["primary"], width=2),
            ),
            secondary_y=False,
        )
    
    # Add IV Rank
    if 'iv_rank' in iv_data.columns:
        fig.add_trace(
            go.Scatter(
                x=iv_data.index,
                y=iv_data['iv_rank'],
                name="IV Rank",
                mode="lines",
                line=dict(color=colors["profit"], width=2),
            ),
            secondary_y=True,
        )
    
    # Add threshold line for IV Rank
    fig.add_hline(
        y=70,
        line_dash="dash",
        line_color="yellow",
        annotation_text="Entry Threshold",
        secondary_y=True,
    )
    
    fig.update_layout(
        template=template,
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    
    fig.update_yaxes(title_text="IV (%)", secondary_y=False)
    fig.update_yaxes(title_text="IV Rank", range=[0, 100], secondary_y=True)
    
    st.plotly_chart(fig, use_container_width=True)


def render_mini_sparkline(
    data: pd.Series,
    color: str = "#ff4b4b",
    width: int = 100,
    height: int = 30,
) -> str:
    """
    Generate a mini sparkline chart as HTML.
    
    Args:
        data: Series of values
        color: Line color
        width: Chart width in pixels
        height: Chart height in pixels
    
    Returns:
        HTML string for the sparkline
    """
    if data.empty:
        return ""
    
    # Normalize data to fit in the height
    min_val = data.min()
    max_val = data.max()
    range_val = max_val - min_val if max_val != min_val else 1
    
    normalized = ((data - min_val) / range_val * (height - 4) + 2).tolist()
    
    # Create SVG path
    x_step = width / (len(normalized) - 1) if len(normalized) > 1 else width
    points = " ".join([f"{i * x_step},{height - y}" for i, y in enumerate(normalized)])
    
    svg = f'''
    <svg width="{width}" height="{height}">
        <polyline
            fill="none"
            stroke="{color}"
            stroke-width="2"
            points="{points}"
        />
    </svg>
    '''
    
    return svg
