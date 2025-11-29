"""
Table Components Module

Provides table components for the trading dashboard including:
- Position table with Greeks
- Order log
- Trade history
"""

import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from ..utils.theme import ThemeManager


def render_position_table(
    positions: List[Any],
    on_close_position: Optional[Callable] = None,
) -> None:
    """
    Render a table of current open positions with Greek exposures.
    
    Args:
        positions: List of PositionData objects
        on_close_position: Callback function when close button is clicked
    """
    if not positions:
        st.info("📭 No open positions")
        return
    
    colors = ThemeManager.get_colors()
    
    # Convert positions to DataFrame
    data = []
    for pos in positions:
        # Determine P&L color
        pnl = pos.unrealized_pnl if hasattr(pos, 'unrealized_pnl') else pos.get('unrealized_pnl', 0)
        pnl_color = colors["profit_color"] if pnl >= 0 else colors["loss_color"]
        
        # Format expiry
        expiry = pos.expiry if hasattr(pos, 'expiry') else pos.get('expiry')
        if expiry:
            days_to_expiry = (expiry - datetime.now()).days
            expiry_str = f"{expiry.strftime('%d %b')} ({days_to_expiry}d)"
        else:
            expiry_str = "N/A"
        
        data.append({
            "Symbol": pos.symbol if hasattr(pos, 'symbol') else pos.get('symbol', ''),
            "Type": pos.position_type if hasattr(pos, 'position_type') else pos.get('position_type', ''),
            "Qty": pos.quantity if hasattr(pos, 'quantity') else pos.get('quantity', 0),
            "Entry": f"₹{pos.entry_price:,.2f}" if hasattr(pos, 'entry_price') else f"₹{pos.get('entry_price', 0):,.2f}",
            "Current": f"₹{pos.current_price:,.2f}" if hasattr(pos, 'current_price') else f"₹{pos.get('current_price', 0):,.2f}",
            "P&L": pnl,
            "Δ": pos.delta if hasattr(pos, 'delta') else pos.get('delta', 0),
            "Γ": pos.gamma if hasattr(pos, 'gamma') else pos.get('gamma', 0),
            "Θ": pos.theta if hasattr(pos, 'theta') else pos.get('theta', 0),
            "V": pos.vega if hasattr(pos, 'vega') else pos.get('vega', 0),
            "Expiry": expiry_str,
        })
    
    df = pd.DataFrame(data)
    
    # Format columns
    def format_pnl(val):
        color = colors["profit_color"] if val >= 0 else colors["loss_color"]
        return f'<span style="color: {color}; font-weight: bold;">₹{val:,.2f}</span>'
    
    # Create styled table
    st.markdown("### 📊 Open Positions")
    
    # Display summary metrics
    total_pnl = sum(d["P&L"] for d in data)
    total_delta = sum(d["Δ"] for d in data)
    total_theta = sum(d["Θ"] for d in data)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Positions", len(positions))
    with col2:
        st.metric("Total P&L", f"₹{total_pnl:,.2f}", delta=f"{'↑' if total_pnl >= 0 else '↓'}")
    with col3:
        st.metric("Net Delta", f"{total_delta:,.4f}")
    with col4:
        st.metric("Daily Theta", f"₹{total_theta:,.2f}")
    
    # Display the table with custom styling
    st.dataframe(
        df.style.format({
            "P&L": "₹{:,.2f}",
            "Δ": "{:.4f}",
            "Γ": "{:.6f}",
            "Θ": "{:.2f}",
            "V": "{:.2f}",
        }).applymap(
            lambda x: f"color: {colors['profit_color']}" if isinstance(x, (int, float)) and x > 0 else (
                f"color: {colors['loss_color']}" if isinstance(x, (int, float)) and x < 0 else ""
            ),
            subset=["P&L"]
        ),
        use_container_width=True,
        hide_index=True,
    )
    
    # Close position buttons
    if on_close_position:
        st.markdown("#### Quick Close")
        cols = st.columns(min(len(positions), 4))
        for i, pos in enumerate(positions):
            with cols[i % 4]:
                symbol = pos.symbol if hasattr(pos, 'symbol') else pos.get('symbol', '')
                if st.button(f"Close {symbol[:20]}...", key=f"close_{symbol}", use_container_width=True):
                    on_close_position(symbol)


