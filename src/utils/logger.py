import logging
import colorlog
from typing import Optional
import sys
from datetime import datetime
import json


class TradingLogger:
    def __init__(self, name: str, log_level: str = "INFO", log_file: Optional[str] = None):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        self.logger.handlers = []
        
        # Console handler with color
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler if specified
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
    
    def debug(self, message: str, **kwargs):
        self.logger.debug(self._format_message(message, kwargs))
    
    def info(self, message: str, **kwargs):
        self.logger.info(self._format_message(message, kwargs))
    
    def warning(self, message: str, **kwargs):
        self.logger.warning(self._format_message(message, kwargs))
    
    def error(self, message: str, **kwargs):
        self.logger.error(self._format_message(message, kwargs))
    
    def critical(self, message: str, **kwargs):
        self.logger.critical(self._format_message(message, kwargs))
    
    def trade_event(self, event_type: str, details: dict):
        """Log trading events with structured data."""
        event_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            **details
        }
        self.info(f"TRADE_EVENT: {event_type}", event_data=json.dumps(event_data))
    
    def _format_message(self, message: str, extra_data: dict) -> str:
        """Format message with extra data if provided."""
        if extra_data:
            extra_str = " | ".join([f"{k}={v}" for k, v in extra_data.items()])
            return f"{message} | {extra_str}"
        return message


# Singleton logger instance
_logger_instance: Optional[TradingLogger] = None


def get_logger(name: str = "TradingBot", log_level: str = "INFO", 
               log_file: Optional[str] = None) -> TradingLogger:
    """Get or create a logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = TradingLogger(name, log_level, log_file)
    return _logger_instance