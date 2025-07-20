import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.execution.engine import ExecutionEngine, Order, OrderStatus
from src.strategies.signal_processor import Signal
from src.risk.manager import RiskManager


class TestExecutionEngine:
    """Test the ExecutionEngine class."""
    
    def test_initialization(self, test_config):
        """Test execution engine initialization."""
        risk_manager = RiskManager(test_config)
        engine = ExecutionEngine(test_config, risk_manager)
        
        assert engine.config == test_config
        assert engine.risk_manager == risk_manager
        assert engine.pending_orders == {}
        assert engine.order_history == []
        assert engine.total_orders == 0
        assert engine.successful_orders == 0
        assert engine.failed_orders == 0
    
    @patch('src.execution.engine.RESTClient')
    def test_rest_client_initialization(self, mock_rest_client, test_config):
        """Test REST client initialization."""
        risk_manager = RiskManager(test_config)
        engine = ExecutionEngine(test_config, risk_manager)
        
        mock_rest_client.assert_called_once_with(
            api_key=test_config.api_name,
            api_secret=test_config.api_key
        )


class TestInitialization:
    """Test engine initialization with account data."""
    
    @patch('src.execution.engine.RESTClient')
    async def test_initialize_success(self, mock_rest_client, test_config, mock_coinbase_client):
        """Test successful initialization."""
        mock_rest_client.return_value = mock_coinbase_client
        risk_manager = RiskManager(test_config)
        engine = ExecutionEngine(test_config, risk_manager)
        
        await engine.initialize()
        
        # Should have set balance from account
        assert risk_manager.balance == 10000.0
        assert risk_manager.available_balance == 10000.0
    
    @patch('src.execution.engine.RESTClient')
    async def test_initialize_error(self, mock_rest_client, test_config):
        """Test initialization with API error."""
        mock_client = Mock()
        mock_client.get_accounts.side_effect = Exception("API Error")
        mock_rest_client.return_value = mock_client
        
        risk_manager = RiskManager(test_config)
        engine = ExecutionEngine(test_config, risk_manager)
        
        with pytest.raises(Exception, match="API Error"):
            await engine.initialize()


class TestSignalExecution:
    """Test signal execution logic."""
    
    async def test_execute_signal_rejected_by_risk_manager(self, test_config):
        """Test signal execution rejected by risk manager."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(5.0)  # Insufficient balance
        test_config.trading_mode = "paper"
        
        engine = ExecutionEngine(test_config, risk_manager)
        
        order = await engine.execute_signal(Signal.BUY, 50000.0)
        
        assert order is None
    
    async def test_execute_signal_no_order_details(self, test_config):
        """Test signal execution with no order details."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Mock risk manager to return empty order details
        risk_manager.calculate_order_details = Mock(return_value={})
        
        engine = ExecutionEngine(test_config, risk_manager)
        
        order = await engine.execute_signal(Signal.BUY, 50000.0)
        
        assert order is None


class TestTestModeExecution:
    """Test execution in test mode."""
    
    async def test_execute_test_buy_order(self, test_config):
        """Test executing buy order in test mode."""
        test_config.trading_mode = "test"
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        engine = ExecutionEngine(test_config, risk_manager)
        
        order = await engine.execute_signal(Signal.BUY, 50000.0, 1.0)
        
        assert order is not None
        assert order.side == "buy"
        assert order.status == OrderStatus.FILLED
        assert order.filled_price == 50000.0
        assert order.order_id.startswith("TEST-")
        assert engine.total_orders == 1
        assert engine.successful_orders == 1
        assert len(engine.order_history) == 1
    
    async def test_execute_test_sell_order(self, test_config):
        """Test executing sell order in test mode."""
        test_config.trading_mode = "test"
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Create a position first
        risk_manager.open_position(50000.0, 0.002, 49000.0, 52500.0)
        
        engine = ExecutionEngine(test_config, risk_manager)
        
        order = await engine.execute_signal(Signal.SELL, 51000.0, 1.0)
        
        assert order is not None
        assert order.side == "sell"
        assert order.status == OrderStatus.FILLED
        assert order.filled_price == 51000.0
        assert risk_manager.current_position is None  # Position closed


