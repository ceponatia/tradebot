#!/usr/bin/env python3
import asyncio
import signal
import sys
from typing import Optional

from src.config import load_config, validate_config
from src.utils.logger import get_logger
from src.data.collector import DataCollector
from src.strategies.signal_processor import SignalProcessor, Signal
from src.risk.manager import RiskManager
from src.execution.engine import ExecutionEngine


class TradingBot:
    def __init__(self):
        # Load and validate configuration
        self.config = load_config()
        validate_config(self.config)
        
        # Initialize logger
        self.logger = get_logger("TradingBot", self.config.log_level, self.config.log_file)
        
        # Initialize components
        self.data_collector = DataCollector(self.config)
        self.signal_processor = SignalProcessor(self.config)
        self.risk_manager = RiskManager(self.config)
        self.execution_engine = ExecutionEngine(self.config, self.risk_manager)
        
        # Control flags
        self.running = False
        self.shutdown_event = asyncio.Event()
        
        # Set up callbacks
        self.data_collector.on_price_update = self.on_price_update
        self.data_collector.on_candle_update = self.on_candle_update
    
    async def start(self):
        """Start the trading bot."""
        self.logger.info("Starting trading bot",
                        mode=self.config.trading_mode,
                        pair=self.config.trading_pair)
        
        try:
            # Initialize execution engine
            await self.execution_engine.initialize()
            
            # Start data collection
            self.running = True
            data_task = asyncio.create_task(self.data_collector.start())
            
            # Start main trading loop
            trading_task = asyncio.create_task(self.trading_loop())
            
            # Wait for shutdown
            await self.shutdown_event.wait()
            
            # Clean shutdown
            self.running = False
            await self.data_collector.stop()
            data_task.cancel()
            trading_task.cancel()
            
        except Exception as e:
            self.logger.error("Bot error", error=str(e))
            raise
    
    async def trading_loop(self):
        """Main trading loop."""
        while self.running:
            try:
                # Check pending orders
                await self.execution_engine.check_pending_orders()
                
                # Log metrics periodically
                if hasattr(self, '_last_metrics_log'):
                    if (asyncio.get_event_loop().time() - self._last_metrics_log) > 300:
                        self.log_metrics()
                        self._last_metrics_log = asyncio.get_event_loop().time()
                else:
                    self._last_metrics_log = asyncio.get_event_loop().time()
                
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error("Trading loop error", error=str(e))
                await asyncio.sleep(5)
    
    async def on_price_update(self, price: float):
        """Handle price updates."""
        # Check stop loss/take profit
        if self.risk_manager.current_position:
            exit_signal = self.risk_manager.update_position(price)
            if exit_signal:
                await self.execution_engine.execute_signal(exit_signal, price)
    
    async def on_candle_update(self, candles):
        """Handle candle updates and generate trading signals."""
        try:
            # Generate signal
            signal, indicators = self.signal_processor.process(candles)
            
            if signal != Signal.HOLD:
                # Get current price
                current_price = self.data_collector.get_latest_price()
                if not current_price:
                    self.logger.warning("No current price available")
                    return
                
                # Calculate signal strength
                signal_strength = self.signal_processor.get_signal_strength(indicators)
                
                # Execute signal
                order = await self.execution_engine.execute_signal(
                    signal, current_price, signal_strength
                )
                
                if order:
                    self.logger.trade_event(
                        "ORDER_EXECUTED",
                        {
                            "signal": signal.value,
                            "price": current_price,
                            "order_id": order.order_id,
                            "size": order.size,
                            "indicators": indicators
                        }
                    )
        
        except Exception as e:
            self.logger.error("Signal processing error", error=str(e))
    
    def log_metrics(self):
        """Log current metrics."""
        risk_metrics = self.risk_manager.get_metrics()
        exec_stats = self.execution_engine.get_execution_stats()
        
        self.logger.info("Trading metrics",
                        **risk_metrics,
                        **exec_stats)
    
    def shutdown(self):
        """Shutdown the bot."""
        self.logger.info("Shutting down trading bot")
        self.shutdown_event.set()


async def main():
    """Main entry point."""
    bot = TradingBot()
    
    # Set up signal handlers
    def signal_handler(signum, frame):
        bot.logger.info("Received shutdown signal")
        bot.shutdown()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Print startup information
    print(f"""
╔══════════════════════════════════════════════════════╗
║           Cryptocurrency Trading Bot                  ║
║                                                       ║
║  Mode: {bot.config.trading_mode:<15}                         ║
║  Pair: {bot.config.trading_pair:<15}                         ║
║  Strategy: RSI + Bollinger Bands                     ║
║                                                       ║
║  Press Ctrl+C to stop                                 ║
╚══════════════════════════════════════════════════════╝
    """)
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        bot.logger.info("Interrupted by user")
    except Exception as e:
        bot.logger.error("Fatal error", error=str(e))
        sys.exit(1)
    
    # Final metrics
    bot.log_metrics()
    print("\nBot stopped successfully")


if __name__ == "__main__":
    asyncio.run(main())