import asyncio
from typing import Dict, Optional, List
from datetime import datetime
from coinbase.rest import RESTClient
from dataclasses import dataclass
from enum import Enum

from src.utils.logger import get_logger
from src.config import TradingConfig
from src.strategies.signal_processor import Signal
from src.risk.manager import RiskManager


class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@dataclass
class Order:
    order_id: str
    side: str
    size: float
    price: Optional[float]
    status: OrderStatus
    created_at: datetime
    filled_at: Optional[datetime] = None
    filled_price: Optional[float] = None
    filled_size: Optional[float] = None
    error_message: Optional[str] = None


class ExecutionEngine:
    def __init__(self, config: TradingConfig, risk_manager: RiskManager):
        self.config = config
        self.risk_manager = risk_manager
        self.logger = get_logger("ExecutionEngine", config.log_level, config.log_file)
        
        # Initialize Coinbase client
        self.client = RESTClient(
            api_key=config.api_name,
            api_secret=config.api_key
        )
        
        # Order tracking
        self.pending_orders: Dict[str, Order] = {}
        self.order_history: List[Order] = []
        
        # Execution stats
        self.total_orders = 0
        self.successful_orders = 0
        self.failed_orders = 0
    
    async def initialize(self):
        """Initialize execution engine and fetch account info."""
        try:
            # Fetch account information
            accounts = self.client.get_accounts()
            
            # Find USD account for balance
            usd_balance = 0.0
            for account in accounts.accounts:
                if account.currency == "USD":
                    usd_balance = float(account.available_balance.value)
                    break
            
            # Update risk manager with actual balance
            self.risk_manager.set_balance(usd_balance)
            
            self.logger.info("Execution engine initialized", 
                           mode=self.config.trading_mode,
                           balance=usd_balance)
            
        except Exception as e:
            self.logger.error("Failed to initialize execution engine", error=str(e))
            raise
    
    async def execute_signal(self, signal: Signal, current_price: float, 
                           signal_strength: float = 1.0) -> Optional[Order]:
        """Execute trading signal."""
        # Check if we can trade
        can_trade, reason = self.risk_manager.can_trade(signal, current_price)
        if not can_trade:
            self.logger.info("Trade rejected by risk manager", 
                           signal=signal.value,
                           reason=reason)
            return None
        
        # Get order details from risk manager
        order_details = self.risk_manager.calculate_order_details(
            signal, current_price, signal_strength
        )
        
        if not order_details:
            self.logger.warning("No order details calculated", signal=signal.value)
            return None
        
        # Execute based on trading mode
        if self.config.trading_mode == "test":
            return await self._execute_test_order(signal, order_details, current_price)
        elif self.config.trading_mode == "paper":
            return await self._execute_paper_order(signal, order_details, current_price)
        else:  # live
            return await self._execute_live_order(signal, order_details, current_price)
    
    async def _execute_test_order(self, signal: Signal, order_details: Dict, 
                                current_price: float) -> Order:
        """Execute order in test mode (instant fill)."""
        order = Order(
            order_id=f"TEST-{self.total_orders}",
            side=order_details['side'],
            size=order_details['size'],
            price=current_price,
            status=OrderStatus.FILLED,
            created_at=datetime.utcnow(),
            filled_at=datetime.utcnow(),
            filled_price=current_price,
            filled_size=order_details['size']
        )
        
        self.logger.info("Test order executed",
                        order_id=order.order_id,
                        side=order.side,
                        size=order.size,
                        price=current_price)
        
        # Update position in risk manager
        if signal == Signal.BUY:
            self.risk_manager.open_position(
                current_price,
                order_details['size'],
                order_details['stop_loss'],
                order_details['take_profit']
            )
        else:
            self.risk_manager.close_position(current_price)
        
        self.total_orders += 1
        self.successful_orders += 1
        self.order_history.append(order)
        
        return order
    
    async def _execute_paper_order(self, signal: Signal, order_details: Dict, 
                                 current_price: float) -> Order:
        """Execute order in paper trading mode."""
        # Simulate order placement with slight delay
        await asyncio.sleep(0.5)
        
        order = Order(
            order_id=f"PAPER-{self.total_orders}",
            side=order_details['side'],
            size=order_details['size'],
            price=current_price,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        self.pending_orders[order.order_id] = order
        
        # Simulate order fill after brief delay
        await asyncio.sleep(1.0)
        
        # Simulate realistic fill
        fill_price = current_price * (1 + (0.001 if signal == Signal.BUY else -0.001))
        
        order.status = OrderStatus.FILLED
        order.filled_at = datetime.utcnow()
        order.filled_price = fill_price
        order.filled_size = order_details['size']
        
        self.logger.info("Paper order filled",
                        order_id=order.order_id,
                        side=order.side,
                        size=order.size,
                        fill_price=fill_price)
        
        # Update position in risk manager
        if signal == Signal.BUY:
            self.risk_manager.open_position(
                fill_price,
                order_details['size'],
                order_details['stop_loss'],
                order_details['take_profit']
            )
        else:
            self.risk_manager.close_position(fill_price)
        
        del self.pending_orders[order.order_id]
        self.total_orders += 1
        self.successful_orders += 1
        self.order_history.append(order)
        
        return order
    
    async def _execute_live_order(self, signal: Signal, order_details: Dict, 
                                current_price: float) -> Optional[Order]:
        """Execute real order on Coinbase."""
        try:
            # Prepare order configuration
            if self.config.order_type == "market":
                if signal == Signal.BUY:
                    # Market buy order (specify quote size in USD)
                    order_config = {
                        "client_order_id": f"BOT-{self.total_orders}",
                        "product_id": self.config.trading_pair,
                        "side": "BUY",
                        "order_configuration": {
                            "market_market_ioc": {
                                "quote_size": str(order_details['value'])
                            }
                        }
                    }
                else:
                    # Market sell order (specify base size)
                    order_config = {
                        "client_order_id": f"BOT-{self.total_orders}",
                        "product_id": self.config.trading_pair,
                        "side": "SELL",
                        "order_configuration": {
                            "market_market_ioc": {
                                "base_size": str(order_details['size'])
                            }
                        }
                    }
            else:
                # Limit order
                limit_price = current_price * (0.999 if signal == Signal.BUY else 1.001)
                order_config = {
                    "client_order_id": f"BOT-{self.total_orders}",
                    "product_id": self.config.trading_pair,
                    "side": "BUY" if signal == Signal.BUY else "SELL",
                    "order_configuration": {
                        "limit_limit_gtc": {
                            "base_size": str(order_details['size']),
                            "limit_price": str(limit_price)
                        }
                    }
                }
            
            # Place order
            self.logger.info("Placing live order", order_config=order_config)
            response = self.client.create_order(**order_config)
            
            if response and hasattr(response, 'order_id'):
                order = Order(
                    order_id=response.order_id,
                    side=order_details['side'],
                    size=order_details['size'],
                    price=current_price,
                    status=OrderStatus.PENDING,
                    created_at=datetime.utcnow()
                )
                
                self.pending_orders[order.order_id] = order
                
                # Wait for order to fill (with timeout)
                filled_order = await self._wait_for_fill(order.order_id, timeout=30)
                
                if filled_order and filled_order.status == OrderStatus.FILLED:
                    # Update position in risk manager
                    if signal == Signal.BUY:
                        self.risk_manager.open_position(
                            filled_order.filled_price,
                            filled_order.filled_size,
                            order_details['stop_loss'],
                            order_details['take_profit']
                        )
                    else:
                        self.risk_manager.close_position(filled_order.filled_price)
                    
                    self.successful_orders += 1
                else:
                    self.failed_orders += 1
                
                self.total_orders += 1
                self.order_history.append(filled_order)
                return filled_order
            
        except Exception as e:
            self.logger.error("Failed to execute live order", 
                            error=str(e),
                            signal=signal.value)
            self.failed_orders += 1
            return None
    
    async def _wait_for_fill(self, order_id: str, timeout: int = 30) -> Optional[Order]:
        """Wait for order to be filled."""
        start_time = datetime.utcnow()
        order = self.pending_orders.get(order_id)
        
        while order and (datetime.utcnow() - start_time).total_seconds() < timeout:
            try:
                # Check order status
                response = self.client.get_order(order_id)
                
                if response and hasattr(response, 'order'):
                    api_order = response.order
                    
                    if api_order.status == "FILLED":
                        order.status = OrderStatus.FILLED
                        order.filled_at = datetime.utcnow()
                        order.filled_price = float(api_order.average_filled_price)
                        order.filled_size = float(api_order.filled_size)
                        
                        self.logger.info("Order filled",
                                       order_id=order_id,
                                       filled_price=order.filled_price,
                                       filled_size=order.filled_size)
                        
                        del self.pending_orders[order_id]
                        return order
                    
                    elif api_order.status in ["CANCELLED", "EXPIRED"]:
                        order.status = OrderStatus.CANCELLED
                        order.error_message = f"Order {api_order.status}"
                        del self.pending_orders[order_id]
                        return order
                
            except Exception as e:
                self.logger.error("Error checking order status", 
                                order_id=order_id,
                                error=str(e))
            
            await asyncio.sleep(1)
        
        # Timeout - cancel order
        if order:
            try:
                self.client.cancel_orders([order_id])
                order.status = OrderStatus.CANCELLED
                order.error_message = "Order timeout"
            except:
                pass
            
            del self.pending_orders[order_id]
        
        return order
    
    async def check_pending_orders(self):
        """Check status of all pending orders."""
        for order_id in list(self.pending_orders.keys()):
            await self._wait_for_fill(order_id, timeout=1)
    
    def get_execution_stats(self) -> Dict:
        """Get execution statistics."""
        return {
            'total_orders': self.total_orders,
            'successful_orders': self.successful_orders,
            'failed_orders': self.failed_orders,
            'pending_orders': len(self.pending_orders),
            'success_rate': self.successful_orders / self.total_orders if self.total_orders > 0 else 0
        }