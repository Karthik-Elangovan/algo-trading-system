"""
Tests for Broker Integration Modules.

Tests for paper trading broker, broker factory, and utility functions.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.execution.broker import (
    BaseBroker,
    BrokerFactory,
    Order,
    Position,
    Holding,
    Quote,
    AccountInfo,
    OrderType,
    TransactionType,
    ProductType,
    Exchange,
    OrderStatus,
)
from src.execution.paper_broker import PaperBroker
from src.execution.utils import (
    generate_order_id,
    calculate_slippage,
    calculate_transaction_costs,
    validate_order_params,
    format_symbol_for_angel,
    parse_option_symbol,
    get_lot_size,
    round_to_tick,
    is_market_open,
    get_expiry_dates,
)
from config.broker_settings import get_broker_config, validate_config


class TestBrokerFactory:
    """Tests for BrokerFactory."""
    
    def test_available_brokers(self):
        """Test that brokers are registered."""
        brokers = BrokerFactory.available_brokers()
        assert 'paper' in brokers
        assert 'live' in brokers
    
    def test_create_paper_broker(self):
        """Test creating paper broker."""
        broker = BrokerFactory.create('paper')
        assert isinstance(broker, PaperBroker)
    
    def test_create_with_config(self):
        """Test creating broker with configuration."""
        config = {'initial_capital': 500_000}
        broker = BrokerFactory.create('paper', config)
        assert broker._initial_capital == 500_000
    
    def test_create_invalid_mode(self):
        """Test creating broker with invalid mode."""
        with pytest.raises(ValueError):
            BrokerFactory.create('invalid_mode')


class TestPaperBroker:
    """Tests for PaperBroker."""
    
    @pytest.fixture
    def broker(self):
        """Create paper broker for testing."""
        config = {
            'initial_capital': 1_000_000,
            'slippage_pct': 0.005,
            'brokerage_per_order': 20,
        }
        broker = PaperBroker(config)
        broker.login()
        return broker
    
    def test_initialization(self, broker):
        """Test broker initializes correctly."""
        assert broker._initial_capital == 1_000_000
        assert broker._slippage_pct == 0.005
        assert broker._cash == 1_000_000
    
    def test_login_logout(self, broker):
        """Test login and logout."""
        assert broker.is_authenticated
        broker.logout()
        assert not broker.is_authenticated
    
    def test_get_profile(self, broker):
        """Test get profile."""
        profile = broker.get_profile()
        assert isinstance(profile, AccountInfo)
        assert profile.client_id == "PAPER001"
        assert profile.broker == "Paper"
    
    def test_set_and_get_price(self, broker):
        """Test setting and getting market price."""
        broker.set_price("NIFTY", 21000.0)
        assert broker.get_ltp("NIFTY", "NSE") == 21000.0
    
    def test_get_quote(self, broker):
        """Test getting market quote."""
        broker.set_price("NIFTY", 21000.0)
        quote = broker.get_quote("NIFTY", "NSE")
        assert isinstance(quote, Quote)
        assert quote.ltp == 21000.0
        assert quote.symbol == "NIFTY"
    
    def test_place_market_order_buy(self, broker):
        """Test placing market buy order."""
        broker.set_price("NIFTY23DEC21000CE", 100.0)
        
        order_id = broker.place_order(
            symbol="NIFTY23DEC21000CE",
            exchange="NFO",
            transaction_type="BUY",
            quantity=50,
            order_type="MARKET",
            product_type="INTRADAY"
        )
        
        assert order_id.startswith("PAPER_")
        
        # Check order status
        order = broker.get_order_status(order_id)
        assert order.status == "complete"
        assert order.filled_quantity == 50
    
    def test_place_market_order_sell(self, broker):
        """Test placing market sell order."""
        broker.set_price("NIFTY23DEC21000CE", 100.0)
        
        # First buy
        broker.place_order(
            symbol="NIFTY23DEC21000CE",
            exchange="NFO",
            transaction_type="BUY",
            quantity=50,
            order_type="MARKET",
            product_type="INTRADAY"
        )
        
        # Then sell
        order_id = broker.place_order(
            symbol="NIFTY23DEC21000CE",
            exchange="NFO",
            transaction_type="SELL",
            quantity=50,
            order_type="MARKET",
            product_type="INTRADAY"
        )
        
        order = broker.get_order_status(order_id)
        assert order.status == "complete"
        
        # Position should be closed
        positions = broker.get_positions()
        assert len(positions) == 0
    
    def test_place_limit_order(self, broker):
        """Test placing limit order."""
        broker.set_price("NIFTY23DEC21000CE", 100.0)
        
        # Limit order below market - should execute
        order_id = broker.place_order(
            symbol="NIFTY23DEC21000CE",
            exchange="NFO",
            transaction_type="BUY",
            quantity=50,
            order_type="LIMIT",
            product_type="INTRADAY",
            price=110.0  # Above market, should execute
        )
        
        order = broker.get_order_status(order_id)
        assert order.status == "complete"
    
    def test_get_positions(self, broker):
        """Test getting positions."""
        broker.set_price("NIFTY23DEC21000CE", 100.0)
        
        broker.place_order(
            symbol="NIFTY23DEC21000CE",
            exchange="NFO",
            transaction_type="BUY",
            quantity=50,
            order_type="MARKET",
            product_type="INTRADAY"
        )
        
        positions = broker.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "NIFTY23DEC21000CE"
        assert positions[0].quantity == 50
    
    def test_position_pnl_update(self, broker):
        """Test position P&L updates with price change."""
        broker.set_price("NIFTY23DEC21000CE", 100.0)
        
        broker.place_order(
            symbol="NIFTY23DEC21000CE",
            exchange="NFO",
            transaction_type="BUY",
            quantity=50,
            order_type="MARKET",
            product_type="INTRADAY"
        )
        
        # Price moves up
        broker.set_price("NIFTY23DEC21000CE", 110.0)
        
        positions = broker.get_positions()
        assert positions[0].last_price == 110.0
        assert positions[0].pnl > 0  # Should be profitable
    
    def test_square_off_position(self, broker):
        """Test squaring off a position."""
        broker.set_price("NIFTY23DEC21000CE", 100.0)
        
        broker.place_order(
            symbol="NIFTY23DEC21000CE",
            exchange="NFO",
            transaction_type="BUY",
            quantity=50,
            order_type="MARKET",
            product_type="INTRADAY"
        )
        
        # Square off
        order_id = broker.square_off_position(
            symbol="NIFTY23DEC21000CE",
            exchange="NFO",
            product_type="INTRADAY"
        )
        
        assert order_id.startswith("PAPER_")
        
        positions = broker.get_positions()
        assert len(positions) == 0
    
    def test_modify_order(self, broker):
        """Test modifying an order."""
        broker.set_price("NIFTY23DEC21000CE", 100.0)
        
        # Place limit order that won't execute
        order_id = broker.place_order(
            symbol="NIFTY23DEC21000CE",
            exchange="NFO",
            transaction_type="BUY",
            quantity=50,
            order_type="LIMIT",
            product_type="INTRADAY",
            price=90.0  # Below market
        )
        
        # Modify quantity
        result = broker.modify_order(order_id, quantity=100)
        assert result is True
        
        order = broker.get_order_status(order_id)
        assert order.quantity == 100
    
    def test_cancel_order(self, broker):
        """Test cancelling an order."""
        broker.set_price("NIFTY23DEC21000CE", 100.0)
        
        order_id = broker.place_order(
            symbol="NIFTY23DEC21000CE",
            exchange="NFO",
            transaction_type="BUY",
            quantity=50,
            order_type="LIMIT",
            product_type="INTRADAY",
            price=90.0
        )
        
        result = broker.cancel_order(order_id)
        assert result is True
        
        order = broker.get_order_status(order_id)
        assert order.status == "cancelled"
    
    def test_get_margin(self, broker):
        """Test getting margin information."""
        margin = broker.get_margin()
        assert 'available_margin' in margin
        assert margin['available_margin'] == 1_000_000
    
    def test_order_history(self, broker):
        """Test getting order history."""
        broker.set_price("NIFTY", 100.0)
        
        broker.place_order(
            symbol="NIFTY",
            exchange="NSE",
            transaction_type="BUY",
            quantity=10,
            order_type="MARKET",
            product_type="INTRADAY"
        )
        
        history = broker.get_order_history()
        assert len(history) == 1
    
    def test_portfolio_value(self, broker):
        """Test portfolio value calculation."""
        initial_value = broker.get_portfolio_value()
        assert initial_value == 1_000_000
        
        broker.set_price("NIFTY", 100.0)
        broker.place_order(
            symbol="NIFTY",
            exchange="NSE",
            transaction_type="BUY",
            quantity=100,
            order_type="MARKET",
            product_type="INTRADAY"
        )
        
        # Price increase
        broker.set_price("NIFTY", 110.0)
        
        new_value = broker.get_portfolio_value()
        assert new_value > initial_value - 10100  # Initial - cost + profit
    
    def test_statistics(self, broker):
        """Test getting statistics."""
        broker.set_price("NIFTY", 100.0)
        
        broker.place_order(
            symbol="NIFTY",
            exchange="NSE",
            transaction_type="BUY",
            quantity=10,
            order_type="MARKET",
            product_type="INTRADAY"
        )
        
        stats = broker.get_statistics()
        assert stats['total_orders'] == 1
        assert stats['total_trades'] == 1
        assert stats['open_positions'] == 1
    
    def test_reset(self, broker):
        """Test resetting paper broker."""
        broker.set_price("NIFTY", 100.0)
        broker.place_order(
            symbol="NIFTY",
            exchange="NSE",
            transaction_type="BUY",
            quantity=10,
            order_type="MARKET",
            product_type="INTRADAY"
        )
        
        broker.reset()
        
        assert broker._cash == 1_000_000
        assert len(broker.get_positions()) == 0
        assert len(broker.get_order_history()) == 0
    
    def test_insufficient_funds(self, broker):
        """Test order rejection due to insufficient funds."""
        broker.set_price("EXPENSIVE", 1_000_000.0)
        
        order_id = broker.place_order(
            symbol="EXPENSIVE",
            exchange="NSE",
            transaction_type="BUY",
            quantity=100,  # Would cost 100 million
            order_type="MARKET",
            product_type="INTRADAY"
        )
        
        # Order should be rejected
        order = broker.get_order_status(order_id)
        assert order.status == "rejected"
        assert "Insufficient" in order.message
    
    def test_invalid_order_params(self, broker):
        """Test order validation."""
        with pytest.raises(ValueError):
            broker.place_order(
                symbol="",  # Empty symbol
                exchange="NSE",
                transaction_type="BUY",
                quantity=10,
                order_type="MARKET",
                product_type="INTRADAY"
            )
        
        with pytest.raises(ValueError):
            broker.place_order(
                symbol="NIFTY",
                exchange="NSE",
                transaction_type="INVALID",  # Invalid transaction type
                quantity=10,
                order_type="MARKET",
                product_type="INTRADAY"
            )
        
        with pytest.raises(ValueError):
            broker.place_order(
                symbol="NIFTY",
                exchange="NSE",
                transaction_type="BUY",
                quantity=-10,  # Negative quantity
                order_type="MARKET",
                product_type="INTRADAY"
            )


class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_generate_order_id(self):
        """Test order ID generation."""
        order_id = generate_order_id()
        assert order_id.startswith("PAPER_")
        assert len(order_id) == 18  # PAPER_ + 12 chars
    
    def test_calculate_slippage_buy(self):
        """Test slippage calculation for buy."""
        price = calculate_slippage(100.0, "BUY", 0.01)
        assert price == 101.0  # 1% slippage
    
    def test_calculate_slippage_sell(self):
        """Test slippage calculation for sell."""
        price = calculate_slippage(100.0, "SELL", 0.01)
        assert price == 99.0  # 1% slippage
    
    def test_calculate_transaction_costs(self):
        """Test transaction cost calculation."""
        costs = calculate_transaction_costs(100_000, is_sell=True)
        
        assert 'brokerage' in costs
        assert 'stt' in costs
        assert 'total' in costs
        assert costs['total'] > 0
    
    def test_calculate_transaction_costs_buy(self):
        """Test transaction costs for buy (no STT)."""
        costs_buy = calculate_transaction_costs(100_000, is_sell=False)
        costs_sell = calculate_transaction_costs(100_000, is_sell=True)
        
        # STT only on sell
        assert costs_buy['stt'] == 0
        assert costs_sell['stt'] > 0
        assert costs_buy['total'] < costs_sell['total']
    
    def test_validate_order_params_valid(self):
        """Test order validation with valid params."""
        is_valid, msg = validate_order_params(
            symbol="NIFTY",
            exchange="NSE",
            transaction_type="BUY",
            quantity=10,
            order_type="MARKET",
            product_type="INTRADAY"
        )
        assert is_valid
        assert msg == ""
    
    def test_validate_order_params_invalid_symbol(self):
        """Test order validation with invalid symbol."""
        is_valid, msg = validate_order_params(
            symbol="",
            exchange="NSE",
            transaction_type="BUY",
            quantity=10,
            order_type="MARKET",
            product_type="INTRADAY"
        )
        assert not is_valid
        assert "Symbol" in msg
    
    def test_validate_order_params_limit_no_price(self):
        """Test order validation for limit order without price."""
        is_valid, msg = validate_order_params(
            symbol="NIFTY",
            exchange="NSE",
            transaction_type="BUY",
            quantity=10,
            order_type="LIMIT",
            product_type="INTRADAY",
            price=0  # No price for limit
        )
        assert not is_valid
        assert "Price" in msg
    
    def test_format_symbol_for_angel(self):
        """Test symbol formatting for Angel One."""
        expiry = datetime(2023, 12, 21)
        symbol = format_symbol_for_angel("NIFTY", expiry, 21000, "CE")
        assert symbol == "NIFTY23DEC21000CE"
    
    def test_parse_option_symbol(self):
        """Test option symbol parsing."""
        result = parse_option_symbol("NIFTY23DEC21000CE")
        
        assert result is not None
        assert result['underlying'] == "NIFTY"
        assert result['strike'] == 21000.0
        assert result['option_type'] == "CE"
    
    def test_parse_option_symbol_invalid(self):
        """Test parsing invalid option symbol."""
        result = parse_option_symbol("INVALID")
        assert result is None
    
    def test_get_lot_size(self):
        """Test lot size retrieval."""
        assert get_lot_size("NIFTY") == 50
        assert get_lot_size("BANKNIFTY") == 15
        assert get_lot_size("NIFTY23DEC21000CE") == 50
        assert get_lot_size("UNKNOWN") == 1  # Default
    
    def test_round_to_tick(self):
        """Test price rounding to tick size."""
        assert round_to_tick(100.03, 0.05) == 100.05
        assert round_to_tick(100.01, 0.05) == 100.0
        assert round_to_tick(100.0, 0.05) == 100.0
    
    def test_get_expiry_dates(self):
        """Test expiry dates generation."""
        expiries = get_expiry_dates("NIFTY", count=5)
        
        assert len(expiries) == 5
        # All expiries should be in the future
        for expiry in expiries:
            assert expiry > datetime.now()


class TestDataClasses:
    """Tests for data classes."""
    
    def test_order_creation(self):
        """Test Order dataclass."""
        order = Order(
            order_id="TEST123",
            symbol="NIFTY",
            exchange="NSE",
            transaction_type="BUY",
            quantity=50,
            order_type="MARKET",
            product_type="INTRADAY"
        )
        
        assert order.order_id == "TEST123"
        assert order.symbol == "NIFTY"
        assert order.status == "pending"
    
    def test_position_creation(self):
        """Test Position dataclass."""
        position = Position(
            symbol="NIFTY",
            exchange="NSE",
            product_type="INTRADAY",
            quantity=50,
            average_price=100.0,
            last_price=110.0,
            pnl=500.0
        )
        
        assert position.symbol == "NIFTY"
        assert position.pnl == 500.0
    
    def test_quote_creation(self):
        """Test Quote dataclass."""
        quote = Quote(
            symbol="NIFTY",
            exchange="NSE",
            ltp=21000.0,
            open=20900.0,
            high=21100.0,
            low=20850.0,
            close=20950.0
        )
        
        assert quote.ltp == 21000.0
        assert quote.high > quote.low
    
    def test_account_info_creation(self):
        """Test AccountInfo dataclass."""
        info = AccountInfo(
            client_id="ABC123",
            name="Test User",
            email="test@example.com",
            broker="Angel One",
            available_margin=100000.0
        )
        
        assert info.client_id == "ABC123"
        assert info.available_margin == 100000.0


class TestBrokerConfig:
    """Tests for broker configuration."""
    
    def test_get_broker_config_paper(self):
        """Test getting paper trading config."""
        config = get_broker_config("paper")
        
        assert config['mode'] == "paper"
        assert 'initial_capital' in config
        assert 'slippage_pct' in config
    
    def test_get_broker_config_live(self):
        """Test getting live trading config."""
        config = get_broker_config("live")
        
        assert config['mode'] == "live"
        assert 'api_key' in config
    
    def test_validate_config_paper_valid(self):
        """Test validating paper config."""
        config = {
            'mode': 'paper',
            'initial_capital': 1_000_000,
            'slippage_pct': 0.005,
        }
        
        assert validate_config(config) is True
    
    def test_validate_config_paper_invalid(self):
        """Test validating invalid paper config."""
        config = {
            'mode': 'paper',
            # Missing initial_capital
            'slippage_pct': 0.005,
        }
        
        with pytest.raises(ValueError):
            validate_config(config)


class TestEnums:
    """Tests for enum values."""
    
    def test_order_type_values(self):
        """Test OrderType enum."""
        assert OrderType.MARKET.value == "MARKET"
        assert OrderType.LIMIT.value == "LIMIT"
        assert OrderType.STOP_LOSS.value == "STOPLOSS"
    
    def test_transaction_type_values(self):
        """Test TransactionType enum."""
        assert TransactionType.BUY.value == "BUY"
        assert TransactionType.SELL.value == "SELL"
    
    def test_product_type_values(self):
        """Test ProductType enum."""
        assert ProductType.INTRADAY.value == "INTRADAY"
        assert ProductType.DELIVERY.value == "DELIVERY"
    
    def test_exchange_values(self):
        """Test Exchange enum."""
        assert Exchange.NSE.value == "NSE"
        assert Exchange.NFO.value == "NFO"
        assert Exchange.BSE.value == "BSE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
