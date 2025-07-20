import pytest
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json

from src.data.collector import DataCollector


class TestDataCollector:
    """Test the DataCollector class."""
    
    def test_initialization(self, test_config):
        """Test data collector initialization."""
        collector = DataCollector(test_config)
        
        assert collector.config == test_config
        assert isinstance(collector.candles, pd.DataFrame)
        assert len(collector.candles) == 0
        assert collector.latest_price is None
        assert collector.on_price_update is None
        assert collector.on_candle_update is None
    
    @patch('src.data.collector.RESTClient')
    def test_rest_client_initialization(self, mock_rest_client, test_config):
        """Test REST client initialization."""
        collector = DataCollector(test_config)
        
        mock_rest_client.assert_called_once_with(
            api_key=test_config.api_name,
            api_secret=test_config.api_key
        )


class TestIntervalConversion:
    """Test interval conversion methods."""
    
    def test_get_interval_minutes(self, test_config):
        """Test interval to minutes conversion."""
        collector = DataCollector(test_config)
        
        test_config.candle_interval = "1m"
        assert collector._get_interval_minutes() == 1
        
        test_config.candle_interval = "5m"
        assert collector._get_interval_minutes() == 5
        
        test_config.candle_interval = "15m"
        assert collector._get_interval_minutes() == 15
        
        test_config.candle_interval = "1h"
        assert collector._get_interval_minutes() == 60
        
        test_config.candle_interval = "4h"
        assert collector._get_interval_minutes() == 240
        
        test_config.candle_interval = "1d"
        assert collector._get_interval_minutes() == 1440
    
    def test_get_granularity(self, test_config):
        """Test interval to granularity conversion."""
        collector = DataCollector(test_config)
        
        test_config.candle_interval = "1m"
        assert collector._get_granularity() == "ONE_MINUTE"
        
        test_config.candle_interval = "5m"
        assert collector._get_granularity() == "FIVE_MINUTE"
        
        test_config.candle_interval = "15m"
        assert collector._get_granularity() == "FIFTEEN_MINUTE"
        
        test_config.candle_interval = "1h"
        assert collector._get_granularity() == "ONE_HOUR"
        
        test_config.candle_interval = "4h"
        assert collector._get_granularity() == "SIX_HOUR"  # Note: Maps to 6h
        
        test_config.candle_interval = "1d"
        assert collector._get_granularity() == "ONE_DAY"
    
    def test_invalid_interval(self, test_config):
        """Test handling of invalid interval."""
        collector = DataCollector(test_config)
        
        test_config.candle_interval = "invalid"
        assert collector._get_interval_minutes() == 60  # Default
        assert collector._get_granularity() == "ONE_HOUR"  # Default


class TestHistoricalDataLoading:
    """Test historical data loading."""
    
    @patch('src.data.collector.RESTClient')
    async def test_load_historical_data_success(self, mock_rest_client, test_config, mock_coinbase_client):
        """Test successful historical data loading."""
        # Setup mock
        mock_rest_client.return_value = mock_coinbase_client
        
        collector = DataCollector(test_config)
        await collector.load_historical_data()
        
        # Verify candles were loaded
        assert len(collector.candles) > 0
        assert 'open' in collector.candles.columns
        assert 'high' in collector.candles.columns
        assert 'low' in collector.candles.columns
        assert 'close' in collector.candles.columns
        assert 'volume' in collector.candles.columns
    
    @patch('src.data.collector.RESTClient')
    async def test_load_historical_data_no_candles(self, mock_rest_client, test_config):
        """Test historical data loading with no candles returned."""
        # Setup mock to return no candles
        mock_client = Mock()
        mock_client.get_candles.return_value = None
        mock_rest_client.return_value = mock_client
        
        collector = DataCollector(test_config)
        await collector.load_historical_data()
        
        # Should handle gracefully
        assert len(collector.candles) == 0
    
    @patch('src.data.collector.RESTClient')
    async def test_load_historical_data_error(self, mock_rest_client, test_config):
        """Test historical data loading with API error."""
        # Setup mock to raise exception
        mock_client = Mock()
        mock_client.get_candles.side_effect = Exception("API Error")
        mock_rest_client.return_value = mock_client
        
        collector = DataCollector(test_config)
        
        with pytest.raises(Exception, match="API Error"):
            await collector.load_historical_data()


