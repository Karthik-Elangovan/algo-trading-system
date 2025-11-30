"""
Algo Trading Dashboard - Main Application

A professional trading dashboard for the algo-trading-system built with Streamlit.
Provides real-time monitoring, risk metrics, and trade management capabilities.

Features:
- Real-time P&L tracking and visualization
- Position monitoring with Greeks exposure
- Risk metrics dashboard (VaR, margin, drawdown)
- Order entry and management
- Alert system for strategy signals and risk warnings
- Dark/Light theme support
- Export functionality (CSV, reports)

Usage:
    streamlit run dashboard/app.py

Author: Algo Trading System
Version: 1.0.0
"""

import streamlit as st
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import dashboard modules
from dashboard.utils.data_handler import DashboardDataHandler
from dashboard.utils.theme import ThemeManager, get_custom_css
from dashboard.utils.export import ExportManager
from dashboard.components.sidebar import render_sidebar
from dashboard.components.charts import (
    render_pnl_chart,
    render_drawdown_chart,
    render_equity_curve,
    render_greeks_chart,
)
from dashboard.components.tables import (
    render_position_table,
    render_order_log,
)
from dashboard.components.metrics import (
    render_risk_metrics,
    render_market_data,
    render_order_entry,
    render_capital_metrics,
    format_compact_number,
)
from dashboard.components.alerts import (
    AlertManager,
    AlertType,
    AlertCategory,
    render_alerts,
    generate_sample_alerts,
)

# Page configuration
st.set_page_config(
    page_title="Algo Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/algo-trading-system",
        "Report a bug": "https://github.com/algo-trading-system/issues",
        "About": "Algo Trading Dashboard v1.0.0 - Professional options trading platform",
    }
)

# Initialize session state
def init_session_state():
    """Initialize session state variables."""
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        st.session_state.data_handler = DashboardDataHandler(initial_capital=1_000_000)
        st.session_state.alert_manager = AlertManager()
        st.session_state.selected_underlying = "NIFTY"
        st.session_state.auto_refresh = True
        st.session_state.refresh_interval = 30
        
        # Generate sample alerts for demo
        generate_sample_alerts(st.session_state.alert_manager)


def load_css():
    """Load custom CSS styles."""
    css = get_custom_css()
    st.markdown(css, unsafe_allow_html=True)
    
    # Load external CSS file
    css_file = Path(__file__).parent / "styles" / "custom.css"
    if css_file.exists():
        with open(css_file) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def main():
    """Main application entry point."""
    # Initialize
    init_session_state()
    load_css()
    
    # Get data handler and alert manager from session state
    data_handler = st.session_state.data_handler
    alert_manager = st.session_state.alert_manager
    
    # Render sidebar
    sidebar_state = render_sidebar(data_handler)
    
    # Main content area
    st.title("📈 Algo Trading Dashboard")
    
    # Auto-refresh toggle in header
    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
    
    with col1:
        st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    with col2:
        auto_refresh = st.checkbox(
            "Auto-refresh",
            value=st.session_state.auto_refresh,
            key="auto_refresh_toggle",
            label_visibility="collapsed"
        )
        st.session_state.auto_refresh = auto_refresh
    
    with col3:
        underlying = st.selectbox(
            "Underlying",
            data_handler.get_available_underlyings(),
            key="main_underlying_select",
            label_visibility="collapsed"
        )
        st.session_state.selected_underlying = underlying
    
    with col4:
        if st.button("🔄 Refresh", key="manual_refresh"):
            st.rerun()
    
    # Auto-refresh using streamlit-autorefresh
    if st.session_state.auto_refresh:
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=st.session_state.refresh_interval * 1000, key="datarefresh")
        except ImportError:
            st.warning("Auto-refresh requires streamlit-autorefresh package")
    
    st.markdown("---")
    
    # Market data section
    market_data = data_handler.get_market_data(st.session_state.selected_underlying)
    
    # Top row - Key metrics and market data
    col1, col2 = st.columns([2, 3])
    
    with col1:
        render_market_data(market_data, st.session_state.selected_underlying)
    
    with col2:
        risk_metrics = data_handler.get_risk_metrics()
        render_capital_metrics(
            initial_capital=data_handler.initial_capital,
            current_capital=data_handler.current_capital,
            margin_used=risk_metrics.margin_used,
        )
    
    st.markdown("---")
    
    # Main content tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "P&L",
        "Positions",
        "Risk",
        "Orders",
        "Alerts"
    ])
    
    with tab1:
        render_pnl_tab(data_handler)
    
    with tab2:
        render_positions_tab(data_handler)
    
    with tab3:
        render_risk_tab(data_handler)
    
    with tab4:
        render_order_tab(data_handler)
    
    with tab5:
        render_alerts_tab(alert_manager)
    
    st.markdown("---")
    
    # Bottom section - Order Log
    st.markdown("### 📜 Recent Orders")
    orders = data_handler.get_order_history()
    render_order_log(orders, max_rows=10, show_filters=False)
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #888; font-size: 0.75rem;'>"
        "⚠️ This dashboard is for EDUCATIONAL purposes only. "
        "Always paper trade first. Trading involves significant risk of loss. "
        "</div>",
        unsafe_allow_html=True
    )


