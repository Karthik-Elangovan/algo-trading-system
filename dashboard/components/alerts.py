"""
Alert System Components Module

Provides alert and notification components for the trading dashboard including:
- Alert manager for storing and managing alerts
- Alert display component
- Notification toast functionality
"""

import streamlit as st
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class AlertType(Enum):
    """Enumeration of alert types."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"


class AlertCategory(Enum):
    """Enumeration of alert categories."""
    STRATEGY = "strategy"
    RISK = "risk"
    ORDER = "order"
    SYSTEM = "system"
    MARKET = "market"


@dataclass
class Alert:
    """
    Data class representing an alert.
    
    Attributes:
        message: Alert message text
        alert_type: Type of alert (info, success, warning, danger)
        category: Category of the alert
        timestamp: When the alert was created
        is_read: Whether the alert has been acknowledged
        metadata: Additional alert data
    """
    message: str
    alert_type: AlertType = AlertType.INFO
    category: AlertCategory = AlertCategory.SYSTEM
    timestamp: datetime = field(default_factory=datetime.now)
    is_read: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "message": self.message,
            "type": self.alert_type.value,
            "category": self.category.value,
            "timestamp": self.timestamp.isoformat(),
            "is_read": self.is_read,
            "metadata": self.metadata,
        }


class AlertManager:
    """
    Manages alerts and notifications for the trading dashboard.
    
    Uses Streamlit session state to persist alerts across reruns.
    
    Attributes:
        max_alerts: Maximum number of alerts to keep in history
    """
    
    def __init__(self, max_alerts: int = 100):
        """
        Initialize the AlertManager.
        
        Args:
            max_alerts: Maximum number of alerts to store
        """
        self.max_alerts = max_alerts
        self._initialize_session_state()
    
    def _initialize_session_state(self) -> None:
        """Initialize session state for alerts."""
        if "alerts" not in st.session_state:
            st.session_state.alerts = []
        if "alert_sound_enabled" not in st.session_state:
            st.session_state.alert_sound_enabled = True
    
    def add_alert(
        self,
        message: str,
        alert_type: AlertType = AlertType.INFO,
        category: AlertCategory = AlertCategory.SYSTEM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Alert:
        """
        Add a new alert.
        
        Args:
            message: Alert message
            alert_type: Type of alert
            category: Category of the alert
            metadata: Additional alert data
        
        Returns:
            The created Alert object
        """
        alert = Alert(
            message=message,
            alert_type=alert_type,
            category=category,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )
        
        st.session_state.alerts.insert(0, alert)
        
        # Trim to max alerts
        if len(st.session_state.alerts) > self.max_alerts:
            st.session_state.alerts = st.session_state.alerts[:self.max_alerts]
        
        return alert
    
    def add_strategy_alert(self, message: str, alert_type: AlertType = AlertType.INFO) -> Alert:
        """Add a strategy-related alert."""
        return self.add_alert(message, alert_type, AlertCategory.STRATEGY)
    
    def add_risk_alert(self, message: str, alert_type: AlertType = AlertType.WARNING) -> Alert:
        """Add a risk-related alert."""
        return self.add_alert(message, alert_type, AlertCategory.RISK)
    
    def add_order_alert(self, message: str, alert_type: AlertType = AlertType.SUCCESS) -> Alert:
        """Add an order-related alert."""
        return self.add_alert(message, alert_type, AlertCategory.ORDER)
    
    def add_system_alert(self, message: str, alert_type: AlertType = AlertType.INFO) -> Alert:
        """Add a system alert."""
        return self.add_alert(message, alert_type, AlertCategory.SYSTEM)
    
    def add_market_alert(self, message: str, alert_type: AlertType = AlertType.INFO) -> Alert:
        """Add a market-related alert."""
        return self.add_alert(message, alert_type, AlertCategory.MARKET)
    
    def get_alerts(
        self,
        category: Optional[AlertCategory] = None,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[Alert]:
        """
        Get alerts with optional filtering.
        
        Args:
            category: Filter by category
            unread_only: Only return unread alerts
            limit: Maximum number of alerts to return
        
        Returns:
            List of Alert objects
        """
        alerts = st.session_state.alerts
        
        if category:
            alerts = [a for a in alerts if a.category == category]
        
        if unread_only:
            alerts = [a for a in alerts if not a.is_read]
        
        return alerts[:limit]
    
    def get_unread_count(self) -> int:
        """Get count of unread alerts."""
        return len([a for a in st.session_state.alerts if not a.is_read])
    
    def mark_as_read(self, index: int) -> None:
        """Mark an alert as read by index."""
        if 0 <= index < len(st.session_state.alerts):
            st.session_state.alerts[index].is_read = True
    
    def mark_all_as_read(self) -> None:
        """Mark all alerts as read."""
        for alert in st.session_state.alerts:
            alert.is_read = True
    
    def clear_alerts(self) -> None:
        """Clear all alerts."""
        st.session_state.alerts = []
    
    def toggle_sound(self) -> bool:
        """Toggle alert sounds and return new state."""
        st.session_state.alert_sound_enabled = not st.session_state.alert_sound_enabled
        return st.session_state.alert_sound_enabled


def render_alerts(
    alert_manager: AlertManager,
    max_display: int = 10,
    show_filters: bool = True,
) -> None:
    """
    Render the alerts panel.
    
    Args:
        alert_manager: AlertManager instance
        max_display: Maximum alerts to display
        show_filters: Whether to show filter controls
    """
    st.markdown("### 🔔 Alerts & Notifications")
    
    # Controls row
    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    
    with col1:
        unread = alert_manager.get_unread_count()
        st.markdown(f"**{unread}** unread alerts")
    
    with col2:
        sound_icon = "🔊" if st.session_state.get("alert_sound_enabled", True) else "🔇"
        if st.button(f"{sound_icon} Sound", key="toggle_sound"):
            alert_manager.toggle_sound()
    
    with col3:
        if st.button("✓ Read All", key="mark_all_read"):
            alert_manager.mark_all_as_read()
            st.rerun()
    
    with col4:
        if st.button("🗑️ Clear", key="clear_alerts"):
            alert_manager.clear_alerts()
            st.rerun()
    
    # Category filter
    if show_filters:
        category_options = ["All"] + [c.value.title() for c in AlertCategory]
        selected_category = st.selectbox(
            "Filter by category",
            category_options,
            key="alert_category_filter",
            label_visibility="collapsed"
        )
        
        if selected_category != "All":
            category_filter = AlertCategory(selected_category.lower())
        else:
            category_filter = None
    else:
        category_filter = None
    
    # Get and display alerts
    alerts = alert_manager.get_alerts(category=category_filter, limit=max_display)
    
    if not alerts:
        st.info("No alerts to display")
        return
    
    # Display alerts
    for i, alert in enumerate(alerts):
        render_single_alert(alert, i)


def render_single_alert(alert: Alert, index: int) -> None:
    """
    Render a single alert item.
    
    Args:
        alert: Alert object to render
        index: Alert index (for unique keys)
    """
    # Determine styling based on alert type
    type_config = {
        AlertType.INFO: {"icon": "ℹ️", "color": "#2196f3"},
        AlertType.SUCCESS: {"icon": "✅", "color": "#00c853"},
        AlertType.WARNING: {"icon": "⚠️", "color": "#ffc107"},
        AlertType.DANGER: {"icon": "🚨", "color": "#ff5252"},
    }
    
    config = type_config.get(alert.alert_type, type_config[AlertType.INFO])
    
    # Category icons
    category_icons = {
        AlertCategory.STRATEGY: "📈",
        AlertCategory.RISK: "⚠️",
        AlertCategory.ORDER: "📝",
        AlertCategory.SYSTEM: "⚙️",
        AlertCategory.MARKET: "📊",
    }
    
    category_icon = category_icons.get(alert.category, "📌")
    
    # Format timestamp
    time_str = alert.timestamp.strftime("%H:%M:%S")
    
    # Opacity for read alerts
    opacity = "0.6" if alert.is_read else "1.0"
    
    # Render alert
    st.markdown(
        f"""
        <div style="
            padding: 0.75rem;
            margin-bottom: 0.5rem;
            border-left: 4px solid {config['color']};
            background-color: {config['color']}20;
            border-radius: 0.25rem;
            opacity: {opacity};
        ">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: bold;">
                    {config['icon']} {category_icon} {alert.message}
                </span>
                <span style="font-size: 0.75rem; color: #888;">
                    {time_str}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_alert_toast(message: str, alert_type: AlertType = AlertType.INFO) -> None:
    """
    Display a toast notification.
    
    Args:
        message: Toast message
        alert_type: Type of toast
    """
    if alert_type == AlertType.SUCCESS:
        st.success(message)
    elif alert_type == AlertType.WARNING:
        st.warning(message)
    elif alert_type == AlertType.DANGER:
        st.error(message)
    else:
        st.info(message)