class TestLatestDataFetching:
    """Test latest data fetching."""
    
    @patch('src.data.collector.RESTClient')
    async def test_fetch_latest_data_success(self, mock_rest_client, test_config, mock_coinbase_client):
        """Test successful latest data fetching."""
        mock_rest_client.return_value = mock_coinbase_client
        
        collector = DataCollector(test_config)
        
        # Setup callback
        price_updates = []
        async def price_callback(price):
            price_updates.append(price)
        collector.on_price_update = price_callback
        
        await collector.fetch_latest_data()
        
        assert collector.latest_price == 50000.0
        assert len(price_updates) == 1
        assert price_updates[0] == 50000.0
    
    @patch('src.data.collector.RESTClient')
    async def test_fetch_latest_data_no_ticker(self, mock_rest_client, test_config):
        """Test latest data fetching with no ticker data."""
        mock_client = Mock()
        mock_client.get_product.return_value = None
        mock_rest_client.return_value = mock_client
        
        collector = DataCollector(test_config)
        await collector.fetch_latest_data()
        
        # Should handle gracefully
        assert collector.latest_price is None
    
    @patch('src.data.collector.RESTClient')
    async def test_fetch_latest_data_error(self, mock_rest_client, test_config):
        """Test latest data fetching with error."""
        mock_client = Mock()
        mock_client.get_product.side_effect = Exception("API Error")
        mock_rest_client.return_value = mock_client
        
        collector = DataCollector(test_config)
        
        # Should handle gracefully and not raise
        await collector.fetch_latest_data()
        assert collector.latest_price is None


class TestCandleUpdates:
    """Test candle data updates."""
    
    @patch('src.data.collector.RESTClient')
    async def test_update_candles_new_candle(self, mock_rest_client, test_config, mock_coinbase_client):
        """Test updating with new candle."""
        mock_rest_client.return_value = mock_coinbase_client
        
        collector = DataCollector(test_config)
        
        # Load some initial data
        await collector.load_historical_data()
        initial_count = len(collector.candles)
        
        # Setup callback
        candle_updates = []
        async def candle_callback(candles):
            candle_updates.append(len(candles))
        collector.on_candle_update = candle_callback
        
        # Update candles
        await collector._update_candles()
        
        # Should have updated or added candle
        assert len(candle_updates) > 0
    
    @patch('src.data.collector.RESTClient')
    async def test_update_candles_error(self, mock_rest_client, test_config):
        """Test candle update with error."""
        mock_client = Mock()
        mock_client.get_candles.side_effect = Exception("API Error")
        mock_rest_client.return_value = mock_client
        
        collector = DataCollector(test_config)
        
        # Should handle gracefully
        await collector._update_candles()


class TestWebSocketHandling:
    """Test WebSocket message handling."""
    
    def test_handle_ticker_message(self, test_config):
        """Test handling ticker WebSocket messages."""
        collector = DataCollector(test_config)
        
        # Setup callback
        price_updates = []
        async def price_callback(price):
            price_updates.append(price)
        collector.on_price_update = price_callback
        
        # Simulate ticker message
        ticker_message = json.dumps({
            "type": "ticker",
            "price": "51000.50"
        })
        
        collector._handle_ws_message(ticker_message)
        
        assert collector.latest_price == 51000.50
    
    def test_handle_l2update_message(self, test_config):
        """Test handling L2 update WebSocket messages."""
        collector = DataCollector(test_config)
        
        # Simulate L2 update message
        l2_message = json.dumps({
            "type": "l2update",
            "changes": [
                ["buy", "50000", "0.1"],
                ["sell", "50100", "0.2"]
            ]
        })
        
        # Should handle gracefully (implementation depends on requirements)
        collector._handle_ws_message(l2_message)
    
    def test_handle_invalid_message(self, test_config):
        """Test handling invalid WebSocket messages."""
        collector = DataCollector(test_config)
        
        # Should handle invalid JSON gracefully
        collector._handle_ws_message("invalid json")
        
        # Should handle missing fields gracefully
        collector._handle_ws_message('{"type": "unknown"}')
    
    def test_handle_ws_error(self, test_config):
        """Test WebSocket error handling."""
        collector = DataCollector(test_config)
        
        # Should handle gracefully
        error = Exception("WebSocket error")
        collector._handle_ws_error(error)
    
    def test_handle_ws_close(self, test_config):
        """Test WebSocket close handling."""
        collector = DataCollector(test_config)
        
        # Mock the start_websocket method to avoid actual reconnection
        collector.start_websocket = AsyncMock()
        
        # Should handle gracefully
        collector._handle_ws_close()


class TestPollingMode:
    """Test REST API polling mode."""
    
    @patch('src.data.collector.RESTClient')
    async def test_start_polling(self, mock_rest_client, test_config, mock_coinbase_client):
        """Test starting polling mode."""
        mock_rest_client.return_value = mock_coinbase_client
        test_config.data_fetch_interval = 0.1  # Very short for testing
        
        collector = DataCollector(test_config)
        
        # Start polling for a short time
        polling_task = asyncio.create_task(collector.start_polling())
        
        # Let it run briefly
        await asyncio.sleep(0.15)
        
        # Cancel the task
        polling_task.cancel()
        
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
        
        # Should have made at least one call
        assert collector.latest_price is not None
    
    @patch('src.data.collector.RESTClient')
    async def test_polling_with_errors(self, mock_rest_client, test_config):
        """Test polling mode with errors."""
        # Setup mock to raise exception
        mock_client = Mock()
        mock_client.get_product.side_effect = Exception("API Error")
        mock_rest_client.return_value = mock_client
        
        test_config.data_fetch_interval = 0.1
        collector = DataCollector(test_config)
        
        # Start polling for a short time
        polling_task = asyncio.create_task(collector.start_polling())
        
        # Let it run briefly
        await asyncio.sleep(0.15)
        
        # Cancel the task
        polling_task.cancel()
        
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
        
        # Should handle errors gracefully