def render_order_log(
    orders: List[Dict[str, Any]],
    max_rows: int = 50,
    show_filters: bool = True,
) -> None:
    """
    Render an order log table with filtering capabilities.
    
    Args:
        orders: List of order dictionaries
        max_rows: Maximum number of rows to display
        show_filters: Whether to show filter controls
    """
    if not orders:
        st.info("📭 No orders in history")
        return
    
    colors = ThemeManager.get_colors()
    
    st.markdown("### 📜 Order Log")
    
    # Filters
    if show_filters:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_filter = st.selectbox(
                "Status",
                ["All", "Filled", "Pending", "Cancelled"],
                key="order_status_filter"
            )
        
        with col2:
            side_filter = st.selectbox(
                "Side",
                ["All", "BUY", "SELL"],
                key="order_side_filter"
            )
        
        with col3:
            days_filter = st.selectbox(
                "Period",
                ["All Time", "Today", "Last 7 Days", "Last 30 Days"],
                key="order_period_filter"
            )
        
        # Apply filters
        filtered_orders = orders.copy()
        
        if status_filter != "All":
            filtered_orders = [o for o in filtered_orders if o.get("status") == status_filter]
        
        if side_filter != "All":
            filtered_orders = [o for o in filtered_orders if o.get("side") == side_filter]
        
        if days_filter == "Today":
            today = datetime.now().date()
            filtered_orders = [o for o in filtered_orders 
                             if o.get("timestamp", datetime.now()).date() == today]
        elif days_filter == "Last 7 Days":
            cutoff = datetime.now().replace(hour=0, minute=0, second=0) - pd.Timedelta(days=7)
            filtered_orders = [o for o in filtered_orders 
                             if o.get("timestamp", datetime.now()) >= cutoff]
        elif days_filter == "Last 30 Days":
            cutoff = datetime.now().replace(hour=0, minute=0, second=0) - pd.Timedelta(days=30)
            filtered_orders = [o for o in filtered_orders 
                             if o.get("timestamp", datetime.now()) >= cutoff]
    else:
        filtered_orders = orders
    
    # Limit rows
    filtered_orders = filtered_orders[:max_rows]
    
    if not filtered_orders:
        st.info("No orders match the selected filters")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame([{
        "Order ID": o.get("order_id", ""),
        "Time": o.get("timestamp", "").strftime("%Y-%m-%d %H:%M") if isinstance(o.get("timestamp"), datetime) else str(o.get("timestamp", "")),
        "Symbol": o.get("symbol", ""),
        "Side": o.get("side", ""),
        "Qty": o.get("quantity", 0),
        "Type": o.get("order_type", ""),
        "Price": o.get("price", 0),
        "Status": o.get("status", ""),
    } for o in filtered_orders])
    
    # Style based on side and status
    def style_side(val):
        if val == "BUY":
            return f"color: {colors['profit_color']}; font-weight: bold;"
        elif val == "SELL":
            return f"color: {colors['loss_color']}; font-weight: bold;"
        return ""
    
    def style_status(val):
        if val == "Filled":
            return f"color: {colors['profit_color']};"
        elif val == "Cancelled":
            return f"color: {colors['loss_color']};"
        elif val == "Pending":
            return f"color: {colors['warning']};"
        return ""
    
    # Display table
    st.dataframe(
        df.style.format({
            "Price": "₹{:,.2f}",
        }).applymap(style_side, subset=["Side"]).applymap(style_status, subset=["Status"]),
        use_container_width=True,
        hide_index=True,
        height=min(len(filtered_orders) * 35 + 38, 400),
    )
    
    # Summary
    filled_orders = [o for o in filtered_orders if o.get("status") == "Filled"]
    buy_orders = [o for o in filled_orders if o.get("side") == "BUY"]
    sell_orders = [o for o in filled_orders if o.get("side") == "SELL"]
    
    st.caption(
        f"Showing {len(filtered_orders)} of {len(orders)} orders | "
        f"Filled: {len(filled_orders)} | Buys: {len(buy_orders)} | Sells: {len(sell_orders)}"
    )


