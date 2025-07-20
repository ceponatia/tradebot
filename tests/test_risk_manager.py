import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from src.risk.manager import RiskManager, Position, PositionStatus
from src.strategies.signal_processor import Signal


class TestRiskManager:
    """Test the RiskManager class."""
    
    def test_initialization(self, test_config):
        """Test risk manager initialization."""
        risk_manager = RiskManager(test_config)
        
        assert risk_manager.config == test_config
        assert risk_manager.balance == 0.0
        assert risk_manager.available_balance == 0.0
        assert risk_manager.current_position is None
        assert risk_manager.trade_history == []
        assert risk_manager.total_pnl == 0.0
    
    def test_set_balance(self, test_config):
        """Test setting account balance."""
        risk_manager = RiskManager(test_config)
        
        risk_manager.set_balance(10000.0)
        
        assert risk_manager.balance == 10000.0
        assert risk_manager.available_balance == 10000.0
        assert risk_manager.peak_balance == 10000.0


class TestCanTrade:
    """Test the can_trade method."""
    
    def test_can_trade_test_mode(self, test_config):
        """Test trading allowance in test mode."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        can_trade, reason = risk_manager.can_trade(Signal.BUY, 50000.0)
        
        assert can_trade is True
        assert "Test mode" in reason
    
    def test_can_trade_paper_mode(self, test_config):
        """Test trading allowance in paper mode."""
        test_config.trading_mode = "paper"
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        can_trade, reason = risk_manager.can_trade(Signal.BUY, 50000.0)
        
        assert can_trade is True
        assert reason == "Trade allowed"
    
    def test_cannot_trade_cooldown(self, test_config):
        """Test trading blocked during cooldown period."""
        test_config.trading_mode = "paper"
        test_config.cooldown_period = 300  # 5 minutes
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Set last trade time to recent
        risk_manager.last_trade_time = datetime.utcnow() - timedelta(seconds=100)
        
        can_trade, reason = risk_manager.can_trade(Signal.BUY, 50000.0)
        
        assert can_trade is False
        assert "Cooldown period active" in reason
    
    def test_cannot_buy_with_position(self, test_config):
        """Test cannot buy when already holding position."""
        test_config.trading_mode = "paper"
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Create existing position
        risk_manager.current_position = Position(
            entry_price=50000.0,
            size=0.002,
            entry_time=datetime.utcnow(),
            status=PositionStatus.OPEN,
            stop_loss=49000.0,
            take_profit=52500.0
        )
        
        can_trade, reason = risk_manager.can_trade(Signal.BUY, 50000.0)
        
        assert can_trade is False
        assert "Already have an open position" in reason
    
    def test_cannot_sell_without_position(self, test_config):
        """Test cannot sell when no position is held."""
        test_config.trading_mode = "paper"
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        can_trade, reason = risk_manager.can_trade(Signal.SELL, 50000.0)
        
        assert can_trade is False
        assert "No position to sell" in reason
    
    def test_insufficient_balance(self, test_config):
        """Test trading blocked due to insufficient balance."""
        test_config.trading_mode = "paper"
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(5.0)  # Very low balance
        
        can_trade, reason = risk_manager.can_trade(Signal.BUY, 50000.0)
        
        assert can_trade is False
        assert "Insufficient balance" in reason
    
    def test_position_size_below_minimum(self, test_config):
        """Test trading blocked when position size below minimum."""
        test_config.trading_mode = "paper"
        test_config.min_order_size = 100.0
        test_config.max_position_size = 0.001  # Very small position
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(1000.0)
        
        can_trade, reason = risk_manager.can_trade(Signal.BUY, 50000.0)
        
        assert can_trade is False
        assert "Position size below minimum" in reason


class TestOrderCalculations:
    """Test order detail calculations."""
    
    def test_calculate_buy_order(self, test_config):
        """Test buy order calculation."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        order_details = risk_manager.calculate_order_details(Signal.BUY, 50000.0, 1.0)
        
        assert order_details['side'] == 'buy'
        assert order_details['size'] > 0
        assert order_details['value'] == order_details['size'] * 50000.0
        assert order_details['stop_loss'] < 50000.0
        assert order_details['take_profit'] > 50000.0
        assert 'risk_amount' in order_details
        assert 'potential_profit' in order_details
    
    def test_calculate_sell_order(self, test_config):
        """Test sell order calculation."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Create position first
        risk_manager.current_position = Position(
            entry_price=50000.0,
            size=0.002,
            entry_time=datetime.utcnow(),
            status=PositionStatus.OPEN,
            stop_loss=49000.0,
            take_profit=52500.0
        )
        
        order_details = risk_manager.calculate_order_details(Signal.SELL, 51000.0)
        
        assert order_details['side'] == 'sell'
        assert order_details['size'] == 0.002
        assert order_details['entry_price'] == 50000.0
        assert order_details['exit_price'] == 51000.0
        assert order_details['pnl'] > 0  # Profitable trade
    
    def test_position_sizing(self, test_config):
        """Test position sizing calculation."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Test with different position size percentages
        position_size = risk_manager._calculate_position_size(50000.0)
        expected_value = 10000.0 * test_config.max_position_size
        expected_size = expected_value / 50000.0
        
        assert abs(position_size - expected_size) < 1e-8
    
    def test_signal_strength_adjustment(self, test_config):
        """Test position size adjustment based on signal strength."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Strong signal (100%)
        strong_order = risk_manager.calculate_order_details(Signal.BUY, 50000.0, 1.0)
        
        # Weak signal (50%)
        weak_order = risk_manager.calculate_order_details(Signal.BUY, 50000.0, 0.5)
        
        assert weak_order['size'] == strong_order['size'] * 0.5
        assert weak_order['value'] == strong_order['value'] * 0.5


class TestPositionManagement:
    """Test position opening and closing."""
    
    def test_open_position(self, test_config):
        """Test opening a new position."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        entry_price = 50000.0
        size = 0.002
        stop_loss = 49000.0
        take_profit = 52500.0
        
        risk_manager.open_position(entry_price, size, stop_loss, take_profit)
        
        assert risk_manager.current_position is not None
        assert risk_manager.current_position.entry_price == entry_price
        assert risk_manager.current_position.size == size
        assert risk_manager.current_position.stop_loss == stop_loss
        assert risk_manager.current_position.take_profit == take_profit
        assert risk_manager.current_position.status == PositionStatus.OPEN
        
        # Check balance update
        position_value = size * entry_price
        assert risk_manager.available_balance == 10000.0 - position_value
        
        # Check trade history
        assert len(risk_manager.trade_history) == 1
        assert risk_manager.trade_history[0]['type'] == 'open'
    
    def test_close_position_profit(self, test_config):
        """Test closing a profitable position."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Open position first
        risk_manager.open_position(50000.0, 0.002, 49000.0, 52500.0)
        initial_balance = risk_manager.balance
        
        # Close at profit
        exit_price = 51000.0
        risk_manager.close_position(exit_price)
        
        assert risk_manager.current_position is None
        
        # Check PnL calculation
        expected_pnl = 0.002 * (51000.0 - 50000.0)
        assert abs(risk_manager.total_pnl - expected_pnl) < 1e-8
        assert risk_manager.balance > initial_balance
        
        # Check trade history
        assert len(risk_manager.trade_history) == 2
        assert risk_manager.trade_history[1]['type'] == 'close'
        assert risk_manager.trade_history[1]['pnl'] > 0
    
    def test_close_position_loss(self, test_config):
        """Test closing a losing position."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Open position first
        risk_manager.open_position(50000.0, 0.002, 49000.0, 52500.0)
        initial_balance = risk_manager.balance
        
        # Close at loss
        exit_price = 49500.0
        risk_manager.close_position(exit_price)
        
        assert risk_manager.current_position is None
        
        # Check PnL calculation
        expected_pnl = 0.002 * (49500.0 - 50000.0)
        assert abs(risk_manager.total_pnl - expected_pnl) < 1e-8
        assert risk_manager.balance < initial_balance
        
        # Check trade history
        assert risk_manager.trade_history[1]['pnl'] < 0


