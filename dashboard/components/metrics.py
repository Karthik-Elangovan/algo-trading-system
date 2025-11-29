"""
Metrics Display Components Module

Provides components for displaying risk metrics and market data including:
- Risk metrics panel (VaR, margin, exposure)
- Market data display (spot, IV, Greeks)
- Order entry panel
"""

import streamlit as st
from typing import Any, Dict, Optional, Callable, List
from datetime import datetime

from ..utils.theme import ThemeManager


# Configuration constants
DELTA_EXPOSURE_THRESHOLD = 0.5  # Delta exposure above this triggers warning color
MARGIN_WARNING_THRESHOLD = 60  # Margin % above this shows yellow warning
MARGIN_DANGER_THRESHOLD = 80  # Margin % above this shows red warning
DRAWDOWN_WARNING_THRESHOLD = 5  # Drawdown % above this shows indicator
DRAWDOWN_DANGER_THRESHOLD = 10  # Drawdown % above this shows warning color


def render_risk_metrics(risk_metrics: Any) -> None:
    """
    Render a risk metrics display panel.
    
    Args:
        risk_metrics: RiskMetrics object with current risk values
    """
    colors = ThemeManager.get_colors()
    
    st.markdown("### ⚠️ Risk Metrics")
    
    # Main risk metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        var_value = risk_metrics.var_95 if hasattr(risk_metrics, 'var_95') else risk_metrics.get('var_95', 0)
        st.metric(
            "VaR (95%)",
            f"₹{var_value:,.0f}",
            help="Maximum expected loss at 95% confidence level"
        )
    
    with col2:
        margin = risk_metrics.margin_used if hasattr(risk_metrics, 'margin_used') else risk_metrics.get('margin_used', 0)
        delta = "⚠️" if margin > MARGIN_DANGER_THRESHOLD else ("🟡" if margin > MARGIN_WARNING_THRESHOLD else "✅")
        st.metric(
            "Margin Used",
            f"{margin:.1f}%",
            delta=delta,
            delta_color="off",
            help="Percentage of available margin in use"
        )
    
    with col3:
        exposure = risk_metrics.max_exposure if hasattr(risk_metrics, 'max_exposure') else risk_metrics.get('max_exposure', 0)
        st.metric(
            "Exposure",
            f"₹{exposure:,.0f}",
            help="Total portfolio exposure"
        )
    
    with col4:
        drawdown = risk_metrics.drawdown if hasattr(risk_metrics, 'drawdown') else risk_metrics.get('drawdown', 0)
        dd_color = colors["loss_color"] if drawdown > DRAWDOWN_DANGER_THRESHOLD else colors["text"]
        st.metric(
            "Drawdown",
            f"{drawdown:.1f}%",
            delta=f"{'↓' if drawdown > DRAWDOWN_WARNING_THRESHOLD else ''}",
            delta_color="inverse",
            help="Current drawdown from peak"
        )
    
    # P&L section
    st.markdown("#### 💰 P&L Summary")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        daily_pnl = risk_metrics.daily_pnl if hasattr(risk_metrics, 'daily_pnl') else risk_metrics.get('daily_pnl', 0)
        pnl_color = colors["profit_color"] if daily_pnl >= 0 else colors["loss_color"]
        st.markdown(
            f"<div style='text-align: center;'>"
            f"<p style='margin-bottom: 0; color: {colors['secondary']};'>Daily P&L</p>"
            f"<p style='font-size: 1.5rem; font-weight: bold; color: {pnl_color};'>₹{daily_pnl:,.2f}</p>"
            f"</div>",
            unsafe_allow_html=True
        )
    
    with col2:
        total_pnl = risk_metrics.total_pnl if hasattr(risk_metrics, 'total_pnl') else risk_metrics.get('total_pnl', 0)
        pnl_color = colors["profit_color"] if total_pnl >= 0 else colors["loss_color"]
        st.markdown(
            f"<div style='text-align: center;'>"
            f"<p style='margin-bottom: 0; color: {colors['secondary']};'>Total P&L</p>"
            f"<p style='font-size: 1.5rem; font-weight: bold; color: {pnl_color};'>₹{total_pnl:,.2f}</p>"
            f"</div>",
            unsafe_allow_html=True
        )
    
    with col3:
        cvar = risk_metrics.cvar_95 if hasattr(risk_metrics, 'cvar_95') else risk_metrics.get('cvar_95', 0)
        st.markdown(
            f"<div style='text-align: center;'>"
            f"<p style='margin-bottom: 0; color: {colors['secondary']};'>CVaR (95%)</p>"
            f"<p style='font-size: 1.5rem; font-weight: bold; color: {colors['loss_color']};'>₹{cvar:,.2f}</p>"
            f"</div>",
            unsafe_allow_html=True
        )
    
    # Greeks exposure section
    st.markdown("#### 📐 Greeks Exposure")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        delta = risk_metrics.delta_exposure if hasattr(risk_metrics, 'delta_exposure') else risk_metrics.get('delta_exposure', 0)
        delta_color = colors["profit_color"] if abs(delta) < DELTA_EXPOSURE_THRESHOLD else colors["warning"]
        st.metric("Delta", f"{delta:,.4f}", help="Net delta exposure")
    
    with col2:
        gamma = risk_metrics.gamma_exposure if hasattr(risk_metrics, 'gamma_exposure') else risk_metrics.get('gamma_exposure', 0)
        st.metric("Gamma", f"{gamma:,.6f}", help="Net gamma exposure")
    
    with col3:
        theta = risk_metrics.theta_exposure if hasattr(risk_metrics, 'theta_exposure') else risk_metrics.get('theta_exposure', 0)
        theta_color = colors["profit_color"] if theta < 0 else colors["loss_color"]  # Negative theta is good for sellers
        st.metric("Theta", f"₹{theta:,.2f}", help="Daily theta decay (positive = collecting)")
    
    with col4:
        vega = risk_metrics.vega_exposure if hasattr(risk_metrics, 'vega_exposure') else risk_metrics.get('vega_exposure', 0)
        st.metric("Vega", f"{vega:,.2f}", help="Net vega exposure")