def render_pnl_tab(data_handler):
    """Render P&L and charts tab."""
    st.markdown("### 💰 Profit & Loss")
    
    # P&L Chart
    pnl_data = data_handler.get_pnl_history()
    render_pnl_chart(pnl_data, height=400)
    
    # Two columns for additional charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📉 Drawdown")
        equity_data = data_handler.get_equity_curve()
        render_drawdown_chart(equity_data, height=250)
    
    with col2:
        st.markdown("### 📈 Equity Curve")
        render_equity_curve(equity_data, height=250)


def render_positions_tab(data_handler):
    """Render positions tab."""
    positions = data_handler.get_positions()
    
    # Position callback for closing
    def on_close_position(symbol):
        result = data_handler.close_position(symbol)
        if result:
            st.session_state.alert_manager.add_order_alert(
                f"Position closed: {symbol}",
                AlertType.SUCCESS
            )
            st.rerun()
    
    render_position_table(positions, on_close_position=on_close_position)
    
    st.markdown("---")
    
    # Greeks visualization
    st.markdown("### 📐 Greeks Exposure")
    col1, col2 = st.columns(2)
    
    with col1:
        render_greeks_chart(positions, height=250)
    
    with col2:
        # Greeks summary
        if positions:
            total_delta = sum(p.delta * p.quantity for p in positions)
            total_gamma = sum(p.gamma * p.quantity for p in positions)
            total_theta = sum(p.theta * p.quantity for p in positions)
            total_vega = sum(p.vega * p.quantity for p in positions)
            
            st.markdown("#### Net Greeks")
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Delta", f"{total_delta:,.4f}")
                st.metric("Gamma", f"{total_gamma:,.6f}")
            with col_b:
                st.metric("Theta/day", format_compact_number(total_theta))
                st.metric("Vega", f"{total_vega:,.2f}")


