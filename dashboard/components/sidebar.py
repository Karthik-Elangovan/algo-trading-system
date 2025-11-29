"""
Sidebar Components Module

Provides sidebar UI components for the trading dashboard including:
- Strategy selector and configuration
- Theme toggle
- Export controls
- Quick actions
"""

import streamlit as st
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from ..utils.theme import ThemeManager, get_custom_css
from ..utils.export import ExportManager


def render_sidebar(
    data_handler: Any,
    on_strategy_change: Optional[Callable] = None,
    on_export: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Render the complete sidebar with all controls.
    
    Args:
        data_handler: DashboardDataHandler instance
        on_strategy_change: Callback for strategy changes
        on_export: Callback for export actions
    
    Returns:
        Dictionary containing sidebar selections and actions
    """
    sidebar_state = {
        "selected_strategy": None,
        "strategy_params": {},
        "export_action": None,
        "theme": ThemeManager.get_current_theme(),
    }
    
    st.sidebar.title("📊 Trading Dashboard")
    st.sidebar.markdown("---")
    
    # Theme toggle
    sidebar_state["theme"] = render_theme_toggle()
    
    st.sidebar.markdown("---")
    
    # Strategy selector
    strategy_selection = render_strategy_selector(data_handler)
    sidebar_state["selected_strategy"] = strategy_selection["selected"]
    sidebar_state["strategy_params"] = strategy_selection["params"]
    
    st.sidebar.markdown("---")
    
    # Strategy controls
    render_strategy_controls(strategy_selection["selected"])
    
    st.sidebar.markdown("---")
    
    # Export controls
    sidebar_state["export_action"] = render_export_controls(data_handler)
    
    st.sidebar.markdown("---")
    
    # Quick actions
    render_quick_actions()
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<small>Last updated: {datetime.now().strftime('%H:%M:%S')}</small>",
        unsafe_allow_html=True
    )
    
    return sidebar_state


def render_theme_toggle() -> str:
    """
    Render the theme toggle control.
    
    Returns:
        Current theme name
    """
    st.sidebar.subheader("🎨 Theme")
    
    current_theme = ThemeManager.get_current_theme()
    theme_label = "🌙 Dark" if current_theme == "dark" else "☀️ Light"
    
    col1, col2 = st.sidebar.columns([2, 1])
    with col1:
        st.markdown(f"Current: **{theme_label}**")
    with col2:
        if st.button("Toggle", key="theme_toggle", use_container_width=True):
            ThemeManager.toggle_theme()
            st.rerun()
    
    return ThemeManager.get_current_theme()


def render_strategy_selector(data_handler: Any) -> Dict[str, Any]:
    """
    Render the strategy selector dropdown and parameter inputs.
    
    Args:
        data_handler: DashboardDataHandler instance
    
    Returns:
        Dictionary with selected strategy and parameters
    """
    st.sidebar.subheader("📈 Strategy")
    
    strategies = data_handler.get_strategies()
    strategy_names = [s["name"] for s in strategies]
    
    selected_idx = st.sidebar.selectbox(
        "Select Strategy",
        range(len(strategy_names)),
        format_func=lambda x: strategy_names[x],
        key="strategy_selector"
    )
    
    selected_strategy = strategies[selected_idx]
    
    # Display strategy description
    st.sidebar.markdown(f"*{selected_strategy['description']}*")
    
    # Status indicator
    status = selected_strategy.get("status", "inactive")
    status_color = "🟢" if status == "active" else "🔴"
    st.sidebar.markdown(f"Status: {status_color} {status.title()}")
    
    # Strategy parameters
    params = {}
    with st.sidebar.expander("⚙️ Parameters", expanded=False):
        for param_name, param_value in selected_strategy["parameters"].items():
            if isinstance(param_value, bool):
                params[param_name] = st.checkbox(
                    param_name.replace("_", " ").title(),
                    value=param_value,
                    key=f"param_{param_name}"
                )
            elif isinstance(param_value, int):
                params[param_name] = st.number_input(
                    param_name.replace("_", " ").title(),
                    value=param_value,
                    step=1,
                    key=f"param_{param_name}"
                )
            elif isinstance(param_value, float):
                params[param_name] = st.number_input(
                    param_name.replace("_", " ").title(),
                    value=param_value,
                    step=0.01,
                    format="%.2f",
                    key=f"param_{param_name}"
                )
            elif isinstance(param_value, tuple):
                st.markdown(f"**{param_name.replace('_', ' ').title()}**")
                params[param_name] = (
                    st.number_input(f"Min", value=param_value[0], step=0.01, key=f"param_{param_name}_min"),
                    st.number_input(f"Max", value=param_value[1], step=0.01, key=f"param_{param_name}_max"),
                )
            else:
                params[param_name] = param_value
    
    return {
        "selected": selected_strategy,
        "params": params,
    }


def render_strategy_controls(strategy: Dict[str, Any]) -> None:
    """
    Render strategy control buttons (Start/Stop/Pause).
    
    Args:
        strategy: Selected strategy dictionary
    """
    st.sidebar.subheader("🎮 Controls")
    
    status = strategy.get("status", "inactive")
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if status == "inactive":
            if st.button("▶️ Start", key="start_strategy", use_container_width=True):
                st.session_state["strategy_status"] = "active"
                st.success("Strategy started!")
        else:
            if st.button("⏸️ Pause", key="pause_strategy", use_container_width=True):
                st.session_state["strategy_status"] = "paused"
                st.info("Strategy paused")
    
    with col2:
        if st.button("⏹️ Stop", key="stop_strategy", use_container_width=True):
            st.session_state["strategy_status"] = "inactive"
            st.warning("Strategy stopped")
    
    # Additional controls
    with st.sidebar.expander("🔧 Advanced", expanded=False):
        st.checkbox("Auto-trade", value=False, key="auto_trade")
        st.checkbox("Paper trading", value=True, key="paper_trading")
        st.slider("Risk level", 1, 10, 5, key="risk_level")


def render_export_controls(data_handler: Any) -> Optional[str]:
    """
    Render export functionality controls.
    
    Args:
        data_handler: DashboardDataHandler instance
    
    Returns:
        Export action taken or None
    """
    st.sidebar.subheader("📥 Export")
    
    export_action = None
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("📊 Positions", key="export_positions", use_container_width=True):
            positions = data_handler.get_positions()
            csv_data = ExportManager.export_positions_csv(positions)
            st.sidebar.download_button(
                label="⬇️ Download CSV",
                data=csv_data,
                file_name=f"positions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_positions"
            )
            export_action = "positions"
    
    with col2:
        if st.button("📜 Orders", key="export_orders", use_container_width=True):
            orders = data_handler.get_order_history()
            csv_data = ExportManager.export_orders_csv(orders)
            st.sidebar.download_button(
                label="⬇️ Download CSV",
                data=csv_data,
                file_name=f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_orders"
            )
            export_action = "orders"
    
    # P&L Export
    if st.sidebar.button("💰 P&L Statement", key="export_pnl", use_container_width=True):
        pnl_data = data_handler.get_pnl_history()
        csv_data = ExportManager.export_pnl_csv(pnl_data)
        st.sidebar.download_button(
            label="⬇️ Download P&L CSV",
            data=csv_data,
            file_name=f"pnl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            key="download_pnl"
        )
        export_action = "pnl"
    
    # Full Report
    if st.sidebar.button("📋 Full Report", key="export_report", use_container_width=True):
        pnl_data = data_handler.get_pnl_history()
        positions = data_handler.get_positions()
        risk_metrics = data_handler.get_risk_metrics()
        
        report = ExportManager.generate_pnl_report(
            pnl_data, positions, risk_metrics
        )
        
        st.sidebar.download_button(
            label="⬇️ Download Report",
            data=report.encode('utf-8'),
            file_name=f"trading_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            key="download_report"
        )
        export_action = "report"
    
    return export_action


def render_quick_actions() -> None:
    """Render quick action buttons."""
    st.sidebar.subheader("⚡ Quick Actions")
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("🔄 Refresh", key="sidebar_refresh_data", use_container_width=True):
            st.rerun()
    
    with col2:
        if st.button("🗑️ Clear Alerts", key="sidebar_clear_alerts", use_container_width=True):
            if "alerts" in st.session_state:
                st.session_state.alerts = []
            st.success("Alerts cleared")


def render_underlying_selector(data_handler: Any) -> str:
    """
    Render the underlying asset selector.
    
    Args:
        data_handler: DashboardDataHandler instance
    
    Returns:
        Selected underlying name
    """
    underlyings = data_handler.get_available_underlyings()
    
    selected = st.sidebar.selectbox(
        "Underlying",
        underlyings,
        key="underlying_selector"
    )
    
    return selected


def render_date_range_selector() -> tuple:
    """
    Render date range selector for historical data.
    
    Returns:
        Tuple of (start_date, end_date)
    """
    st.sidebar.subheader("📅 Date Range")
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Start",
            value=datetime.now().replace(day=1),
            key="start_date"
        )
    
    with col2:
        end_date = st.date_input(
            "End",
            value=datetime.now(),
            key="end_date"
        )
    
    return start_date, end_date