def generate_sample_alerts(alert_manager: AlertManager) -> None:
    """
    Generate sample alerts for demonstration.
    
    Args:
        alert_manager: AlertManager instance
    """
    sample_alerts = [
        {
            "message": "IV Rank above 70% for NIFTY - Entry conditions met",
            "type": AlertType.INFO,
            "category": AlertCategory.STRATEGY,
        },
        {
            "message": "Order filled: SELL 2 lots NIFTY 19500CE @ ₹125.50",
            "type": AlertType.SUCCESS,
            "category": AlertCategory.ORDER,
        },
        {
            "message": "Margin utilization at 75% - approaching limit",
            "type": AlertType.WARNING,
            "category": AlertCategory.RISK,
        },
        {
            "message": "Position profit target reached: NIFTY Strangle +50%",
            "type": AlertType.SUCCESS,
            "category": AlertCategory.STRATEGY,
        },
        {
            "message": "VIX spike detected - review positions",
            "type": AlertType.WARNING,
            "category": AlertCategory.MARKET,
        },
        {
            "message": "Daily loss limit warning - 80% of limit reached",
            "type": AlertType.DANGER,
            "category": AlertCategory.RISK,
        },
        {
            "message": "Auto-refresh enabled - updating every 30 seconds",
            "type": AlertType.INFO,
            "category": AlertCategory.SYSTEM,
        },
        {
            "message": "BANKNIFTY expiry day - increased gamma risk",
            "type": AlertType.WARNING,
            "category": AlertCategory.RISK,
        },
    ]
    
    # Only add if alerts have not been initialized
    if "alerts" not in st.session_state:
        for alert_data in sample_alerts:
            alert_manager.add_alert(
                message=alert_data["message"],
                alert_type=alert_data["type"],
                category=alert_data["category"],
            )
