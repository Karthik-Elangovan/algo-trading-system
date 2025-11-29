"""
Tests for Dashboard Components

Tests for the trading dashboard including:
- Data handler functionality
- Export functionality
- Theme management
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.utils.data_handler import (
    DashboardDataHandler,
    MarketData,
    RiskMetrics,
    PositionData,
)
from dashboard.utils.export import ExportManager
from dashboard.utils.theme import ThemeManager, DARK_THEME, LIGHT_THEME


class TestDashboardDataHandler:
    """Tests for DashboardDataHandler."""
    
    @pytest.fixture
    def data_handler(self):
        """Create a data handler instance."""
        return DashboardDataHandler(initial_capital=1_000_000)
    
    def test_initialization(self, data_handler):
        """Test data handler initializes correctly."""
        assert data_handler.initial_capital == 1_000_000
        assert data_handler.current_capital > 0
        assert data_handler.data_fetcher is not None
        assert data_handler.iv_calculator is not None
        assert data_handler.strategy is not None
    
    def test_get_market_data(self, data_handler):
        """Test getting market data."""
        market_data = data_handler.get_market_data("NIFTY")
        
        assert isinstance(market_data, MarketData)
        assert market_data.spot_price > 0
        assert 0 <= market_data.iv <= 1
        assert 0 <= market_data.iv_rank <= 100
        assert market_data.timestamp is not None
    
    def test_get_market_data_different_underlyings(self, data_handler):
        """Test getting market data for different underlyings."""
        underlyings = ["NIFTY", "BANKNIFTY", "SENSEX"]
        
        for underlying in underlyings:
            market_data = data_handler.get_market_data(underlying)
            assert market_data.spot_price > 0
    
    def test_get_positions(self, data_handler):
        """Test getting positions."""
        positions = data_handler.get_positions()
        
        assert isinstance(positions, list)
        assert len(positions) >= 0
        
        if positions:
            pos = positions[0]
            assert isinstance(pos, PositionData)
            assert pos.symbol is not None
            assert pos.quantity != 0
    
    def test_get_risk_metrics(self, data_handler):
        """Test getting risk metrics."""
        risk = data_handler.get_risk_metrics()
        
        assert isinstance(risk, RiskMetrics)
        assert risk.var_95 >= 0
        assert risk.var_99 >= risk.var_95  # 99% VaR is more extreme, so should be >= 95% VaR
        assert 0 <= risk.margin_used <= 100
        assert risk.drawdown >= 0
    
    def test_get_pnl_history(self, data_handler):
        """Test getting P&L history."""
        pnl_history = data_handler.get_pnl_history()
        
        assert isinstance(pnl_history, pd.DataFrame)
        
        if not pnl_history.empty:
            assert "date" in pnl_history.columns
            assert "daily_pnl" in pnl_history.columns
            assert "cumulative_pnl" in pnl_history.columns
    
    def test_get_order_history(self, data_handler):
        """Test getting order history."""
        orders = data_handler.get_order_history()
        
        assert isinstance(orders, list)
        
        if orders:
            order = orders[0]
            assert "order_id" in order
            assert "symbol" in order
            assert "side" in order
            assert "quantity" in order
            assert "status" in order
    
    def test_get_strategies(self, data_handler):
        """Test getting available strategies."""
        strategies = data_handler.get_strategies()
        
        assert isinstance(strategies, list)
        assert len(strategies) > 0
        
        strategy = strategies[0]
        assert "name" in strategy
        assert "description" in strategy
        assert "parameters" in strategy
        assert "status" in strategy
    
    def test_get_available_underlyings(self, data_handler):
        """Test getting available underlyings."""
        underlyings = data_handler.get_available_underlyings()
        
        assert isinstance(underlyings, list)
        assert "NIFTY" in underlyings
        assert "BANKNIFTY" in underlyings
        assert "SENSEX" in underlyings
    
    def test_place_order(self, data_handler):
        """Test placing an order."""
        order = data_handler.place_order(
            symbol="NIFTY25DEC19500CE",
            side="SELL",
            quantity=50,
            order_type="Market",
        )
        
        assert order is not None
        assert "order_id" in order
        assert order["symbol"] == "NIFTY25DEC19500CE"
        assert order["side"] == "SELL"
        assert order["quantity"] == 50
        assert order["status"] == "Pending"
    
    def test_close_position(self, data_handler):
        """Test closing a position."""
        positions = data_handler.get_positions()
        
        if positions:
            symbol = positions[0].symbol
            initial_count = len(positions)
            
            result = data_handler.close_position(symbol)
            
            assert result is not None
            assert result["status"] == "Filled"
            
            new_positions = data_handler.get_positions()
            assert len(new_positions) == initial_count - 1
    
    def test_get_equity_curve(self, data_handler):
        """Test getting equity curve."""
        equity = data_handler.get_equity_curve()
        
        assert isinstance(equity, pd.DataFrame)
        
        if not equity.empty:
            assert "equity" in equity.columns
            assert "peak" in equity.columns
            assert "drawdown" in equity.columns


class TestExportManager:
    """Tests for ExportManager."""
    
    @pytest.fixture
    def sample_dataframe(self):
        """Create sample DataFrame for testing."""
        return pd.DataFrame({
            "date": pd.date_range(start="2024-01-01", periods=10),
            "value": range(10),
            "category": ["A", "B"] * 5,
        })
    
    @pytest.fixture
    def sample_positions(self):
        """Create sample positions for testing."""
        return [
            PositionData(
                symbol="NIFTY_STRANGLE",
                underlying="NIFTY",
                position_type="Short Strangle",
                quantity=100,
                entry_price=250,
                current_price=200,
                unrealized_pnl=5000,
                delta=-0.15,
                gamma=0.002,
                theta=-8.5,
                vega=12.3,
                entry_date=datetime.now() - timedelta(days=5),
                expiry=datetime.now() + timedelta(days=15),
            )
        ]
    
    @pytest.fixture
    def sample_orders(self):
        """Create sample orders for testing."""
        return [
            {
                "order_id": "ORD001",
                "timestamp": datetime.now(),
                "symbol": "NIFTY25DEC19500CE",
                "underlying": "NIFTY",
                "side": "SELL",
                "quantity": 50,
                "order_type": "Market",
                "price": 125.50,
                "status": "Filled",
            }
        ]
    
    def test_export_to_csv(self, sample_dataframe):
        """Test exporting DataFrame to CSV."""
        csv_data = ExportManager.export_to_csv(sample_dataframe)
        
        assert isinstance(csv_data, bytes)
        assert len(csv_data) > 0
        assert b"date" in csv_data
        assert b"value" in csv_data
    
    def test_export_positions_csv(self, sample_positions):
        """Test exporting positions to CSV."""
        csv_data = ExportManager.export_positions_csv(sample_positions)
        
        assert isinstance(csv_data, bytes)
        assert len(csv_data) > 0
        assert b"Symbol" in csv_data
        assert b"NIFTY_STRANGLE" in csv_data
    
    def test_export_positions_csv_empty(self):
        """Test exporting empty positions list."""
        csv_data = ExportManager.export_positions_csv([])
        
        assert b"No positions" in csv_data
    
    def test_export_orders_csv(self, sample_orders):
        """Test exporting orders to CSV."""
        csv_data = ExportManager.export_orders_csv(sample_orders)
        
        assert isinstance(csv_data, bytes)
        assert len(csv_data) > 0
        assert b"Order ID" in csv_data
        assert b"ORD001" in csv_data
    
    def test_export_orders_csv_empty(self):
        """Test exporting empty orders list."""
        csv_data = ExportManager.export_orders_csv([])
        
        assert b"No orders" in csv_data
    
    def test_export_pnl_csv(self):
        """Test exporting P&L data to CSV."""
        pnl_data = pd.DataFrame({
            "date": pd.date_range(start="2024-01-01", periods=5),
            "daily_pnl": [1000, -500, 2000, 1500, -200],
            "cumulative_pnl": [1000, 500, 2500, 4000, 3800],
            "equity": [1001000, 1000500, 1002500, 1004000, 1003800],
        })
        
        csv_data = ExportManager.export_pnl_csv(pnl_data)
        
        assert isinstance(csv_data, bytes)
        assert len(csv_data) > 0
    
    def test_generate_pnl_report(self, sample_positions):
        """Test generating P&L report."""
        pnl_data = pd.DataFrame({
            "date": pd.date_range(start="2024-01-01", periods=5),
            "daily_pnl": [1000, -500, 2000, 1500, -200],
            "cumulative_pnl": [1000, 500, 2500, 4000, 3800],
        })
        
        risk_metrics = RiskMetrics(
            var_95=5000,
            var_99=7500,
            cvar_95=6000,
            margin_used=35.5,
            max_exposure=150000,
            daily_pnl=-200,
            total_pnl=3800,
            drawdown=5.2,
            delta_exposure=-0.15,
            gamma_exposure=0.002,
            theta_exposure=-8.5,
            vega_exposure=12.3,
        )
        
        report = ExportManager.generate_pnl_report(
            pnl_data, sample_positions, risk_metrics
        )
        
        assert isinstance(report, str)
        assert "TRADING P&L REPORT" in report
        assert "₹3,800" in report  # Total P&L
        assert "Value at Risk" in report


class TestThemeManager:
    """Tests for ThemeManager."""
    
    def test_default_theme(self):
        """Test default theme is dark."""
        assert ThemeManager.DEFAULT_THEME == "dark"
    
    def test_get_colors_dark(self):
        """Test getting dark theme colors."""
        # Force dark theme
        if "theme" in dir(ThemeManager):
            original = ThemeManager.get_current_theme()
        
        colors = DARK_THEME
        
        assert "background" in colors
        assert "text" in colors
        assert "profit_color" in colors
        assert "loss_color" in colors
    
    def test_get_colors_light(self):
        """Test getting light theme colors."""
        colors = LIGHT_THEME
        
        assert "background" in colors
        assert "text" in colors
        assert "profit_color" in colors
        assert "loss_color" in colors
    
    def test_theme_colors_differ(self):
        """Test that dark and light themes have different colors."""
        assert DARK_THEME["background"] != LIGHT_THEME["background"]
        assert DARK_THEME["text"] != LIGHT_THEME["text"]
    
    def test_get_plotly_template(self):
        """Test getting Plotly template."""
        # Test dark template
        assert ThemeManager.get_plotly_template() in ["plotly_dark", "plotly_white"]
    
    def test_get_chart_colors(self):
        """Test getting chart colors."""
        chart_colors = ThemeManager.get_chart_colors()
        
        assert "background" in chart_colors
        assert "grid" in chart_colors
        assert "profit" in chart_colors
        assert "loss" in chart_colors
        assert "text" in chart_colors


class TestPositionData:
    """Tests for PositionData dataclass."""
    
    def test_position_data_creation(self):
        """Test creating a PositionData object."""
        pos = PositionData(
            symbol="TEST_POSITION",
            underlying="NIFTY",
            position_type="Short Strangle",
            quantity=100,
            entry_price=200,
            current_price=150,
            unrealized_pnl=5000,
        )
        
        assert pos.symbol == "TEST_POSITION"
        assert pos.quantity == 100
        assert pos.unrealized_pnl == 5000
    
    def test_position_data_default_greeks(self):
        """Test PositionData has default Greek values."""
        pos = PositionData(
            symbol="TEST",
            underlying="NIFTY",
            position_type="Test",
            quantity=1,
            entry_price=100,
            current_price=100,
            unrealized_pnl=0,
        )
        
        assert pos.delta == 0.0
        assert pos.gamma == 0.0
        assert pos.theta == 0.0
        assert pos.vega == 0.0


class TestMarketData:
    """Tests for MarketData dataclass."""
    
    def test_market_data_creation(self):
        """Test creating a MarketData object."""
        data = MarketData(
            spot_price=19250.50,
            iv=0.18,
            iv_rank=72.5,
            bid=19250.00,
            ask=19251.00,
            change=0.85,
            volume=50000,
        )
        
        assert data.spot_price == 19250.50
        assert data.iv == 0.18
        assert data.iv_rank == 72.5
        assert data.timestamp is not None


class TestRiskMetrics:
    """Tests for RiskMetrics dataclass."""
    
    def test_risk_metrics_creation(self):
        """Test creating a RiskMetrics object."""
        metrics = RiskMetrics(
            var_95=5000,
            var_99=7500,
            cvar_95=6000,
            margin_used=35.5,
            max_exposure=150000,
            daily_pnl=2500,
            total_pnl=45000,
            drawdown=3.2,
            delta_exposure=-0.25,
            gamma_exposure=0.003,
            theta_exposure=-12.5,
            vega_exposure=18.2,
        )
        
        assert metrics.var_95 == 5000
        assert metrics.var_99 == 7500
        assert metrics.margin_used == 35.5
        assert metrics.delta_exposure == -0.25
    
    def test_risk_metrics_defaults(self):
        """Test RiskMetrics default values."""
        metrics = RiskMetrics()
        
        assert metrics.var_95 == 0.0
        assert metrics.margin_used == 0.0
        assert metrics.drawdown == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
