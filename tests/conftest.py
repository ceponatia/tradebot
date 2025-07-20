import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock
import os
import tempfile

from src.config import TradingConfig


@pytest.fixture
def test_config():
    """Create a test configuration."""
    return TradingConfig(
        # API Configuration
        api_name="test_api_name",
        api_key="test_api_key",
        
        # Trading Configuration
        trading_mode="test",
        trading_pair="BTC-USD",
        candle_interval="1m",
        order_type="market",
        
        # Risk Management
        max_position_size=0.1,
        stop_loss_percentage=2.0,
        take_profit_percentage=5.0,
        min_order_size=10.0,
        cooldown_period=300,
        
        # Strategy Parameters
        rsi_period=14,
        rsi_oversold=30,
        rsi_overbought=70,
        bollinger_period=20,
        bollinger_std=2.0,
        
        # Data Collection
        websocket_enabled=False,
        data_fetch_interval=60,
        
        # Logging
        log_level="DEBUG",
        log_file="test.log"
    )


@pytest.fixture
def sample_candles():
    """Create sample candle data for testing."""
    # Generate realistic candle data
    dates = pd.date_range(start='2024-01-01', periods=100, freq='1T')
    
    # Start with a base price and add some random walk
    base_price = 50000.0
    price_changes = np.random.normal(0, 100, 100)
    prices = [base_price]
    
    for change in price_changes[:-1]:
        new_price = max(prices[-1] + change, 1000)  # Minimum price
        prices.append(new_price)
    
    # Create OHLCV data
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        # Create realistic OHLC based on close price
        high = close + np.random.uniform(0, close * 0.002)
        low = close - np.random.uniform(0, close * 0.002)
        open_price = close + np.random.uniform(-close * 0.001, close * 0.001)
        volume = np.random.uniform(1000, 10000)
        
        data.append({
            'timestamp': date,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df


@pytest.fixture
def volatile_candles():
    """Create volatile candle data for stress testing."""
    dates = pd.date_range(start='2024-01-01', periods=50, freq='1T')
    
    # Create highly volatile price data
    base_price = 50000.0
    prices = []
    
    for i in range(50):
        if i == 0:
            price = base_price
        else:
            # Add large price swings
            change_percent = np.random.uniform(-0.05, 0.05)  # ±5% changes
            price = max(prices[-1] * (1 + change_percent), 1000)
        prices.append(price)
    
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        high = close * (1 + np.random.uniform(0, 0.01))
        low = close * (1 - np.random.uniform(0, 0.01))
        open_price = close + np.random.uniform(-close * 0.005, close * 0.005)
        volume = np.random.uniform(5000, 50000)
        
        data.append({
            'timestamp': date,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df


@pytest.fixture
def trending_candles():
    """Create trending candle data (upward trend)."""
    dates = pd.date_range(start='2024-01-01', periods=50, freq='1T')
    
    # Create upward trending data
    base_price = 45000.0
    trend_rate = 0.002  # 0.2% increase per candle on average
    
    prices = []
    for i in range(50):
        if i == 0:
            price = base_price
        else:
            # Add trend + noise
            trend_change = trend_rate
            noise = np.random.normal(0, 0.001)  # Small random noise
            price = max(prices[-1] * (1 + trend_change + noise), 1000)
        prices.append(price)
    
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        high = close * (1 + np.random.uniform(0, 0.005))
        low = close * (1 - np.random.uniform(0, 0.005))
        open_price = close + np.random.uniform(-close * 0.002, close * 0.002)
        volume = np.random.uniform(2000, 20000)
        
        data.append({
            'timestamp': date,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df


@pytest.fixture
def mock_coinbase_client():
    """Create a mock Coinbase client."""
    mock_client = Mock()
    
    # Mock account data
    mock_account = Mock()
    mock_account.currency = "USD"
    mock_account.available_balance.value = "10000.00"
    
    mock_accounts = Mock()
    mock_accounts.accounts = [mock_account]
    mock_client.get_accounts.return_value = mock_accounts
    
    # Mock product data
    mock_product = Mock()
    mock_product.price = "50000.00"
    mock_client.get_product.return_value = mock_product
    
    # Mock candle data
    mock_candle = Mock()
    mock_candle.start = str(int(datetime.utcnow().timestamp()))
    mock_candle.open = "49900.00"
    mock_candle.high = "50100.00"
    mock_candle.low = "49800.00"
    mock_candle.close = "50000.00"
    mock_candle.volume = "1000.0"
    
    mock_candles = Mock()
    mock_candles.candles = [mock_candle]
    mock_client.get_candles.return_value = mock_candles
    
    # Mock order creation
    mock_order_response = Mock()
    mock_order_response.order_id = "test-order-123"
    mock_client.create_order.return_value = mock_order_response
    
    # Mock order status
    mock_order = Mock()
    mock_order.status = "FILLED"
    mock_order.average_filled_price = "50000.00"
    mock_order.filled_size = "0.002"
    
    mock_order_response_status = Mock()
    mock_order_response_status.order = mock_order
    mock_client.get_order.return_value = mock_order_response_status
    
    return mock_client


@pytest.fixture
def temp_log_file():
    """Create a temporary log file for testing."""
    fd, path = tempfile.mkstemp(suffix='.log')
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket client."""
    mock_ws = AsyncMock()
    mock_ws.subscribe = AsyncMock()
    mock_ws.close = AsyncMock()
    mock_ws.run_forever = AsyncMock()
    return mock_ws


@pytest.fixture
async def async_mock():
    """Helper for creating async mocks."""
    return AsyncMock()


class MockPriceGenerator:
    """Generate realistic price sequences for testing."""
    
    def __init__(self, initial_price=50000.0, volatility=0.01):
        self.current_price = initial_price
        self.volatility = volatility
    
    def next_price(self):
        """Generate next price with random walk."""
        change = np.random.normal(0, self.volatility)
        self.current_price *= (1 + change)
        return max(self.current_price, 1000.0)  # Minimum price
    
    def price_sequence(self, count=10):
        """Generate a sequence of prices."""
        return [self.next_price() for _ in range(count)]


@pytest.fixture
def price_generator():
    """Create a price generator for testing."""
    return MockPriceGenerator()


# Environment variable fixtures
@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment variables for testing."""
    env_vars = [
        "COINBASE_API_NAME", "COINBASE_API_KEY", "TRADING_MODE",
        "TRADING_PAIR", "MAX_POSITION_SIZE", "STOP_LOSS_PERCENTAGE",
        "RSI_PERIOD", "LOG_LEVEL"
    ]
    
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock environment variables."""
    env_vars = {
        "COINBASE_API_NAME": "test_api_name",
        "COINBASE_API_KEY": "test_api_key",
        "TRADING_MODE": "test",
        "TRADING_PAIR": "BTC-USD",
        "MAX_POSITION_SIZE": "0.1",
        "STOP_LOSS_PERCENTAGE": "2.0",
        "RSI_PERIOD": "14",
        "LOG_LEVEL": "DEBUG"
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)