def render_trade_history(
    trades: List[Dict[str, Any]],
    max_rows: int = 30,
) -> None:
    """
    Render a trade history table with P&L breakdown.
    
    Args:
        trades: List of completed trade dictionaries
        max_rows: Maximum number of rows to display
    """
    if not trades:
        st.info("📭 No completed trades")
        return
    
    colors = ThemeManager.get_colors()
    
    st.markdown("### 📈 Trade History")
    
    # Limit rows
    trades = trades[:max_rows]
    
    # Convert to DataFrame
    df = pd.DataFrame([{
        "Exit Date": t.get("exit_date", "").strftime("%Y-%m-%d") if isinstance(t.get("exit_date"), datetime) else str(t.get("exit_date", "")),
        "Symbol": t.get("symbol", ""),
        "Direction": t.get("direction", ""),
        "Entry": t.get("entry_price", 0),
        "Exit": t.get("exit_price", 0),
        "P&L": t.get("pnl", 0),
        "Return": t.get("return_pct", 0),
        "Days": t.get("holding_period", 0),
        "Exit Reason": t.get("exit_reason", ""),
    } for t in trades])
    
    # Display table with styling
    st.dataframe(
        df.style.format({
            "Entry": "₹{:,.2f}",
            "Exit": "₹{:,.2f}",
            "P&L": "₹{:,.2f}",
            "Return": "{:.2%}",
        }).applymap(
            lambda x: f"color: {colors['profit_color']}; font-weight: bold;" if isinstance(x, (int, float)) and x > 0 else (
                f"color: {colors['loss_color']}; font-weight: bold;" if isinstance(x, (int, float)) and x < 0 else ""
            ),
            subset=["P&L", "Return"]
        ),
        use_container_width=True,
        hide_index=True,
    )
    
    # Trade statistics
    if trades:
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
        avg_winner = sum(t.get("pnl", 0) for t in winning_trades) / len(winning_trades) if winning_trades else 0
        losing_trades = [t for t in trades if t.get("pnl", 0) < 0]
        avg_loser = sum(t.get("pnl", 0) for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total P&L", f"₹{total_pnl:,.2f}")
        with col2:
            st.metric("Win Rate", f"{win_rate:.1f}%")
        with col3:
            st.metric("Avg Winner", f"₹{avg_winner:,.2f}")
        with col4:
            st.metric("Avg Loser", f"₹{avg_loser:,.2f}")


def render_greeks_table(positions: List[Any]) -> None:
    """
    Render a table focused on Greek exposures.
    
    Args:
        positions: List of position objects
    """
    if not positions:
        st.info("No positions for Greeks analysis")
        return
    
    st.markdown("### 🔢 Greeks Breakdown")
    
    data = []
    for pos in positions:
        qty = pos.quantity if hasattr(pos, 'quantity') else pos.get('quantity', 0)
        data.append({
            "Position": pos.symbol if hasattr(pos, 'symbol') else pos.get('symbol', ''),
            "Delta": pos.delta if hasattr(pos, 'delta') else pos.get('delta', 0),
            "Gamma": pos.gamma if hasattr(pos, 'gamma') else pos.get('gamma', 0),
            "Theta": pos.theta if hasattr(pos, 'theta') else pos.get('theta', 0),
            "Vega": pos.vega if hasattr(pos, 'vega') else pos.get('vega', 0),
            "Position Delta": (pos.delta if hasattr(pos, 'delta') else pos.get('delta', 0)) * qty,
            "Position Theta": (pos.theta if hasattr(pos, 'theta') else pos.get('theta', 0)) * qty,
        })
    
    # Add totals row
    total_row = {
        "Position": "**TOTAL**",
        "Delta": sum(d["Delta"] for d in data),
        "Gamma": sum(d["Gamma"] for d in data),
        "Theta": sum(d["Theta"] for d in data),
        "Vega": sum(d["Vega"] for d in data),
        "Position Delta": sum(d["Position Delta"] for d in data),
        "Position Theta": sum(d["Position Theta"] for d in data),
    }
    data.append(total_row)
    
    df = pd.DataFrame(data)
    
    st.dataframe(
        df.style.format({
            "Delta": "{:.4f}",
            "Gamma": "{:.6f}",
            "Theta": "{:.2f}",
            "Vega": "{:.2f}",
            "Position Delta": "{:.4f}",
            "Position Theta": "₹{:.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )
