import pytest
import os
from unittest.mock import patch

from src.config import TradingConfig, load_config, validate_config


class TestTradingConfig:
    """Test the TradingConfig dataclass."""
    
    def test_config_creation(self, test_config):
        """Test basic config creation."""
        assert test_config.api_name == "test_api_name"
        assert test_config.trading_mode == "test"
        assert test_config.max_position_size == 0.1
        assert test_config.rsi_period == 14
    
    def test_config_defaults(self):
        """Test config with minimal parameters."""
        config = TradingConfig(
            api_name="test",
            api_key="test",
            trading_mode="test",
            trading_pair="BTC-USD",
            candle_interval="1m",
            order_type="market",
            max_position_size=0.1,
            stop_loss_percentage=2.0,
            take_profit_percentage=5.0,
            min_order_size=10.0,
            cooldown_period=300,
            rsi_period=14,
            rsi_oversold=30,
            rsi_overbought=70,
            bollinger_period=20,
            bollinger_std=2.0,
            websocket_enabled=True,
            data_fetch_interval=60,
            log_level="INFO",
            log_file="trading_bot.log"
        )
        
        assert config.discord_webhook_url is None
        assert config.telegram_bot_token is None
        assert config.telegram_chat_id is None


class TestLoadConfig:
    """Test the load_config function."""
    
    def test_load_config_with_env_vars(self, mock_env):
        """Test loading config from environment variables."""
        config = load_config()
        
        assert config.api_name == "test_api_name"
        assert config.api_key == "test_api_key"
        assert config.trading_mode == "test"
        assert config.trading_pair == "BTC-USD"
        assert config.max_position_size == 0.1
        assert config.stop_loss_percentage == 2.0
        assert config.rsi_period == 14
        assert config.log_level == "DEBUG"
    
    def test_load_config_with_defaults(self, clean_env):
        """Test loading config with default values."""
        config = load_config()
        
        assert config.api_name == ""
        assert config.api_key == ""
        assert config.trading_mode == "test"
        assert config.trading_pair == "BTC-USD"
        assert config.max_position_size == 0.1
        assert config.rsi_period == 14
        assert config.log_level == "INFO"
    
    def test_load_config_boolean_conversion(self, monkeypatch):
        """Test boolean environment variable conversion."""
        monkeypatch.setenv("WEBSOCKET_ENABLED", "true")
        config = load_config()
        assert config.websocket_enabled is True
        
        monkeypatch.setenv("WEBSOCKET_ENABLED", "false")
        config = load_config()
        assert config.websocket_enabled is False
        
        monkeypatch.setenv("WEBSOCKET_ENABLED", "TRUE")
        config = load_config()
        assert config.websocket_enabled is True
    
    def test_load_config_numeric_conversion(self, monkeypatch):
        """Test numeric environment variable conversion."""
        monkeypatch.setenv("MAX_POSITION_SIZE", "0.25")
        monkeypatch.setenv("RSI_PERIOD", "21")
        monkeypatch.setenv("COOLDOWN_PERIOD", "600")
        
        config = load_config()
        
        assert config.max_position_size == 0.25
        assert config.rsi_period == 21
        assert config.cooldown_period == 600


