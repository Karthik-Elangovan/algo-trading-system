"""
Streamlit Dashboard for Algorithmic Trading System.

This module provides a web-based dashboard for monitoring and analyzing
trading strategies, positions, and performance metrics.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Algo Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)


def main():
    """Main dashboard application."""
    st.title("📈 Algorithmic Trading Dashboard")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Select Page",
            ["Overview", "Strategies", "Positions", "Performance", "Settings"]
        )
    
    # Main content based on page selection
    if page == "Overview":
        show_overview()
    elif page == "Strategies":
        show_strategies()
    elif page == "Positions":
        show_positions()
    elif page == "Performance":
        show_performance()
    elif page == "Settings":
        show_settings()


def show_overview():
    """Display overview page."""
    st.header("Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Portfolio Value", "₹10,50,000", "+5.0%")
    
    with col2:
        st.metric("Today's P&L", "₹15,000", "+1.5%")
    
    with col3:
        st.metric("Open Positions", "3")
    
    with col4:
        st.metric("Win Rate", "65%", "+2%")
    
    st.markdown("---")
    st.subheader("Recent Activity")
    st.info("Connect to live data source to view recent activity.")


def show_strategies():
    """Display strategies page."""
    st.header("Trading Strategies")
    
    strategies = [
        {"name": "Premium Selling", "status": "Active", "pnl": "+5.2%"},
        {"name": "Iron Condor", "status": "Active", "pnl": "+3.8%"},
        {"name": "Calendar Spread", "status": "Inactive", "pnl": "+1.5%"},
        {"name": "Ratio Spread", "status": "Active", "pnl": "+4.1%"},
    ]
    
    df = pd.DataFrame(strategies)
    st.dataframe(df, use_container_width=True)


def show_positions():
    """Display positions page."""
    st.header("Current Positions")
    st.info("Connect to broker to view live positions.")


def show_performance():
    """Display performance page."""
    st.header("Performance Analytics")
    
    # Create sample data for demonstration
    dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
    values = [1000000 + i * 5000 + (i % 5) * 2000 for i in range(30)]
    
    df = pd.DataFrame({'Date': dates, 'Portfolio Value': values})
    
    fig = px.line(df, x='Date', y='Portfolio Value', title='Portfolio Value Over Time')
    st.plotly_chart(fig, use_container_width=True)


def show_settings():
    """Display settings page."""
    st.header("Settings")
    
    st.subheader("Trading Mode")
    mode = st.radio("Select Mode", ["Paper Trading", "Live Trading"])
    
    st.subheader("Risk Parameters")
    max_risk = st.slider("Max Risk per Trade (%)", 1, 10, 2)
    daily_loss = st.slider("Daily Loss Limit (%)", 1, 20, 5)
    
    if st.button("Save Settings"):
        st.success("Settings saved successfully!")


if __name__ == "__main__":
    main()
