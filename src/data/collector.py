import asyncio
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
import pandas as pd
from coinbase.rest import RESTClient
from coinbase.websocket import WSClient
import json

from src.utils.logger import get_logger
from src.config import TradingConfig


class DataCollector:
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = get_logger("DataCollector", config.log_level, config.log_file)
        
        # Initialize Coinbase REST client
        self.rest_client = RESTClient(
            api_key=config.api_name,
            api_secret=config.api_key
        )
        
        # WebSocket client will be initialized when needed
        self.ws_client = None
        
        # Data storage
        self.candles: pd.DataFrame = pd.DataFrame()
        self.orderbook: Dict = {}
        self.latest_price: Optional[float] = None
        
        # Callbacks
        self.on_price_update: Optional[Callable] = None
        self.on_candle_update: Optional[Callable] = None
    
    async def start(self):
        """Start data collection."""
        self.logger.info("Starting data collector", pair=self.config.trading_pair)
        
        # Load historical data
        await self.load_historical_data()
        
        # Start real-time data collection
        if self.config.websocket_enabled:
            await self.start_websocket()
        else:
            await self.start_polling()
    
    async def stop(self):
        """Stop data collection."""
        self.logger.info("Stopping data collector")
        if self.ws_client:
            await self.ws_client.close()
    
    async def load_historical_data(self):
        """Load historical candle data."""
        try:
            # Calculate start time based on strategy requirements
            periods_needed = max(
                self.config.rsi_period,
                self.config.bollinger_period
            ) * 2  # Extra buffer
            
            interval_minutes = self._get_interval_minutes()
            start_time = datetime.utcnow() - timedelta(minutes=interval_minutes * periods_needed)
            
            self.logger.info("Loading historical data", 
                           periods=periods_needed,
                           start_time=start_time.isoformat())
            
            # Fetch candles from Coinbase
            candles = self.rest_client.get_candles(
                product_id=self.config.trading_pair,
                start=int(start_time.timestamp()),
                end=int(datetime.utcnow().timestamp()),
                granularity=self._get_granularity()
            )
            
            # Convert to DataFrame
            if candles and hasattr(candles, 'candles'):
                candle_data = []
                for candle in candles.candles:
                    candle_data.append({
                        'timestamp': datetime.fromtimestamp(int(candle.start)),
                        'open': float(candle.open),
                        'high': float(candle.high),
                        'low': float(candle.low),
                        'close': float(candle.close),
                        'volume': float(candle.volume)
                    })
                
                self.candles = pd.DataFrame(candle_data)
                self.candles.set_index('timestamp', inplace=True)
                self.candles.sort_index(inplace=True)
                
                self.logger.info("Historical data loaded", 
                               candles=len(self.candles),
                               latest=self.candles.index[-1] if len(self.candles) > 0 else None)
            
        except Exception as e:
            self.logger.error("Failed to load historical data", error=str(e))
            raise
    
    async def start_websocket(self):
        """Start WebSocket connection for real-time data."""
        try:
            self.logger.info("Starting WebSocket connection")
            
            # Initialize WebSocket client
            self.ws_client = WSClient(
                api_key=self.config.api_name,
                api_secret=self.config.api_key,
                on_message=self._handle_ws_message,
                on_error=self._handle_ws_error,
                on_close=self._handle_ws_close
            )
            
            # Subscribe to ticker channel
            await self.ws_client.subscribe(
                product_ids=[self.config.trading_pair],
                channels=["ticker", "level2"]
            )
            
            # Keep connection alive
            await self.ws_client.run_forever()
            
        except Exception as e:
            self.logger.error("WebSocket error", error=str(e))
            # Fallback to polling
            await self.start_polling()
    
    async def start_polling(self):
        """Start polling for data updates."""
        self.logger.info("Starting REST API polling", 
                        interval=self.config.data_fetch_interval)
        
        while True:
            try:
                await self.fetch_latest_data()
                await asyncio.sleep(self.config.data_fetch_interval)
            except Exception as e:
                self.logger.error("Polling error", error=str(e))
                await asyncio.sleep(5)  # Brief pause before retry
    
    async def fetch_latest_data(self):
        """Fetch latest market data via REST API."""
        try:
            # Get ticker data
            ticker = self.rest_client.get_product(self.config.trading_pair)
            if ticker:
                self.latest_price = float(ticker.price)
                
                if self.on_price_update:
                    await self.on_price_update(self.latest_price)
                
                self.logger.debug("Price updated", price=self.latest_price)
            
            # Update candles
            await self._update_candles()
            
        except Exception as e:
            self.logger.error("Failed to fetch latest data", error=str(e))
    
    async def _update_candles(self):
        """Update candle data with latest values."""
        try:
            # Get latest candle
            latest_candles = self.rest_client.get_candles(
                product_id=self.config.trading_pair,
                start=int((datetime.utcnow() - timedelta(minutes=self._get_interval_minutes() * 2)).timestamp()),
                end=int(datetime.utcnow().timestamp()),
                granularity=self._get_granularity()
            )
            
            if latest_candles and hasattr(latest_candles, 'candles') and latest_candles.candles:
                latest = latest_candles.candles[0]
                new_candle = pd.DataFrame([{
                    'timestamp': datetime.fromtimestamp(int(latest.start)),
                    'open': float(latest.open),
                    'high': float(latest.high),
                    'low': float(latest.low),
                    'close': float(latest.close),
                    'volume': float(latest.volume)
                }]).set_index('timestamp')
                
                # Update or append candle
                if new_candle.index[0] in self.candles.index:
                    self.candles.loc[new_candle.index[0]] = new_candle.iloc[0]
                else:
                    self.candles = pd.concat([self.candles, new_candle])
                    self.candles.sort_index(inplace=True)
                
                if self.on_candle_update:
                    await self.on_candle_update(self.candles)
                    
        except Exception as e:
            self.logger.error("Failed to update candles", error=str(e))
    
    def _handle_ws_message(self, message: str):
        """Handle WebSocket message."""
        try:
            data = json.loads(message)
            
            if data.get('type') == 'ticker':
                self.latest_price = float(data.get('price', 0))
                if self.on_price_update:
                    asyncio.create_task(self.on_price_update(self.latest_price))
                    
            elif data.get('type') == 'l2update':
                # Update orderbook
                self._update_orderbook(data)
                
        except Exception as e:
            self.logger.error("Failed to handle WebSocket message", error=str(e))
    
    def _handle_ws_error(self, error: Exception):
        """Handle WebSocket error."""
        self.logger.error("WebSocket error", error=str(error))
    
    def _handle_ws_close(self):
        """Handle WebSocket close."""
        self.logger.warning("WebSocket connection closed")
        # Attempt to reconnect
        asyncio.create_task(self.start_websocket())
    
    def _update_orderbook(self, data: dict):
        """Update orderbook from L2 data."""
        # Implementation depends on specific orderbook requirements
        pass
    
    def _get_interval_minutes(self) -> int:
        """Convert interval string to minutes."""
        interval_map = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '1h': 60,
            '4h': 240,
            '1d': 1440
        }
        return interval_map.get(self.config.candle_interval, 60)
    
    def _get_granularity(self) -> str:
        """Convert interval to Coinbase granularity."""
        granularity_map = {
            '1m': 'ONE_MINUTE',
            '5m': 'FIVE_MINUTE',
            '15m': 'FIFTEEN_MINUTE',
            '1h': 'ONE_HOUR',
            '4h': 'SIX_HOUR',  # Note: Coinbase doesn't have 4h, using 6h
            '1d': 'ONE_DAY'
        }
        return granularity_map.get(self.config.candle_interval, 'ONE_HOUR')
    
    def get_latest_candles(self, count: int = 100) -> pd.DataFrame:
        """Get latest N candles."""
        return self.candles.tail(count).copy()
    
    def get_latest_price(self) -> Optional[float]:
        """Get latest price."""
        return self.latest_price