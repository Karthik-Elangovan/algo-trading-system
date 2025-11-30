"""
Paper Trading Broker Implementation.

A simulated broker for testing strategies without real money.
"""

import logging
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from .broker import (
    BaseBroker,
    BrokerFactory,
    Order,
    Position,
    Holding,
    Quote,
    AccountInfo,
)
from .utils import (
    generate_order_id,
    calculate_slippage,
    calculate_transaction_costs,
    validate_order_params,
)

logger = logging.getLogger(__name__)


class PaperBroker(BaseBroker):
    """Paper trading broker for backtesting and simulation."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._initial_capital = config.get('initial_capital', 1_000_000) if config else 1_000_000
        self._slippage_pct = config.get('slippage_pct', 0.005) if config else 0.005
        self._brokerage_per_order = config.get('brokerage_per_order', 20) if config else 20
        self._cash = self._initial_capital
        self._positions: Dict[str, Position] = {}
        self._holdings: Dict[str, Holding] = {}
        self._orders: Dict[str, Order] = {}
        self._order_history: List[Order] = []
        self._market_prices: Dict[str, float] = {}
        self._total_orders = 0
        self._total_trades = 0
        self._total_commission = 0.0
        logger.info(f"Initialized PaperBroker with capital: {self._initial_capital}")
    
    def login(self) -> bool:
        self._is_authenticated = True
        return True
    
    def logout(self) -> bool:
        self._is_authenticated = False
        return True
    
    def get_profile(self) -> AccountInfo:
        return AccountInfo(
            client_id="PAPER001",
            name="Paper Trading Account",
            email="paper@trading.com",
            broker="Paper",
            available_margin=self._cash,
            used_margin=self._calculate_used_margin(),
            total_margin=self._initial_capital,
        )
    
    def get_ltp(self, symbol: str, exchange: str) -> float:
        return self._market_prices.get(symbol, 0.0)
    
    def set_price(self, symbol: str, price: float) -> None:
        self._market_prices[symbol] = price
        if symbol in self._positions:
            self._positions[symbol].last_price = price
            self._update_position_pnl(symbol)
    
    def get_quote(self, symbol: str, exchange: str) -> Quote:
        price = self._market_prices.get(symbol, 100.0)
        spread = price * 0.001
        return Quote(
            symbol=symbol, exchange=exchange, ltp=price,
            open=price * 0.99, high=price * 1.01, low=price * 0.98, close=price,
            volume=random.randint(10000, 100000),
            bid_price=price - spread / 2, ask_price=price + spread / 2,
            bid_quantity=random.randint(100, 1000), ask_quantity=random.randint(100, 1000),
        )
    
    def get_historical_data(self, symbol: str, exchange: str, interval: str,
                           from_date: datetime, to_date: datetime) -> List[Dict[str, Any]]:
        return []
    
    def place_order(self, symbol: str, exchange: str, transaction_type: str, quantity: int,
                   order_type: str = "MARKET", product_type: str = "INTRADAY",
                   price: float = 0.0, trigger_price: float = 0.0, variety: str = "NORMAL") -> str:
        is_valid, error_msg = validate_order_params(
            symbol, exchange, transaction_type, quantity, order_type, product_type, price, trigger_price
        )
        if not is_valid:
            raise ValueError(error_msg)
        
        order_id = generate_order_id()
        self._total_orders += 1
        market_price = self._market_prices.get(symbol, price if price > 0 else 100.0)
        
        if order_type.upper() == "MARKET":
            exec_price = calculate_slippage(market_price, transaction_type, self._slippage_pct)
        else:
            exec_price = price if price > 0 else trigger_price
        
        order = Order(
            order_id=order_id, symbol=symbol, exchange=exchange,
            transaction_type=transaction_type.upper(), quantity=quantity,
            order_type=order_type.upper(), product_type=product_type.upper(),
            price=price, trigger_price=trigger_price, status="pending", variety=variety,
        )
        self._orders[order_id] = order
        
        if order_type.upper() == "MARKET":
            self._execute_order(order_id, exec_price)
        else:
            can_execute = self._check_limit_order(order, market_price)
            if can_execute:
                self._execute_order(order_id, exec_price)
            else:
                order.status = "open"
        
        self._order_history.append(order)
        return order_id
    
    def _execute_order(self, order_id: str, exec_price: float) -> None:
        order = self._orders.get(order_id)
        if not order:
            return
        
        value = exec_price * order.quantity
        costs = calculate_transaction_costs(value, is_sell=(order.transaction_type == "SELL"),
                                           brokerage=self._brokerage_per_order)
        self._total_commission += costs['total']
        
        if order.transaction_type == "BUY":
            total_cost = value + costs['total']
            if total_cost > self._cash:
                order.status = "rejected"
                order.message = "Insufficient funds"
                return
            self._cash -= total_cost
        else:
            self._cash += value - costs['total']
        
        order.status = "complete"
        order.filled_quantity = order.quantity
        order.average_price = exec_price
        order.updated_at = datetime.now()
        self._update_position(order, exec_price)
        self._total_trades += 1
    
    def _check_limit_order(self, order: Order, market_price: float) -> bool:
        if order.order_type == "LIMIT":
            if order.transaction_type == "BUY" and market_price <= order.price:
                return True
            if order.transaction_type == "SELL" and market_price >= order.price:
                return True
        return False
    
    def _update_position(self, order: Order, exec_price: float) -> None:
        symbol = order.symbol
        qty = order.quantity
        
        if symbol in self._positions:
            pos = self._positions[symbol]
            if order.transaction_type == "BUY":
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
                pos.quantity -= qty
                pos.day_sell_quantity += qty
                pos.day_sell_value += exec_price * qty
            pos.last_price = exec_price
            self._update_position_pnl(symbol)
            if pos.quantity == 0:
                del self._positions[symbol]
        else:
            direction = 1 if order.transaction_type == "BUY" else -1
            self._positions[symbol] = Position(
                symbol=symbol, exchange=order.exchange, product_type=order.product_type,
                quantity=qty * direction, average_price=exec_price, last_price=exec_price, pnl=0.0,
                day_buy_quantity=qty if direction > 0 else 0,
                day_sell_quantity=qty if direction < 0 else 0,
                day_buy_value=exec_price * qty if direction > 0 else 0,
                day_sell_value=exec_price * qty if direction < 0 else 0,
            )
    
    def _update_position_pnl(self, symbol: str) -> None:
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
    
    def modify_order(self, order_id: str, quantity: Optional[int] = None, price: Optional[float] = None,
                    trigger_price: Optional[float] = None, order_type: Optional[str] = None) -> bool:
        if order_id not in self._orders:
            return False
        order = self._orders[order_id]
        if order.status not in ["pending", "open"]:
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
        return True
    
    def cancel_order(self, order_id: str, variety: str = "NORMAL") -> bool:
        if order_id not in self._orders:
            return False
        order = self._orders[order_id]
        if order.status not in ["pending", "open"]:
            return False
        order.status = "cancelled"
        order.updated_at = datetime.now()
        return True
    
    def get_order_status(self, order_id: str) -> Order:
        if order_id not in self._orders:
            raise ValueError(f"Order not found: {order_id}")
        return self._orders[order_id]
    
    def get_order_history(self) -> List[Order]:
        return list(self._orders.values())
    
    def get_positions(self) -> List[Position]:
        return list(self._positions.values())
    
    def get_holdings(self) -> List[Holding]:
        return list(self._holdings.values())
    
    def convert_position(self, symbol: str, exchange: str, transaction_type: str,
                        quantity: int, from_product: str, to_product: str) -> bool:
        if symbol not in self._positions:
            return False
        pos = self._positions[symbol]
        pos.product_type = to_product
        return True
    
    def square_off_position(self, symbol: str, exchange: str, product_type: str,
                           quantity: Optional[int] = None) -> str:
        if symbol not in self._positions:
            raise ValueError(f"Position not found: {symbol}")
        pos = self._positions[symbol]
        sq_qty = quantity if quantity else abs(pos.quantity)
        transaction_type = "SELL" if pos.quantity > 0 else "BUY"
        return self.place_order(symbol=symbol, exchange=exchange, transaction_type=transaction_type,
                               quantity=sq_qty, order_type="MARKET", product_type=product_type)
    
    def get_margin(self) -> Dict[str, float]:
        used_margin = self._calculate_used_margin()
        unrealized_pnl = sum(pos.pnl for pos in self._positions.values())
        return {
            'available_margin': self._cash, 'used_margin': used_margin,
            'total_margin': self._cash + used_margin, 'unrealized_pnl': unrealized_pnl, 'collateral': 0.0,
        }
    
    def _calculate_used_margin(self) -> float:
        margin = 0.0
        margin_rate = 0.15
        for pos in self._positions.values():
            margin += abs(pos.quantity) * pos.average_price * margin_rate
        return margin
    
    def get_rms_limits(self) -> Dict[str, Any]:
        return {
            'max_position_size': self._initial_capital * 0.10,
            'daily_loss_limit': self._initial_capital * 0.05,
            'max_orders_per_day': 100,
        }
    
    def get_portfolio_value(self) -> float:
        positions_value = sum(pos.quantity * pos.last_price for pos in self._positions.values())
        return self._cash + positions_value
    
    def get_statistics(self) -> Dict[str, Any]:
        portfolio_value = self.get_portfolio_value()
        total_pnl = portfolio_value - self._initial_capital
        return {
            'initial_capital': self._initial_capital, 'current_cash': self._cash,
            'portfolio_value': portfolio_value, 'total_pnl': total_pnl,
            'total_pnl_pct': (total_pnl / self._initial_capital) * 100,
            'total_orders': self._total_orders, 'total_trades': self._total_trades,
            'total_commission': self._total_commission, 'open_positions': len(self._positions),
        }
    
    def reset(self) -> None:
        self._cash = self._initial_capital
        self._positions.clear()
        self._holdings.clear()
        self._orders.clear()
        self._order_history.clear()
        self._market_prices.clear()
        self._total_orders = 0
        self._total_trades = 0
        self._total_commission = 0.0


# Register paper broker with factory
BrokerFactory.register('paper', PaperBroker)