class TestValidateConfig:
    """Test the validate_config function."""
    
    def test_valid_config(self, test_config):
        """Test validation of a valid config."""
        # Should not raise any exception
        validate_config(test_config)
    
    def test_missing_api_credentials(self, test_config):
        """Test validation with missing API credentials."""
        test_config.api_name = ""
        test_config.api_key = ""
        
        with pytest.raises(ValueError, match="Coinbase API credentials are required"):
            validate_config(test_config)
    
    def test_invalid_trading_mode(self, test_config):
        """Test validation with invalid trading mode."""
        test_config.trading_mode = "invalid"
        
        with pytest.raises(ValueError, match="Invalid trading mode"):
            validate_config(test_config)
    
    def test_invalid_position_size(self, test_config):
        """Test validation with invalid position size."""
        # Test negative position size
        test_config.max_position_size = -0.1
        with pytest.raises(ValueError, match="max_position_size must be between 0 and 1"):
            validate_config(test_config)
        
        # Test position size > 1
        test_config.max_position_size = 1.5
        with pytest.raises(ValueError, match="max_position_size must be between 0 and 1"):
            validate_config(test_config)
        
        # Test position size = 0
        test_config.max_position_size = 0
        with pytest.raises(ValueError, match="max_position_size must be between 0 and 1"):
            validate_config(test_config)
    
    def test_invalid_stop_loss(self, test_config):
        """Test validation with invalid stop loss."""
        test_config.stop_loss_percentage = -1.0
        
        with pytest.raises(ValueError, match="stop_loss_percentage must be positive"):
            validate_config(test_config)
    
    def test_invalid_take_profit(self, test_config):
        """Test validation with invalid take profit."""
        test_config.take_profit_percentage = 0
        
        with pytest.raises(ValueError, match="take_profit_percentage must be positive"):
            validate_config(test_config)
    
    def test_invalid_min_order_size(self, test_config):
        """Test validation with invalid minimum order size."""
        test_config.min_order_size = -10
        
        with pytest.raises(ValueError, match="min_order_size must be positive"):
            validate_config(test_config)
    
    def test_invalid_rsi_period(self, test_config):
        """Test validation with invalid RSI period."""
        test_config.rsi_period = 0
        
        with pytest.raises(ValueError, match="rsi_period must be positive"):
            validate_config(test_config)
    
    def test_invalid_rsi_thresholds(self, test_config):
        """Test validation with invalid RSI thresholds."""
        # Oversold >= overbought
        test_config.rsi_oversold = 70
        test_config.rsi_overbought = 30
        
        with pytest.raises(ValueError, match="Invalid RSI thresholds"):
            validate_config(test_config)
        
        # Oversold < 0
        test_config.rsi_oversold = -10
        test_config.rsi_overbought = 70
        
        with pytest.raises(ValueError, match="Invalid RSI thresholds"):
            validate_config(test_config)
        
        # Overbought > 100
        test_config.rsi_oversold = 30
        test_config.rsi_overbought = 110
        
        with pytest.raises(ValueError, match="Invalid RSI thresholds"):
            validate_config(test_config)
    
    def test_invalid_bollinger_period(self, test_config):
        """Test validation with invalid Bollinger period."""
        test_config.bollinger_period = -5
        
        with pytest.raises(ValueError, match="bollinger_period must be positive"):
            validate_config(test_config)
    
    def test_invalid_bollinger_std(self, test_config):
        """Test validation with invalid Bollinger standard deviation."""
        test_config.bollinger_std = 0
        
        with pytest.raises(ValueError, match="bollinger_std must be positive"):
            validate_config(test_config)
    
    def test_multiple_validation_errors(self, test_config):
        """Test validation with multiple errors."""
        test_config.api_name = ""
        test_config.trading_mode = "invalid"
        test_config.max_position_size = 2.0
        test_config.rsi_period = -1
        
        with pytest.raises(ValueError) as exc_info:
            validate_config(test_config)
        
        error_message = str(exc_info.value)
        assert "Coinbase API credentials are required" in error_message
        assert "Invalid trading mode" in error_message
        assert "max_position_size must be between 0 and 1" in error_message
        assert "rsi_period must be positive" in error_message


class TestConfigEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_boundary_values(self, test_config):
        """Test boundary values for validation."""
        # Test valid boundary values
        test_config.max_position_size = 0.000001  # Very small but positive
        test_config.rsi_oversold = 0
        test_config.rsi_overbought = 100
        
        # Should not raise
        validate_config(test_config)
        
        # Test exact boundary
        test_config.max_position_size = 1.0  # Exactly 1
        validate_config(test_config)
    
    def test_float_precision(self, monkeypatch):
        """Test float precision in environment variables."""
        monkeypatch.setenv("MAX_POSITION_SIZE", "0.123456789")
        monkeypatch.setenv("BOLLINGER_STD", "2.5")
        
        config = load_config()
        
        assert abs(config.max_position_size - 0.123456789) < 1e-9
        assert config.bollinger_std == 2.5
    
    def test_optional_fields(self, monkeypatch):
        """Test optional configuration fields."""
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "test_chat_id")
        
        config = load_config()
        
        assert config.discord_webhook_url == "https://discord.com/api/webhooks/test"
        assert config.telegram_bot_token == "test_token"
        assert config.telegram_chat_id == "test_chat_id"