class TestPositionUpdates:
    """Test position updates and stop-loss/take-profit triggers."""
    
    def test_update_position_normal(self, test_config):
        """Test normal position update."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Open position
        risk_manager.open_position(50000.0, 0.002, 49000.0, 52500.0)
        
        # Update with normal price
        signal = risk_manager.update_position(50500.0)
        
        assert signal is None  # No exit signal
        assert risk_manager.current_position.unrealized_pnl == 0.002 * (50500.0 - 50000.0)
    
    def test_stop_loss_trigger(self, test_config):
        """Test stop-loss trigger."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Open position
        risk_manager.open_position(50000.0, 0.002, 49000.0, 52500.0)
        
        # Update with price at stop-loss
        signal = risk_manager.update_position(49000.0)
        
        assert signal == Signal.SELL
    
    def test_take_profit_trigger(self, test_config):
        """Test take-profit trigger."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Open position
        risk_manager.open_position(50000.0, 0.002, 49000.0, 52500.0)
        
        # Update with price at take-profit
        signal = risk_manager.update_position(52500.0)
        
        assert signal == Signal.SELL
    
    def test_update_position_no_position(self, test_config):
        """Test updating position when no position exists."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        signal = risk_manager.update_position(50000.0)
        
        assert signal is None


class TestCooldownManagement:
    """Test cooldown period management."""
    
    def test_cooldown_check_no_trades(self, test_config):
        """Test cooldown check with no previous trades."""
        risk_manager = RiskManager(test_config)
        
        assert risk_manager._check_cooldown() is True
        assert risk_manager._get_cooldown_remaining() == 0
    
    def test_cooldown_check_recent_trade(self, test_config):
        """Test cooldown check with recent trade."""
        test_config.cooldown_period = 300  # 5 minutes
        risk_manager = RiskManager(test_config)
        
        # Set recent trade time
        risk_manager.last_trade_time = datetime.utcnow() - timedelta(seconds=100)
        
        assert risk_manager._check_cooldown() is False
        remaining = risk_manager._get_cooldown_remaining()
        assert 190 <= remaining <= 210  # Approximately 200 seconds
    
    def test_cooldown_check_expired(self, test_config):
        """Test cooldown check after cooldown period."""
        test_config.cooldown_period = 300
        risk_manager = RiskManager(test_config)
        
        # Set old trade time
        risk_manager.last_trade_time = datetime.utcnow() - timedelta(seconds=400)
        
        assert risk_manager._check_cooldown() is True
        assert risk_manager._get_cooldown_remaining() == 0