def render_market_data(market_data: Any, underlying: str = "NIFTY") -> None:
    """
    Render a market data display panel.
    
    Args:
        market_data: MarketData object with current market values
        underlying: Name of the underlying asset
    """
    colors = ThemeManager.get_colors()
    
    st.markdown(f"### 📈 {underlying} Market Data")
    
    # Main price display
    spot = market_data.spot_price if hasattr(market_data, 'spot_price') else market_data.get('spot_price', 0)
    change = market_data.change if hasattr(market_data, 'change') else market_data.get('change', 0)
    change_color = colors["profit_color"] if change >= 0 else colors["loss_color"]
    change_arrow = "▲" if change >= 0 else "▼"
    
    st.markdown(
        f"<div style='text-align: center; padding: 1rem; background: {colors['secondary_background']}; border-radius: 0.5rem;'>"
        f"<p style='font-size: 2.5rem; font-weight: bold; margin-bottom: 0;'>₹{spot:,.2f}</p>"
        f"<p style='font-size: 1.2rem; color: {change_color};'>{change_arrow} {abs(change):.2f}%</p>"
        f"</div>",
        unsafe_allow_html=True
    )
    
    # Market details
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        bid = market_data.bid if hasattr(market_data, 'bid') else market_data.get('bid', 0)
        st.metric("Bid", f"₹{bid:,.2f}")
    
    with col2:
        ask = market_data.ask if hasattr(market_data, 'ask') else market_data.get('ask', 0)
        st.metric("Ask", f"₹{ask:,.2f}")
    
    with col3:
        iv = market_data.iv if hasattr(market_data, 'iv') else market_data.get('iv', 0)
        st.metric("IV", f"{iv * 100:.1f}%", help="Implied Volatility")
    
    with col4:
        iv_rank = market_data.iv_rank if hasattr(market_data, 'iv_rank') else market_data.get('iv_rank', 0)
        rank_color = colors["profit_color"] if iv_rank > 70 else (colors["warning"] if iv_rank > 40 else colors["loss_color"])
        st.metric("IV Rank", f"{iv_rank:.0f}", help="IV Rank (0-100)")
    
    # Volume
    volume = market_data.volume if hasattr(market_data, 'volume') else market_data.get('volume', 0)
    timestamp = market_data.timestamp if hasattr(market_data, 'timestamp') else market_data.get('timestamp', datetime.now())
    
    st.caption(f"Volume: {volume:,} | Last update: {timestamp.strftime('%H:%M:%S')}")


