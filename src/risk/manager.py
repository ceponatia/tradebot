from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from src.utils.logger import get_logger
from src.config import TradingConfig
from src.strategies.signal_processor import Signal


class PositionStatus(Enum):
    NONE = "NONE"
    OPEN = "OPEN"
    CLOSING = "CLOSING"


@dataclass
class Position:
    entry_price: float
    size: float
    entry_time: datetime
    status: PositionStatus
    stop_loss: float
    take_profit: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


class RiskManager:
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = get_logger("RiskManager", config.log_level, config.log_file)
        
        # Portfolio state
        self.balance: float = 0.0
        self.available_balance: float = 0.0
        self.current_position: Optional[Position] = None
        
        # Trading history
        self.trade_history: list = []
        self.last_trade_time: Optional[datetime] = None
        
        # Risk metrics
        self.total_pnl: float = 0.0
        self.win_rate: float = 0.0
        self.max_drawdown: float = 0.0
        self.peak_balance: float = 0.0
    
    def can_trade(self, signal: Signal, current_price: float) -> Tuple[bool, str]:
        """Check if trading is allowed based on risk rules."""
        # Check trading mode
        if self.config.trading_mode not in ["paper", "live"]:
            return True, "Test mode - trading allowed"
        
        # Check cooldown period
        if not self._check_cooldown():
            time_remaining = self._get_cooldown_remaining()
            return False, f"Cooldown period active: {time_remaining}s remaining"
        
        # Check if we have a position
        if signal == Signal.BUY and self.current_position:
            return False, "Already have an open position"
        
        if signal == Signal.SELL and not self.current_position:
            return False, "No position to sell"
        
        # Check minimum order size
        if signal == Signal.BUY:
            position_size = self._calculate_position_size(current_price)
            if position_size * current_price < self.config.min_order_size:
                return False, f"Position size below minimum: ${position_size * current_price:.2f}"
        
        # Check available balance
        if signal == Signal.BUY and self.available_balance < self.config.min_order_size:
            return False, f"Insufficient balance: ${self.available_balance:.2f}"
        
        return True, "Trade allowed"
    
    def calculate_order_details(self, signal: Signal, current_price: float, 
                              signal_strength: float = 1.0) -> Dict:
        """Calculate order size and risk parameters."""
        if signal == Signal.BUY:
            # Calculate position size
            base_size = self._calculate_position_size(current_price)
            
            # Adjust size based on signal strength
            adjusted_size = base_size * signal_strength
            
            # Calculate risk levels
            stop_loss = current_price * (1 - self.config.stop_loss_percentage / 100)
            take_profit = current_price * (1 + self.config.take_profit_percentage / 100)
            
            return {
                'side': 'buy',
                'size': adjusted_size,
                'value': adjusted_size * current_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'risk_amount': adjusted_size * (current_price - stop_loss),
                'potential_profit': adjusted_size * (take_profit - current_price)
            }
        
        elif signal == Signal.SELL and self.current_position:
            return {
                'side': 'sell',
                'size': self.current_position.size,
                'value': self.current_position.size * current_price,
                'entry_price': self.current_position.entry_price,
                'exit_price': current_price,
                'pnl': self.current_position.size * (current_price - self.current_position.entry_price)
            }
        
        return {}
    
    def open_position(self, entry_price: float, size: float, stop_loss: float, 
                     take_profit: float):
        """Open a new position."""
        self.current_position = Position(
            entry_price=entry_price,
            size=size,
            entry_time=datetime.utcnow(),
            status=PositionStatus.OPEN,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        # Update balance
        position_value = size * entry_price
        self.available_balance -= position_value
        
        self.logger.info("Position opened",
                        entry_price=entry_price,
                        size=size,
                        value=position_value,
                        stop_loss=stop_loss,
                        take_profit=take_profit)
        
        # Record trade
        self.last_trade_time = datetime.utcnow()
        self.trade_history.append({
            'timestamp': self.last_trade_time,
            'type': 'open',
            'price': entry_price,
            'size': size,
            'value': position_value
        })
    
    def close_position(self, exit_price: float):
        """Close current position."""
        if not self.current_position:
            self.logger.error("No position to close")
            return
        
        # Calculate PnL
        pnl = self.current_position.size * (exit_price - self.current_position.entry_price)
        self.current_position.realized_pnl = pnl
        self.total_pnl += pnl
        
        # Update balance
        position_value = self.current_position.size * exit_price
        self.balance += pnl
        self.available_balance = self.balance
        
        # Update peak balance for drawdown calculation
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        
        self.logger.info("Position closed",
                        exit_price=exit_price,
                        entry_price=self.current_position.entry_price,
                        size=self.current_position.size,
                        pnl=pnl,
                        total_pnl=self.total_pnl)
        
        # Record trade
        self.last_trade_time = datetime.utcnow()
        self.trade_history.append({
            'timestamp': self.last_trade_time,
            'type': 'close',
            'price': exit_price,
            'size': self.current_position.size,
            'pnl': pnl
        })
        
        # Clear position
        self.current_position = None
        
        # Update metrics
        self._update_metrics()
    
    def update_position(self, current_price: float) -> Optional[Signal]:
        """Update position and check for stop loss/take profit."""
        if not self.current_position:
            return None
        
        # Update unrealized PnL
        self.current_position.unrealized_pnl = (
            self.current_position.size * (current_price - self.current_position.entry_price)
        )
        
        # Check stop loss
        if current_price <= self.current_position.stop_loss:
            self.logger.warning("Stop loss triggered", 
                              current_price=current_price,
                              stop_loss=self.current_position.stop_loss)
            return Signal.SELL
        
        # Check take profit
        if current_price >= self.current_position.take_profit:
            self.logger.info("Take profit triggered",
                           current_price=current_price,
                           take_profit=self.current_position.take_profit)
            return Signal.SELL
        
        return None
    
    def set_balance(self, balance: float):
        """Set account balance."""
        self.balance = balance
        self.available_balance = balance
        self.peak_balance = balance
        self.logger.info("Balance set", balance=balance)
    
    def _calculate_position_size(self, current_price: float) -> float:
        """Calculate position size based on risk management rules."""
        # Use configured max position size percentage
        position_value = self.available_balance * self.config.max_position_size
        position_size = position_value / current_price
        
        return position_size
    
    def _check_cooldown(self) -> bool:
        """Check if cooldown period has passed."""
        if not self.last_trade_time:
            return True
        
        time_since_trade = (datetime.utcnow() - self.last_trade_time).total_seconds()
        return time_since_trade >= self.config.cooldown_period
    
    def _get_cooldown_remaining(self) -> int:
        """Get remaining cooldown time in seconds."""
        if not self.last_trade_time:
            return 0
        
        time_since_trade = (datetime.utcnow() - self.last_trade_time).total_seconds()
        remaining = max(0, self.config.cooldown_period - time_since_trade)
        return int(remaining)
    
    def _update_metrics(self):
        """Update trading metrics."""
        # Calculate win rate
        winning_trades = [t for t in self.trade_history 
                         if t.get('type') == 'close' and t.get('pnl', 0) > 0]
        losing_trades = [t for t in self.trade_history 
                        if t.get('type') == 'close' and t.get('pnl', 0) <= 0]
        
        total_closed = len(winning_trades) + len(losing_trades)
        if total_closed > 0:
            self.win_rate = len(winning_trades) / total_closed
        
        # Calculate max drawdown
        if self.peak_balance > 0:
            current_drawdown = (self.peak_balance - self.balance) / self.peak_balance
            self.max_drawdown = max(self.max_drawdown, current_drawdown)
    
    def get_metrics(self) -> Dict:
        """Get current risk metrics."""
        return {
            'balance': self.balance,
            'available_balance': self.available_balance,
            'total_pnl': self.total_pnl,
            'win_rate': self.win_rate,
            'max_drawdown': self.max_drawdown,
            'total_trades': len([t for t in self.trade_history if t.get('type') == 'close']),
            'open_position': self.current_position is not None,
            'position_pnl': self.current_position.unrealized_pnl if self.current_position else 0
        }