def render_risk_tab(data_handler):
    """Render risk metrics tab."""
    risk_metrics = data_handler.get_risk_metrics()
    render_risk_metrics(risk_metrics)
    
    st.markdown("---")
    
    # Risk limits section
    st.markdown("### 🚦 Risk Limits")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Positions**")
        positions = data_handler.get_positions()
        max_positions = 5
        st.progress(len(positions) / max_positions)
        st.caption(f"{len(positions)}/{max_positions}")
    
    with col2:
        st.markdown("**Daily Loss**")
        daily_limit = 50000
        daily_loss = max(0, -risk_metrics.daily_pnl)
        st.progress(min(daily_loss / daily_limit, 1.0))
        loss_str = format_compact_number(daily_loss, decimals=0)
        limit_str = format_compact_number(daily_limit, decimals=0)
        st.caption(f"{loss_str}/{limit_str}")
    
    with col3:
        st.markdown("**Margin**")
        margin_limit = 100
        st.progress(risk_metrics.margin_used / margin_limit)
        st.caption(f"{risk_metrics.margin_used:.0f}%/{margin_limit}%")
    
    # Risk warnings
    st.markdown("---")
    st.markdown("### ⚠️ Risk Warnings")
    
    warnings = []
    
    if risk_metrics.margin_used > 80:
        warnings.append(("🔴", "High margin utilization - consider reducing positions"))
    elif risk_metrics.margin_used > 60:
        warnings.append(("🟡", "Moderate margin utilization - monitor closely"))
    
    if risk_metrics.drawdown > 10:
        warnings.append(("🔴", f"Significant drawdown of {risk_metrics.drawdown:.1f}% - review risk management"))
    elif risk_metrics.drawdown > 5:
        warnings.append(("🟡", f"Drawdown of {risk_metrics.drawdown:.1f}% - monitor positions"))
    
    if abs(risk_metrics.delta_exposure) > 1:
        warnings.append(("🟡", f"High delta exposure ({risk_metrics.delta_exposure:.2f}) - consider hedging"))
    
    if not warnings:
        st.success("✅ All risk metrics within acceptable limits")
    else:
        for icon, message in warnings:
            st.warning(f"{icon} {message}")


def render_order_tab(data_handler):
    """Render order entry tab."""
    col1, col2 = st.columns([2, 1])
    
    with col1:
        def on_order_submit(order):
            st.session_state.alert_manager.add_order_alert(
                f"Order submitted: {order.get('side', '')} {order.get('symbol', '')} @ ₹{order.get('price', 0):.2f}",
                AlertType.SUCCESS
            )
        
        render_order_entry(data_handler, on_order_submit=on_order_submit)
    
    with col2:
        st.markdown("### 📊 Quick Stats")
        
        # Strategy status
        strategy = data_handler.get_strategies()[0]
        status = strategy.get("status", "inactive")
        status_icon = "🟢" if status == "active" else "🔴"
        
        st.markdown(f"**Strategy Status:** {status_icon} {status.title()}")
        st.markdown(f"**IV Rank Threshold:** {strategy['parameters'].get('iv_rank_threshold', 70)}")
        
        market_data = data_handler.get_market_data(st.session_state.selected_underlying)
        current_iv_rank = market_data.iv_rank
        
        if current_iv_rank >= strategy['parameters'].get('iv_rank_threshold', 70):
            st.success(f"✅ Entry conditions met (IV Rank: {current_iv_rank:.0f})")
        else:
            st.info(f"ℹ️ IV Rank ({current_iv_rank:.0f}) below threshold")
        
        # Position summary
        positions = data_handler.get_positions()
        total_pnl = sum(p.unrealized_pnl for p in positions)
        
        st.markdown("---")
        st.markdown("### 📋 Position Summary")
        st.metric("Open Positions", len(positions))
        st.metric("Unrealized P&L", f"₹{total_pnl:,.2f}")


def render_alerts_tab(alert_manager):
    """Render alerts tab."""
    render_alerts(alert_manager, max_display=20, show_filters=True)
    
    st.markdown("---")
    
    # Manual alert creation
    st.markdown("### ➕ Add Custom Alert")
    
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        alert_message = st.text_input("Alert message", key="custom_alert_message")
    
    with col2:
        alert_type = st.selectbox(
            "Type",
            ["Info", "Success", "Warning", "Danger"],
            key="custom_alert_type"
        )
    
    with col3:
        if st.button("Add Alert", key="add_custom_alert"):
            if alert_message:
                type_map = {
                    "Info": AlertType.INFO,
                    "Success": AlertType.SUCCESS,
                    "Warning": AlertType.WARNING,
                    "Danger": AlertType.DANGER,
                }
                alert_manager.add_alert(
                    message=alert_message,
                    alert_type=type_map[alert_type],
                    category=AlertCategory.SYSTEM,
                )
                st.success("Alert added!")
                st.rerun()
            else:
                st.error("Please enter a message")


if __name__ == "__main__":
    main()
