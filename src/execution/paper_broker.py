"""
Paper Trading Broker Implementation.

A simulated broker for testing strategies without real money.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .broker import (
    BaseBroker,
    BrokerFactory,
    Order,
    Position,
    Holding,
    Quote,
    AccountInfo,
    OrderStatus,
)
from .utils import (
    generate_order_id,
    calculate_slippage,
    calculate_transaction_costs,
    validate_order_params,
)

logger = logging.getLogger(__name__)


class PaperBroker(BaseBroker):
    """
    Paper trading broker for backtesting and simulation.
    
    Simulates realistic order execution with:
    - Configurable slippage
    - Transaction costs
    - Position tracking
    - P&L calculation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize paper trading broker.
        
        Args:
            config: Configuration dictionary with:
                - initial_capital: Starting capital (default 1,000,000)
                - slippage_pct: Slippage percentage (default 0.5%)
                - brokerage_per_order: Per order brokerage (default 20)
        """
        super().__init__(config)
        
        # Initialize with configuration
        self._initial_capital = config.get('initial_capital', 1_000_000) if config else 1_000_000
        self._slippage_pct = config.get('slippage_pct', 0.005) if config else 0.005
        self._brokerage_per_order = config.get('brokerage_per_order', 20) if config else 20
        
        # Account state
        self._cash = self._initial_capital
        self._positions: Dict[str, Position] = {}  # symbol -> Position
        self._holdings: Dict[str, Holding] = {}  # symbol -> Holding
        self._orders: Dict[str, Order] = {}  # order_id -> Order
        self._order_history: List[Order] = []
        
        # Market data simulation
        self._market_prices: Dict[str, float] = {}  # symbol -> price
        
        # Statistics
        self._total_orders = 0
        self._total_trades = 0
        self._total_commission = 0.0
        
        logger.info(f"Initialized PaperBroker with capital: {self._initial_capital}")
    
    # ==================== Authentication ====================
    
    def login(self) -> bool:
        """Login to paper broker (always succeeds)."""
        self._is_authenticated = True
        logger.info("Paper broker logged in")
        return True
    
    def logout(self) -> bool:
        """Logout from paper broker."""
        self._is_authenticated = False
        logger.info("Paper broker logged out")
        return True
    
    def get_profile(self) -> AccountInfo:
        """Get paper broker profile."""
        return AccountInfo(
            client_id="PAPER001",
            name="Paper Trading Account",
            email="paper@trading.com",
            broker="Paper",
            available_margin=self._cash,
            used_margin=self._calculate_used_margin(),
            total_margin=self._initial_capital,
        )
    
    # ==================== Market Data ====================
    
    def get_ltp(self, symbol: str, exchange: str) -> float:
        """Get last traded price for a symbol."""
        return self._market_prices.get(symbol, 0.0)
    
    def set_price(self, symbol: str, price: float) -> None:
        """
        Set price for a symbol (for simulation).
        
        Args:
            symbol: Trading symbol
            price: Price to set
        """
        self._market_prices[symbol] = price
        
        # Update position LTP
        if symbol in self._positions:
            self._positions[symbol].last_price = price
            self._update_position_pnl(symbol)
    
    def get_quote(self, symbol: str, exchange: str) -> Quote:
        """Get market quote for a symbol."""
        price = self._market_prices.get(symbol, 100.0)
        
        # Simulate bid-ask spread
        spread = price * 0.001  # 0.1% spread
        
        return Quote(
            symbol=symbol,
            exchange=exchange,
            ltp=price,
            open=price * 0.99,
            high=price * 1.01,
            low=price * 0.98,
            close=price,
            volume=random.randint(10000, 100000),
            bid_price=price - spread / 2,
            ask_price=price + spread / 2,
            bid_quantity=random.randint(100, 1000),
            ask_quantity=random.randint(100, 1000),
        )
    
    def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get historical data (returns empty for paper trading)."""
        # Paper broker doesn't have historical data
        # Use data module for historical data
        logger.warning("Paper broker doesn't provide historical data")
        return []
    
    # ==================== Order Management ====================
    
    def place_order(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str = "MARKET",
        product_type: str = "INTRADAY",
        price: float = 0.0,
        trigger_price: float = 0.0,
        variety: str = "NORMAL"
    ) -> str:
        """
        Place an order in paper trading mode.
        
        Returns:
            Order ID string
        """
        # Validate parameters
        is_valid, error_msg = validate_order_params(
            symbol, exchange, transaction_type, quantity,
            order_type, product_type, price, trigger_price
        )
        if not is_valid:
            logger.error(f"Invalid order parameters: {error_msg}")
            raise ValueError(error_msg)
        
        # Generate order ID
        order_id = generate_order_id()
        self._total_orders += 1
        
        # Get market price
        market_price = self._market_prices.get(symbol, price if price > 0 else 100.0)
        
        # Determine execution price
        if order_type.upper() == "MARKET":
            exec_price = calculate_slippage(market_price, transaction_type, self._slippage_pct)
        elif order_type.upper() == "LIMIT":
            exec_price = price
        else:
            exec_price = trigger_price if trigger_price > 0 else price
        
        # Create order
        order = Order(
            order_id=order_id,
            symbol=symbol,
            exchange=exchange,
            transaction_type=transaction_type.upper(),
            quantity=quantity,
            order_type=order_type.upper(),
            product_type=product_type.upper(),
            price=price,
            trigger_price=trigger_price,
            status="pending",
            variety=variety,
        )
        
        self._orders[order_id] = order
        
        # Execute order immediately for market orders
        if order_type.upper() == "MARKET":
            self._execute_order(order_id, exec_price)
        else:
            # For limit orders, check if can execute immediately
            can_execute = self._check_limit_order(order, market_price)
            if can_execute:
                self._execute_order(order_id, exec_price)
            else:
                order.status = "open"
        
        self._order_history.append(order)
        logger.info(f"Order placed: {order_id} {transaction_type} {quantity} {symbol} @ {exec_price}")
        
        return order_id
    
    def _execute_order(self, order_id: str, exec_price: float) -> None:
        """Execute an order and update positions."""
        order = self._orders.get(order_id)
        if not order:
            return
        
        # Calculate transaction costs
        value = exec_price * order.quantity
        costs = calculate_transaction_costs(
            value,
            is_sell=(order.transaction_type == "SELL"),
            brokerage=self._brokerage_per_order
        )
        
        self._total_commission += costs['total']
        
        # Update cash
        if order.transaction_type == "BUY":
            total_cost = value + costs['total']
            if total_cost > self._cash:
                order.status = "rejected"
                order.message = "Insufficient funds"
                logger.warning(f"Order {order_id} rejected: Insufficient funds")
                return
            self._cash -= total_cost
        else:
            self._cash += value - costs['total']
        
        # Update order status
        order.status = "complete"
        order.filled_quantity = order.quantity
        order.average_price = exec_price
        order.updated_at = datetime.now()
        
        # Update positions
        self._update_position(order, exec_price)
        
        self._total_trades += 1
        logger.info(f"Order {order_id} executed @ {exec_price}")
    
    def _check_limit_order(self, order: Order, market_price: float) -> bool:
        """Check if a limit order can be executed."""
        if order.order_type == "LIMIT":
            if order.transaction_type == "BUY" and market_price <= order.price:
                return True
            if order.transaction_type == "SELL" and market_price >= order.price:
                return True
        return False
    
    def _update_position(self, order: Order, exec_price: float) -> None:
        """Update position based on executed order."""
        symbol = order.symbol
        qty = order.quantity
        
        if symbol in self._positions:
            pos = self._positions[symbol]
            
            if order.transaction_type == "BUY":
                # Add to position
                new_qty = pos.quantity + qty
                if new_qty != 0:
                    new_avg = (pos.average_price * pos.quantity + exec_price * qty) / new_qty
                else:
                    new_avg = 0
                pos.quantity = new_qty
                pos.average_price = new_avg if new_qty > 0 else pos.average_price
                pos.day_buy_quantity += qty
                pos.day_buy_value += exec_price * qty
            else:
                # Reduce position
                pos.quantity -= qty
                pos.day_sell_quantity += qty
                pos.day_sell_value += exec_price * qty
            
            pos.last_price = exec_price
            self._update_position_pnl(symbol)
            
            # Remove if position is closed
            if pos.quantity == 0:
                del self._positions[symbol]
        else:
            # Create new position
            direction = 1 if order.transaction_type == "BUY" else -1
            self._positions[symbol] = Position(
                symbol=symbol,
                exchange=order.exchange,
                product_type=order.product_type,
                quantity=qty * direction,
                average_price=exec_price,
                last_price=exec_price,
                pnl=0.0,
                day_buy_quantity=qty if direction > 0 else 0,
                day_sell_quantity=qty if direction < 0 else 0,
                day_buy_value=exec_price * qty if direction > 0 else 0,
                day_sell_value=exec_price * qty if direction < 0 else 0,
            )
    
    def _update_position_pnl(self, symbol: str) -> None:
        """Update P&L for a position."""
        if symbol not in self._positions:
            return
        
        pos = self._positions[symbol]
        if pos.quantity == 0:
            return
            
        if pos.quantity > 0:
            pos.pnl = (pos.last_price - pos.average_price) * pos.quantity
        else:
            pos.pnl = (pos.average_price - pos.last_price) * abs(pos.quantity)
        
        if pos.average_price > 0 and pos.quantity != 0:
            pos.pnl_percentage = pos.pnl / (pos.average_price * abs(pos.quantity)) * 100
    
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        order_type: Optional[str] = None
    ) -> bool:
        """Modify an existing order."""
        if order_id not in self._orders:
            logger.warning(f"Order not found: {order_id}")
            return False
        
        order = self._orders[order_id]
        
        if order.status not in ["pending", "open"]:
            logger.warning(f"Cannot modify order with status: {order.status}")
            return False
        
        if quantity:
            order.quantity = quantity
        if price:
            order.price = price
        if trigger_price:
            order.trigger_price = trigger_price
        if order_type:
            order.order_type = order_type
        
        order.updated_at = datetime.now()
        logger.info(f"Order {order_id} modified")
        return True
    
    def cancel_order(self, order_id: str, variety: str = "NORMAL") -> bool:
        """Cancel an order."""
        if order_id not in self._orders:
            logger.warning(f"Order not found: {order_id}")
            return False
        
        order = self._orders[order_id]
        
        if order.status not in ["pending", "open"]:
            logger.warning(f"Cannot cancel order with status: {order.status}")
            return False
        
        order.status = "cancelled"
        order.updated_at = datetime.now()
        logger.info(f"Order {order_id} cancelled")
        return True
    
    def get_order_status(self, order_id: str) -> Order:
        """Get order status."""
        if order_id not in self._orders:
            raise ValueError(f"Order not found: {order_id}")
        return self._orders[order_id]
    
    def get_order_history(self) -> List[Order]:
        """Get all orders."""
        return list(self._orders.values())
    
    # ==================== Position Management ====================
    
    def get_positions(self) -> List[Position]:
        """Get current positions."""
        return list(self._positions.values())
    
    def get_holdings(self) -> List[Holding]:
        """Get holdings (delivery positions)."""
        return list(self._holdings.values())
    
    def convert_position(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        from_product: str,
        to_product: str
    ) -> bool:
        """Convert position product type."""
        if symbol not in self._positions:
            logger.warning(f"Position not found: {symbol}")
            return False
        
        pos = self._positions[symbol]
        pos.product_type = to_product
        logger.info(f"Position {symbol} converted from {from_product} to {to_product}")
        return True
    
    def square_off_position(
        self,
        symbol: str,
        exchange: str,
        product_type: str,
        quantity: Optional[int] = None
    ) -> str:
        """Square off a position."""
        if symbol not in self._positions:
            raise ValueError(f"Position not found: {symbol}")
        
        pos = self._positions[symbol]
        sq_qty = quantity if quantity else abs(pos.quantity)
        
        # Determine transaction type (opposite of position)
        transaction_type = "SELL" if pos.quantity > 0 else "BUY"
        
        return self.place_order(
            symbol=symbol,
            exchange=exchange,
            transaction_type=transaction_type,
            quantity=sq_qty,
            order_type="MARKET",
            product_type=product_type
        )
    
    # ==================== Account Information ====================
    
    def get_margin(self) -> Dict[str, float]:
        """Get margin information."""
        used_margin = self._calculate_used_margin()
        unrealized_pnl = sum(pos.pnl for pos in self._positions.values())
        
        return {
            'available_margin': self._cash,
            'used_margin': used_margin,
            'total_margin': self._cash + used_margin,
            'unrealized_pnl': unrealized_pnl,
            'collateral': 0.0,
        }
    
    def _calculate_used_margin(self) -> float:
        """Calculate margin used by positions."""
        margin = 0.0
        margin_rate = 0.15  # 15% margin for options
        
        for pos in self._positions.values():
            margin += abs(pos.quantity) * pos.average_price * margin_rate
        
        return margin
    
    def get_rms_limits(self) -> Dict[str, Any]:
        """Get RMS limits."""
        return {
            'max_position_size': self._initial_capital * 0.10,  # 10% per position
            'daily_loss_limit': self._initial_capital * 0.05,  # 5% daily loss
            'max_orders_per_day': 100,
        }
    
    # ==================== Paper Trading Specific ====================
    
    def get_portfolio_value(self) -> float:
        """Get total portfolio value."""
        positions_value = sum(
            pos.quantity * pos.last_price for pos in self._positions.values()
        )
        return self._cash + positions_value
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get paper trading statistics."""
        portfolio_value = self.get_portfolio_value()
        total_pnl = portfolio_value - self._initial_capital
        
        return {
            'initial_capital': self._initial_capital,
            'current_cash': self._cash,
            'portfolio_value': portfolio_value,
            'total_pnl': total_pnl,
            'total_pnl_pct': (total_pnl / self._initial_capital) * 100,
            'total_orders': self._total_orders,
            'total_trades': self._total_trades,
            'total_commission': self._total_commission,
            'open_positions': len(self._positions),
        }
    
    def reset(self) -> None:
        """Reset paper trading state."""
        self._cash = self._initial_capital
        self._positions.clear()
        self._holdings.clear()
        self._orders.clear()
        self._order_history.clear()
        self._market_prices.clear()
        self._total_orders = 0
        self._total_trades = 0
        self._total_commission = 0.0
        
        logger.info("Paper broker reset")
    
    def simulate_tick(self, symbol: str, price_change_pct: float = 0.001) -> None:
        """
        Simulate a market tick for testing.
        
        Args:
            symbol: Symbol to update
            price_change_pct: Random price change range (default ±0.1%)
        """
        current_price = self._market_prices.get(symbol, 100.0)
        change = current_price * random.uniform(-price_change_pct, price_change_pct)
        new_price = max(0.01, current_price + change)
        self.set_price(symbol, new_price)


# Register paper broker with factory
BrokerFactory.register('paper', PaperBroker)