class TestMetricsCalculation:
    """Test trading metrics calculation."""
    
    def test_metrics_no_trades(self, test_config):
        """Test metrics with no trades."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        metrics = risk_manager.get_metrics()
        
        assert metrics['balance'] == 10000.0
        assert metrics['total_pnl'] == 0.0
        assert metrics['win_rate'] == 0.0
        assert metrics['total_trades'] == 0
        assert metrics['open_position'] is False
    
    def test_win_rate_calculation(self, test_config):
        """Test win rate calculation."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Simulate some trades
        risk_manager.trade_history = [
            {'type': 'close', 'pnl': 100},   # Win
            {'type': 'close', 'pnl': -50},   # Loss
            {'type': 'close', 'pnl': 200},   # Win
            {'type': 'close', 'pnl': -25},   # Loss
            {'type': 'close', 'pnl': 150},   # Win
        ]
        
        risk_manager._update_metrics()
        
        expected_win_rate = 3 / 5  # 3 wins out of 5 trades
        assert abs(risk_manager.win_rate - expected_win_rate) < 1e-8
    
    def test_max_drawdown_calculation(self, test_config):
        """Test maximum drawdown calculation."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(8000.0)  # Current balance
        risk_manager.peak_balance = 10000.0  # Peak was higher
        
        risk_manager._update_metrics()
        
        expected_drawdown = (10000.0 - 8000.0) / 10000.0  # 20%
        assert abs(risk_manager.max_drawdown - expected_drawdown) < 1e-8
    
    def test_metrics_with_open_position(self, test_config):
        """Test metrics with open position."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Open position
        risk_manager.open_position(50000.0, 0.002, 49000.0, 52500.0)
        risk_manager.current_position.unrealized_pnl = 100.0
        
        metrics = risk_manager.get_metrics()
        
        assert metrics['open_position'] is True
        assert metrics['position_pnl'] == 100.0


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_close_position_without_position(self, test_config):
        """Test closing position when none exists."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Should not raise an error
        risk_manager.close_position(50000.0)
        
        assert risk_manager.current_position is None
        assert len(risk_manager.trade_history) == 0
    
    def test_zero_balance_operations(self, test_config):
        """Test operations with zero balance."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(0.0)
        
        can_trade, reason = risk_manager.can_trade(Signal.BUY, 50000.0)
        
        assert can_trade is False
        assert "Insufficient balance" in reason
    
    def test_negative_prices(self, test_config):
        """Test handling of negative prices (should not occur in practice)."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # This should handle gracefully even with negative price
        order_details = risk_manager.calculate_order_details(Signal.BUY, -100.0, 1.0)
        
        # Position size calculation should still work
        assert 'size' in order_details
    
    def test_very_small_position_sizes(self, test_config):
        """Test very small position sizes."""
        test_config.max_position_size = 0.00001  # Very small
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(100.0)  # Small balance
        
        order_details = risk_manager.calculate_order_details(Signal.BUY, 50000.0, 1.0)
        
        assert order_details['size'] > 0
        assert order_details['value'] < 1.0  # Very small value