class TestDataRetrieval:
    """Test data retrieval methods."""
    
    def test_get_latest_candles(self, test_config, sample_candles):
        """Test getting latest candles."""
        collector = DataCollector(test_config)
        collector.candles = sample_candles
        
        # Get last 10 candles
        latest = collector.get_latest_candles(10)
        
        assert len(latest) == 10
        assert isinstance(latest, pd.DataFrame)
        assert latest.index.equals(sample_candles.tail(10).index)
    
    def test_get_latest_candles_more_than_available(self, test_config, sample_candles):
        """Test getting more candles than available."""
        collector = DataCollector(test_config)
        collector.candles = sample_candles.head(5)  # Only 5 candles
        
        # Request 10 candles
        latest = collector.get_latest_candles(10)
        
        assert len(latest) == 5  # Should return all available
    
    def test_get_latest_price(self, test_config):
        """Test getting latest price."""
        collector = DataCollector(test_config)
        
        # No price set
        assert collector.get_latest_price() is None
        
        # Set price
        collector.latest_price = 50000.0
        assert collector.get_latest_price() == 50000.0


class TestStartStop:
    """Test start and stop functionality."""
    
    @patch('src.data.collector.DataCollector.load_historical_data')
    @patch('src.data.collector.DataCollector.start_websocket')
    async def test_start_with_websocket(self, mock_start_ws, mock_load_hist, test_config):
        """Test starting data collector with WebSocket enabled."""
        test_config.websocket_enabled = True
        mock_load_hist.return_value = None
        mock_start_ws.return_value = None
        
        collector = DataCollector(test_config)
        
        # Start for a brief moment
        start_task = asyncio.create_task(collector.start())
        await asyncio.sleep(0.01)
        start_task.cancel()
        
        try:
            await start_task
        except asyncio.CancelledError:
            pass
        
        mock_load_hist.assert_called_once()
        mock_start_ws.assert_called_once()
    
    @patch('src.data.collector.DataCollector.load_historical_data')
    @patch('src.data.collector.DataCollector.start_polling')
    async def test_start_with_polling(self, mock_start_poll, mock_load_hist, test_config):
        """Test starting data collector with polling enabled."""
        test_config.websocket_enabled = False
        mock_load_hist.return_value = None
        mock_start_poll.return_value = None
        
        collector = DataCollector(test_config)
        
        # Start for a brief moment
        start_task = asyncio.create_task(collector.start())
        await asyncio.sleep(0.01)
        start_task.cancel()
        
        try:
            await start_task
        except asyncio.CancelledError:
            pass
        
        mock_load_hist.assert_called_once()
        mock_start_poll.assert_called_once()
    
    async def test_stop(self, test_config):
        """Test stopping data collector."""
        collector = DataCollector(test_config)
        
        # Mock WebSocket client
        collector.ws_client = AsyncMock()
        
        await collector.stop()
        
        collector.ws_client.close.assert_called_once()


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_callbacks_none(self, test_config):
        """Test behavior when callbacks are None."""
        collector = DataCollector(test_config)
        
        # Should handle None callbacks gracefully
        ticker_message = json.dumps({
            "type": "ticker",
            "price": "51000.50"
        })
        
        collector._handle_ws_message(ticker_message)
        assert collector.latest_price == 51000.50
    
    @patch('src.data.collector.RESTClient')
    async def test_empty_candle_response(self, mock_rest_client, test_config):
        """Test handling empty candle response."""
        mock_client = Mock()
        mock_candles = Mock()
        mock_candles.candles = []  # Empty list
        mock_client.get_candles.return_value = mock_candles
        mock_rest_client.return_value = mock_client
        
        collector = DataCollector(test_config)
        await collector.load_historical_data()
        
        assert len(collector.candles) == 0
    
    def test_malformed_websocket_data(self, test_config):
        """Test handling malformed WebSocket data."""
        collector = DataCollector(test_config)
        
        # Test various malformed messages
        malformed_messages = [
            "not json",
            "{}",  # Empty object
            '{"type": "ticker"}',  # Missing price
            '{"price": "invalid"}',  # Invalid price format
        ]
        
        for message in malformed_messages:
            # Should not raise exceptions
            collector._handle_ws_message(message)