import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class TradingConfig:
    # Coinbase API Configuration
    api_name: str
    api_key: str
    
    # Trading Configuration
    trading_mode: str
    trading_pair: str
    candle_interval: str
    order_type: str
    
    # Risk Management
    max_position_size: float
    stop_loss_percentage: float
    take_profit_percentage: float
    min_order_size: float
    cooldown_period: int
    
    # Strategy Parameters
    rsi_period: int
    rsi_oversold: int
    rsi_overbought: int
    bollinger_period: int
    bollinger_std: float
    
    # Data Collection
    websocket_enabled: bool
    data_fetch_interval: int
    
    # Logging
    log_level: str
    log_file: str
    
    # Optional Notifications
    discord_webhook_url: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None


def load_config() -> TradingConfig:
    """Load configuration from environment variables."""
    return TradingConfig(
        # Coinbase API Configuration
        api_name=os.getenv("COINBASE_API_NAME", ""),
        api_key=os.getenv("COINBASE_API_KEY", ""),
        
        # Trading Configuration
        trading_mode=os.getenv("TRADING_MODE", "test"),
        trading_pair=os.getenv("TRADING_PAIR", "BTC-USD"),
        candle_interval=os.getenv("CANDLE_INTERVAL", "1m"),
        order_type=os.getenv("ORDER_TYPE", "market"),
        
        # Risk Management
        max_position_size=float(os.getenv("MAX_POSITION_SIZE", "0.1")),
        stop_loss_percentage=float(os.getenv("STOP_LOSS_PERCENTAGE", "2.0")),
        take_profit_percentage=float(os.getenv("TAKE_PROFIT_PERCENTAGE", "5.0")),
        min_order_size=float(os.getenv("MIN_ORDER_SIZE", "10")),
        cooldown_period=int(os.getenv("COOLDOWN_PERIOD", "300")),
        
        # Strategy Parameters
        rsi_period=int(os.getenv("RSI_PERIOD", "14")),
        rsi_oversold=int(os.getenv("RSI_OVERSOLD", "30")),
        rsi_overbought=int(os.getenv("RSI_OVERBOUGHT", "70")),
        bollinger_period=int(os.getenv("BOLLINGER_PERIOD", "20")),
        bollinger_std=float(os.getenv("BOLLINGER_STD", "2")),
        
        # Data Collection
        websocket_enabled=os.getenv("WEBSOCKET_ENABLED", "true").lower() == "true",
        data_fetch_interval=int(os.getenv("DATA_FETCH_INTERVAL", "60")),
        
        # Logging
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_file=os.getenv("LOG_FILE", "trading_bot.log"),
        
        # Optional Notifications
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    )


def validate_config(config: TradingConfig) -> None:
    """Validate the configuration values."""
    errors = []
    
    # API validation
    if not config.api_name or not config.api_key:
        errors.append("Coinbase API credentials are required")
    
    # Trading mode validation
    if config.trading_mode not in ["test", "paper", "live"]:
        errors.append(f"Invalid trading mode: {config.trading_mode}")
    
    # Risk management validation
    if not 0 < config.max_position_size <= 1:
        errors.append("max_position_size must be between 0 and 1")
    
    if config.stop_loss_percentage <= 0:
        errors.append("stop_loss_percentage must be positive")
    
    if config.take_profit_percentage <= 0:
        errors.append("take_profit_percentage must be positive")
    
    if config.min_order_size <= 0:
        errors.append("min_order_size must be positive")
    
    # Strategy validation
    if config.rsi_period <= 0:
        errors.append("rsi_period must be positive")
    
    if not 0 <= config.rsi_oversold < config.rsi_overbought <= 100:
        errors.append("Invalid RSI thresholds")
    
    if config.bollinger_period <= 0:
        errors.append("bollinger_period must be positive")
    
    if config.bollinger_std <= 0:
        errors.append("bollinger_std must be positive")
    
    if errors:
        raise ValueError(f"Configuration errors: {'; '.join(errors)}")