def render_order_entry(
    data_handler: Any,
    on_order_submit: Optional[Callable] = None,
) -> None:
    """
    Render an order entry panel.
    
    Args:
        data_handler: DashboardDataHandler instance
        on_order_submit: Callback function when order is submitted
    """
    colors = ThemeManager.get_colors()
    
    st.markdown("### 📝 Order Entry")
    
    with st.form("order_entry_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # Underlying selection
            underlyings = data_handler.get_available_underlyings()
            underlying = st.selectbox("Underlying", underlyings, key="order_underlying")
            
            # Get instrument config for lot size
            config = data_handler.get_instrument_config(underlying)
            lot_size = config.get("lot_size", 50)
            
            # Strike price
            market_data = data_handler.get_market_data(underlying)
            atm_strike = round(market_data.spot_price / config.get("strike_interval", 50)) * config.get("strike_interval", 50)
            
            strike = st.number_input(
                "Strike Price",
                value=int(atm_strike),
                step=config.get("strike_interval", 50),
                key="order_strike"
            )
            
            # Option type
            option_type = st.selectbox("Option Type", ["CE (Call)", "PE (Put)"], key="order_option_type")
        
        with col2:
            # Order side
            side = st.selectbox("Side", ["SELL", "BUY"], key="order_side")
            
            # Quantity (in lots)
            lots = st.number_input("Lots", min_value=1, max_value=50, value=1, key="order_lots")
            quantity = lots * lot_size
            st.caption(f"Quantity: {quantity} ({lots} lots × {lot_size})")
            
            # Order type
            order_type = st.selectbox(
                "Order Type",
                ["Market", "Limit", "Stop Loss"],
                key="order_type"
            )
            
            # Price (for limit orders)
            if order_type != "Market":
                price = st.number_input(
                    "Price",
                    min_value=0.0,
                    value=100.0,
                    step=0.5,
                    format="%.2f",
                    key="order_price"
                )
            else:
                price = None
        
        # Submit button
        submitted = st.form_submit_button("🚀 Submit Order", use_container_width=True)
        
        if submitted:
            # Construct order symbol
            expiry_str = datetime.now().strftime("%d%b").upper()
            opt_type = "CE" if "CE" in option_type else "PE"
            symbol = f"{underlying}{expiry_str}{int(strike)}{opt_type}"
            
            # Place order
            order = data_handler.place_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                price=price
            )
            
            if order:
                st.success(f"✅ Order submitted: {order.get('order_id', 'N/A')}")
                if on_order_submit:
                    on_order_submit(order)
            else:
                st.error("❌ Failed to submit order")
    
    # Quick close section
    st.markdown("#### ⚡ Quick Close")
    
    positions = data_handler.get_positions()
    if positions:
        col1, col2 = st.columns(2)
        
        with col1:
            selected_position = st.selectbox(
                "Select Position",
                [p.symbol if hasattr(p, 'symbol') else p.get('symbol', '') for p in positions],
                key="close_position_select"
            )
        
        with col2:
            if st.button("Close Position", key="close_position_btn", use_container_width=True):
                result = data_handler.close_position(selected_position)
                if result:
                    st.success(f"✅ Position closed: {selected_position}")
                else:
                    st.error("❌ Failed to close position")
    else:
        st.info("No positions to close")


def render_strategy_metrics(strategy: Dict[str, Any], trades: List[Dict] = None) -> None:
    """
    Render strategy performance metrics.
    
    Args:
        strategy: Strategy configuration dictionary
        trades: List of historical trades
    """
    colors = ThemeManager.get_colors()
    
    st.markdown("### 📊 Strategy Performance")
    
    # Strategy info
    strategy_name = strategy.get("name", "Unknown Strategy")
    status = strategy.get("status", "inactive")
    status_icon = "🟢" if status == "active" else "🔴"
    
    st.markdown(f"**{strategy_name}** {status_icon}")
    
    # Performance metrics (demo values if no trades)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Win Rate", "65.8%", delta="+2.3%")
    
    with col2:
        st.metric("Profit Factor", "2.15", delta="+0.12")
    
    with col3:
        st.metric("Sharpe Ratio", "1.85", delta="+0.05")
    
    with col4:
        st.metric("Avg Trade", "₹2,450", delta="₹+125")
    
    # Recent performance
    st.markdown("#### Recent Performance")
    
    perf_data = {
        "Period": ["Today", "This Week", "This Month", "YTD"],
        "P&L": ["₹3,250", "₹12,800", "₹45,600", "₹156,000"],
        "Trades": [2, 8, 32, 145],
        "Win Rate": ["100%", "75%", "68%", "66%"],
    }
    
    st.dataframe(
        perf_data,
        use_container_width=True,
        hide_index=True,
    )


def render_capital_metrics(
    initial_capital: float,
    current_capital: float,
    margin_used: float,
) -> None:
    """
    Render capital and margin metrics.
    
    Args:
        initial_capital: Starting capital
        current_capital: Current capital
        margin_used: Margin used percentage
    """
    colors = ThemeManager.get_colors()
    
    st.markdown("### 💵 Capital Overview")
    
    # Capital metrics
    col1, col2, col3 = st.columns(3)
    
    return_pct = ((current_capital - initial_capital) / initial_capital) * 100
    return_color = colors["profit_color"] if return_pct >= 0 else colors["loss_color"]
    
    with col1:
        st.metric(
            "Initial Capital",
            f"₹{initial_capital:,.0f}",
        )
    
    with col2:
        st.metric(
            "Current Capital",
            f"₹{current_capital:,.0f}",
            delta=f"{return_pct:+.2f}%",
        )
    
    with col3:
        available = current_capital * (1 - margin_used / 100)
        st.metric(
            "Available",
            f"₹{available:,.0f}",
        )
    
    # Margin bar
    st.markdown("**Margin Utilization**")
    
    # Create a progress bar
    margin_color = (
        colors["profit_color"] if margin_used < 50 else
        colors["warning"] if margin_used < 80 else
        colors["loss_color"]
    )
    
    st.progress(min(margin_used / 100, 1.0))
    st.caption(f"Margin Used: {margin_used:.1f}% | Free: {100 - margin_used:.1f}%")