class TestPaperModeExecution:
    """Test execution in paper trading mode."""
    
    async def test_execute_paper_buy_order(self, test_config):
        """Test executing buy order in paper mode."""
        test_config.trading_mode = "paper"
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        engine = ExecutionEngine(test_config, risk_manager)
        
        order = await engine.execute_signal(Signal.BUY, 50000.0, 1.0)
        
        assert order is not None
        assert order.side == "buy"
        assert order.status == OrderStatus.FILLED
        assert order.order_id.startswith("PAPER-")
        assert order.filled_price is not None
        assert abs(order.filled_price - 50000.0) < 100  # Should be close to market price
        assert engine.total_orders == 1
        assert engine.successful_orders == 1
    
    async def test_execute_paper_sell_order(self, test_config):
        """Test executing sell order in paper mode."""
        test_config.trading_mode = "paper"
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Create a position first
        risk_manager.open_position(50000.0, 0.002, 49000.0, 52500.0)
        
        engine = ExecutionEngine(test_config, risk_manager)
        
        order = await engine.execute_signal(Signal.SELL, 51000.0, 1.0)
        
        assert order is not None
        assert order.side == "sell"
        assert order.status == OrderStatus.FILLED
        assert risk_manager.current_position is None


class TestLiveModeExecution:
    """Test execution in live trading mode."""
    
    @patch('src.execution.engine.RESTClient')
    async def test_execute_live_market_buy_order(self, mock_rest_client, test_config, mock_coinbase_client):
        """Test executing live market buy order."""
        test_config.trading_mode = "live"
        test_config.order_type = "market"
        mock_rest_client.return_value = mock_coinbase_client
        
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        engine = ExecutionEngine(test_config, risk_manager)
        
        # Mock the wait_for_fill method
        engine._wait_for_fill = AsyncMock(return_value=Order(
            order_id="test-order-123",
            side="buy",
            size=0.002,
            price=50000.0,
            status=OrderStatus.FILLED,
            created_at=datetime.utcnow(),
            filled_at=datetime.utcnow(),
            filled_price=50000.0,
            filled_size=0.002
        ))
        
        order = await engine.execute_signal(Signal.BUY, 50000.0, 1.0)
        
        assert order is not None
        assert order.side == "buy"
        assert order.status == OrderStatus.FILLED
        assert order.order_id == "test-order-123"
        
        # Verify create_order was called
        mock_coinbase_client.create_order.assert_called_once()
    
    @patch('src.execution.engine.RESTClient')
    async def test_execute_live_limit_buy_order(self, mock_rest_client, test_config, mock_coinbase_client):
        """Test executing live limit buy order."""
        test_config.trading_mode = "live"
        test_config.order_type = "limit"
        mock_rest_client.return_value = mock_coinbase_client
        
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        engine = ExecutionEngine(test_config, risk_manager)
        
        # Mock the wait_for_fill method
        engine._wait_for_fill = AsyncMock(return_value=Order(
            order_id="test-order-123",
            side="buy",
            size=0.002,
            price=49950.0,  # Limit price
            status=OrderStatus.FILLED,
            created_at=datetime.utcnow(),
            filled_at=datetime.utcnow(),
            filled_price=49950.0,
            filled_size=0.002
        ))
        
        order = await engine.execute_signal(Signal.BUY, 50000.0, 1.0)
        
        assert order is not None
        # Verify limit order configuration
        call_args = mock_coinbase_client.create_order.call_args
        assert "limit_limit_gtc" in str(call_args)
    
    @patch('src.execution.engine.RESTClient')
    async def test_execute_live_order_api_error(self, mock_rest_client, test_config):
        """Test live order execution with API error."""
        test_config.trading_mode = "live"
        
        mock_client = Mock()
        mock_client.create_order.side_effect = Exception("API Error")
        mock_rest_client.return_value = mock_client
        
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        engine = ExecutionEngine(test_config, risk_manager)
        
        order = await engine.execute_signal(Signal.BUY, 50000.0, 1.0)
        
        assert order is None
        assert engine.failed_orders == 1


