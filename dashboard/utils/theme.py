"""
Theme Management Module

Provides theme management functionality for the trading dashboard.
Supports dark and light themes with persistent preference storage.
"""

import streamlit as st
from typing import Dict, Any


# Theme color schemes
DARK_THEME: Dict[str, str] = {
    "background": "#0e1117",
    "secondary_background": "#262730",
    "text": "#fafafa",
    "primary": "#ff4b4b",
    "secondary": "#6c757d",
    "success": "#00c853",
    "warning": "#ffc107",
    "danger": "#ff5252",
    "info": "#2196f3",
    "chart_background": "#1e1e1e",
    "grid_color": "#333333",
    "profit_color": "#00c853",
    "loss_color": "#ff5252",
}

LIGHT_THEME: Dict[str, str] = {
    "background": "#ffffff",
    "secondary_background": "#f0f2f6",
    "text": "#31333f",
    "primary": "#ff4b4b",
    "secondary": "#6c757d",
    "success": "#28a745",
    "warning": "#ffc107",
    "danger": "#dc3545",
    "info": "#17a2b8",
    "chart_background": "#ffffff",
    "grid_color": "#e0e0e0",
    "profit_color": "#28a745",
    "loss_color": "#dc3545",
}


class ThemeManager:
    """
    Manages theme preferences and provides theme-related utilities.
    
    Supports dark and light themes with persistent preference storage
    using Streamlit session state.
    
    Attributes:
        DEFAULT_THEME: Default theme setting ('dark' or 'light')
    """
    
    DEFAULT_THEME = "dark"
    
    @staticmethod
    def initialize() -> None:
        """Initialize theme in session state if not already set."""
        if "theme" not in st.session_state:
            st.session_state.theme = ThemeManager.DEFAULT_THEME
    
    @staticmethod
    def get_current_theme() -> str:
        """
        Get the current theme setting.
        
        Returns:
            Current theme name ('dark' or 'light')
        """
        ThemeManager.initialize()
        return st.session_state.theme
    
    @staticmethod
    def set_theme(theme: str) -> None:
        """
        Set the current theme.
        
        Args:
            theme: Theme name ('dark' or 'light')
        """
        if theme in ["dark", "light"]:
            st.session_state.theme = theme
    
    @staticmethod
    def toggle_theme() -> str:
        """
        Toggle between dark and light themes.
        
        Returns:
            New theme name after toggle
        """
        current = ThemeManager.get_current_theme()
        new_theme = "light" if current == "dark" else "dark"
        ThemeManager.set_theme(new_theme)
        return new_theme
    
    @staticmethod
    def is_dark_theme() -> bool:
        """
        Check if dark theme is currently active.
        
        Returns:
            True if dark theme is active
        """
        return ThemeManager.get_current_theme() == "dark"
    
    @staticmethod
    def get_colors() -> Dict[str, str]:
        """
        Get color scheme for current theme.
        
        Returns:
            Dictionary of color values
        """
        return DARK_THEME if ThemeManager.is_dark_theme() else LIGHT_THEME
    
    @staticmethod
    def get_plotly_template() -> str:
        """
        Get Plotly template name for current theme.
        
        Returns:
            Plotly template name
        """
        return "plotly_dark" if ThemeManager.is_dark_theme() else "plotly_white"
    
    @staticmethod
    def get_chart_colors() -> Dict[str, str]:
        """
        Get chart-specific colors for current theme.
        
        Returns:
            Dictionary of chart colors
        """
        colors = ThemeManager.get_colors()
        return {
            "background": colors["chart_background"],
            "grid": colors["grid_color"],
            "profit": colors["profit_color"],
            "loss": colors["loss_color"],
            "text": colors["text"],
            "primary": colors["primary"],
        }


def get_custom_css() -> str:
    """
    Generate custom CSS based on current theme.
    
    Returns:
        CSS string for styling
    """
    colors = ThemeManager.get_colors()
    
    css = f"""
    <style>
        /* Main container styles */
        .stApp {{
            background-color: {colors["background"]};
        }}
        
        /* Metric card styles */
        .metric-card {{
            background-color: {colors["secondary_background"]};
            padding: 1rem;
            border-radius: 0.5rem;
            border-left: 4px solid {colors["primary"]};
            margin-bottom: 0.5rem;
        }}
        
        .metric-value {{
            font-size: 1.5rem;
            font-weight: bold;
            color: {colors["text"]};
        }}
        
        .metric-label {{
            font-size: 0.875rem;
            color: {colors["secondary"]};
        }}
        
        /* Profit/Loss colors */
        .profit {{
            color: {colors["profit_color"]} !important;
        }}
        
        .loss {{
            color: {colors["loss_color"]} !important;
        }}
        
        /* Alert styles */
        .alert-info {{
            background-color: {colors["info"]}20;
            border-left: 4px solid {colors["info"]};
            padding: 0.75rem;
            border-radius: 0.25rem;
            margin-bottom: 0.5rem;
        }}
        
        .alert-warning {{
            background-color: {colors["warning"]}20;
            border-left: 4px solid {colors["warning"]};
            padding: 0.75rem;
            border-radius: 0.25rem;
            margin-bottom: 0.5rem;
        }}
        
        .alert-danger {{
            background-color: {colors["danger"]}20;
            border-left: 4px solid {colors["danger"]};
            padding: 0.75rem;
            border-radius: 0.25rem;
            margin-bottom: 0.5rem;
        }}
        
        .alert-success {{
            background-color: {colors["success"]}20;
            border-left: 4px solid {colors["success"]};
            padding: 0.75rem;
            border-radius: 0.25rem;
            margin-bottom: 0.5rem;
        }}
        
        /* Position table styles */
        .position-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        .position-table th {{
            background-color: {colors["secondary_background"]};
            padding: 0.5rem;
            text-align: left;
            border-bottom: 2px solid {colors["grid_color"]};
        }}
        
        .position-table td {{
            padding: 0.5rem;
            border-bottom: 1px solid {colors["grid_color"]};
        }}
        
        /* Sidebar styles */
        .sidebar-section {{
            background-color: {colors["secondary_background"]};
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
        }}
        
        /* Button styles */
        .stButton > button {{
            width: 100%;
        }}
        
        /* Hide Streamlit branding */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        
        /* Metric overflow handling */
        .metric-value {{
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        /* Responsive adjustments for medium screens */
        @media (max-width: 1024px) {{
            .metric-value {{
                font-size: 1.25rem;
            }}
        }}
        
        /* Responsive adjustments for small screens */
        @media (max-width: 768px) {{
            .metric-value {{
                font-size: 1.1rem;
            }}
            
            .metric-card {{
                padding: 0.75rem;
            }}
        }}
    </style>
    """
    
    return css