class TestOrderFillWaiting:
    """Test order fill waiting logic."""
    
    @patch('src.execution.engine.RESTClient')
    async def test_wait_for_fill_success(self, mock_rest_client, test_config):
        """Test successful order fill waiting."""
        # Setup mock API response
        mock_order = Mock()
        mock_order.status = "FILLED"
        mock_order.average_filled_price = "50000.00"
        mock_order.filled_size = "0.002"
        
        mock_response = Mock()
        mock_response.order = mock_order
        
        mock_client = Mock()
        mock_client.get_order.return_value = mock_response
        mock_rest_client.return_value = mock_client
        
        risk_manager = RiskManager(test_config)
        engine = ExecutionEngine(test_config, risk_manager)
        
        # Create pending order
        order = Order(
            order_id="test-123",
            side="buy",
            size=0.002,
            price=50000.0,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )
        engine.pending_orders["test-123"] = order
        
        result = await engine._wait_for_fill("test-123", timeout=1)
        
        assert result is not None
        assert result.status == OrderStatus.FILLED
        assert result.filled_price == 50000.00
        assert result.filled_size == 0.002
        assert "test-123" not in engine.pending_orders
    
    @patch('src.execution.engine.RESTClient')
    async def test_wait_for_fill_cancelled(self, mock_rest_client, test_config):
        """Test order cancelled during waiting."""
        mock_order = Mock()
        mock_order.status = "CANCELLED"
        
        mock_response = Mock()
        mock_response.order = mock_order
        
        mock_client = Mock()
        mock_client.get_order.return_value = mock_response
        mock_rest_client.return_value = mock_client
        
        risk_manager = RiskManager(test_config)
        engine = ExecutionEngine(test_config, risk_manager)
        
        # Create pending order
        order = Order(
            order_id="test-123",
            side="buy",
            size=0.002,
            price=50000.0,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )
        engine.pending_orders["test-123"] = order
        
        result = await engine._wait_for_fill("test-123", timeout=1)
        
        assert result is not None
        assert result.status == OrderStatus.CANCELLED
    
    @patch('src.execution.engine.RESTClient')
    async def test_wait_for_fill_timeout(self, mock_rest_client, test_config):
        """Test order fill timeout."""
        mock_order = Mock()
        mock_order.status = "PENDING"  # Never fills
        
        mock_response = Mock()
        mock_response.order = mock_order
        
        mock_client = Mock()
        mock_client.get_order.return_value = mock_response
        mock_client.cancel_orders.return_value = None
        mock_rest_client.return_value = mock_client
        
        risk_manager = RiskManager(test_config)
        engine = ExecutionEngine(test_config, risk_manager)
        
        # Create pending order
        order = Order(
            order_id="test-123",
            side="buy",
            size=0.002,
            price=50000.0,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )
        engine.pending_orders["test-123"] = order
        
        result = await engine._wait_for_fill("test-123", timeout=0.1)
        
        assert result is not None
        assert result.status == OrderStatus.CANCELLED
        assert result.error_message == "Order timeout"
        
        # Should have attempted to cancel
        mock_client.cancel_orders.assert_called_once_with(["test-123"])


class TestPendingOrderManagement:
    """Test pending order management."""
    
    async def test_check_pending_orders(self, test_config):
        """Test checking pending orders."""
        risk_manager = RiskManager(test_config)
        engine = ExecutionEngine(test_config, risk_manager)
        
        # Mock _wait_for_fill to avoid actual API calls
        engine._wait_for_fill = AsyncMock()
        
        # Add some pending orders
        order1 = Order("order1", "buy", 0.001, 50000.0, OrderStatus.PENDING, datetime.utcnow())
        order2 = Order("order2", "sell", 0.001, 51000.0, OrderStatus.PENDING, datetime.utcnow())
        
        engine.pending_orders["order1"] = order1
        engine.pending_orders["order2"] = order2
        
        await engine.check_pending_orders()
        
        # Should have checked both orders
        assert engine._wait_for_fill.call_count == 2


class TestExecutionStats:
    """Test execution statistics."""
    
    def test_get_execution_stats_initial(self, test_config):
        """Test getting initial execution statistics."""
        risk_manager = RiskManager(test_config)
        engine = ExecutionEngine(test_config, risk_manager)
        
        stats = engine.get_execution_stats()
        
        assert stats['total_orders'] == 0
        assert stats['successful_orders'] == 0
        assert stats['failed_orders'] == 0
        assert stats['pending_orders'] == 0
        assert stats['success_rate'] == 0
    
    async def test_get_execution_stats_with_orders(self, test_config):
        """Test getting execution statistics after some orders."""
        test_config.trading_mode = "test"
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        engine = ExecutionEngine(test_config, risk_manager)
        
        # Execute some orders
        await engine.execute_signal(Signal.BUY, 50000.0, 1.0)
        await engine.execute_signal(Signal.SELL, 51000.0, 1.0)
        
        stats = engine.get_execution_stats()
        
        assert stats['total_orders'] == 2
        assert stats['successful_orders'] == 2
        assert stats['failed_orders'] == 0
        assert stats['success_rate'] == 1.0


class TestOrderModel:
    """Test the Order dataclass."""
    
    def test_order_creation(self):
        """Test order creation."""
        order = Order(
            order_id="test-123",
            side="buy",
            size=0.002,
            price=50000.0,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        assert order.order_id == "test-123"
        assert order.side == "buy"
        assert order.size == 0.002
        assert order.price == 50000.0
        assert order.status == OrderStatus.PENDING
        assert order.filled_at is None
        assert order.filled_price is None
        assert order.filled_size is None
        assert order.error_message is None


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    async def test_execute_signal_hold(self, test_config):
        """Test executing HOLD signal (should do nothing)."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        engine = ExecutionEngine(test_config, risk_manager)
        
        order = await engine.execute_signal(Signal.HOLD, 50000.0, 1.0)
        
        assert order is None
    
    @patch('src.execution.engine.RESTClient')
    async def test_live_order_no_response(self, mock_rest_client, test_config):
        """Test live order with no API response."""
        test_config.trading_mode = "live"
        
        mock_client = Mock()
        mock_client.create_order.return_value = None  # No response
        mock_rest_client.return_value = mock_client
        
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        engine = ExecutionEngine(test_config, risk_manager)
        
        order = await engine.execute_signal(Signal.BUY, 50000.0, 1.0)
        
        assert order is None
    
    @patch('src.execution.engine.RESTClient')
    async def test_wait_for_fill_api_error(self, mock_rest_client, test_config):
        """Test order fill waiting with API error."""
        mock_client = Mock()
        mock_client.get_order.side_effect = Exception("API Error")
        mock_client.cancel_orders.return_value = None
        mock_rest_client.return_value = mock_client
        
        risk_manager = RiskManager(test_config)
        engine = ExecutionEngine(test_config, risk_manager)
        
        # Create pending order
        order = Order(
            order_id="test-123",
            side="buy",
            size=0.002,
            price=50000.0,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )
        engine.pending_orders["test-123"] = order
        
        result = await engine._wait_for_fill("test-123", timeout=0.1)
        
        # Should handle error gracefully and timeout
        assert result is not None
        assert result.status == OrderStatus.CANCELLED
    
    async def test_wait_for_fill_nonexistent_order(self, test_config):
        """Test waiting for fill of non-existent order."""
        risk_manager = RiskManager(test_config)
        engine = ExecutionEngine(test_config, risk_manager)
        
        result = await engine._wait_for_fill("nonexistent", timeout=0.1)
        
        assert result is None
    
    def test_signal_strength_zero(self, test_config):
        """Test order calculation with zero signal strength."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        engine = ExecutionEngine(test_config, risk_manager)
        
        # Calculate order with zero signal strength should still work
        # The risk manager handles this
        order_details = risk_manager.calculate_order_details(Signal.BUY, 50000.0, 0.0)
        
        assert 'size' in order_details
        assert order_details['size'] == 0.0  # Should be zero size