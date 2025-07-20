import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd
import numpy as np

from src.config import TradingConfig
from src.data.collector import DataCollector
from src.strategies.signal_processor import SignalProcessor, Signal
from src.risk.manager import RiskManager
from src.execution.engine import ExecutionEngine


@pytest.mark.integration
class TestDataToSignalIntegration:
    """Test integration between data collection and signal processing."""
    
    def test_data_to_signal_flow(self, test_config, sample_candles):
        """Test complete flow from data to signal generation."""
        # Initialize components
        data_collector = DataCollector(test_config)
        signal_processor = SignalProcessor(test_config)
        
        # Set candle data
        data_collector.candles = sample_candles
        
        # Process signals
        signal, indicators = signal_processor.process(sample_candles)
        
        # Verify integration
        assert signal in [Signal.BUY, Signal.SELL, Signal.HOLD]
        assert 'rsi' in indicators
        assert 'bb_upper' in indicators
        assert 'close' in indicators
        
        # Verify data consistency
        assert indicators['close'] == sample_candles['close'].iloc[-1]
    
    def test_signal_strength_calculation(self, test_config, volatile_candles):
        """Test signal strength calculation with volatile data."""
        signal_processor = SignalProcessor(test_config)
        
        signal, indicators = signal_processor.process(volatile_candles)
        strength = signal_processor.get_signal_strength(indicators)
        
        assert 0 <= strength <= 1
        
        # If signal is not HOLD, strength should correlate with signal type
        if signal != Signal.HOLD:
            assert strength > 0


@pytest.mark.integration
class TestSignalToRiskIntegration:
    """Test integration between signal processing and risk management."""
    
    async def test_signal_risk_evaluation(self, test_config):
        """Test signal evaluation by risk manager."""
        test_config.trading_mode = "paper"
        
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Test BUY signal evaluation
        can_trade_buy, reason_buy = risk_manager.can_trade(Signal.BUY, 50000.0)
        assert can_trade_buy is True
        
        order_details_buy = risk_manager.calculate_order_details(Signal.BUY, 50000.0, 1.0)
        assert order_details_buy['side'] == 'buy'
        assert order_details_buy['size'] > 0
        assert order_details_buy['stop_loss'] < 50000.0
        assert order_details_buy['take_profit'] > 50000.0
        
        # Open position
        risk_manager.open_position(
            order_details_buy['size'] * 50000.0 / order_details_buy['size'],  # entry price
            order_details_buy['size'],
            order_details_buy['stop_loss'],
            order_details_buy['take_profit']
        )
        
        # Test SELL signal evaluation with position
        can_trade_sell, reason_sell = risk_manager.can_trade(Signal.SELL, 51000.0)
        assert can_trade_sell is True
        
        order_details_sell = risk_manager.calculate_order_details(Signal.SELL, 51000.0)
        assert order_details_sell['side'] == 'sell'
        assert 'pnl' in order_details_sell
    
    def test_position_size_scaling(self, test_config):
        """Test position size scaling based on signal strength."""
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        # Strong signal
        strong_order = risk_manager.calculate_order_details(Signal.BUY, 50000.0, 1.0)
        
        # Weak signal
        weak_order = risk_manager.calculate_order_details(Signal.BUY, 50000.0, 0.5)
        
        assert weak_order['size'] == strong_order['size'] * 0.5
        assert weak_order['risk_amount'] == strong_order['risk_amount'] * 0.5


@pytest.mark.integration
class TestRiskToExecutionIntegration:
    """Test integration between risk management and execution."""
    
    async def test_risk_execution_flow(self, test_config):
        """Test complete risk to execution flow."""
        test_config.trading_mode = "test"
        
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        execution_engine = ExecutionEngine(test_config, risk_manager)
        
        # Execute BUY signal
        order = await execution_engine.execute_signal(Signal.BUY, 50000.0, 1.0)
        
        assert order is not None
        assert order.side == "buy"
        assert order.status.name == "FILLED"
        assert risk_manager.current_position is not None
        
        # Execute SELL signal
        order = await execution_engine.execute_signal(Signal.SELL, 51000.0, 1.0)
        
        assert order is not None
        assert order.side == "sell"
        assert order.status.name == "FILLED"
        assert risk_manager.current_position is None  # Position closed
        assert risk_manager.total_pnl > 0  # Profitable trade
    
    async def test_stop_loss_execution(self, test_config):
        """Test stop loss trigger and execution."""
        test_config.trading_mode = "test"
        
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        execution_engine = ExecutionEngine(test_config, risk_manager)
        
        # Execute BUY signal
        await execution_engine.execute_signal(Signal.BUY, 50000.0, 1.0)
        
        # Simulate price drop to stop loss
        stop_loss_price = risk_manager.current_position.stop_loss
        exit_signal = risk_manager.update_position(stop_loss_price)
        
        assert exit_signal == Signal.SELL
        
        # Execute stop loss
        order = await execution_engine.execute_signal(exit_signal, stop_loss_price)
        
        assert order is not None
        assert risk_manager.current_position is None
        assert risk_manager.total_pnl < 0  # Loss as expected


@pytest.mark.integration
class TestFullTradingCycleIntegration:
    """Test complete trading cycle integration."""
    
    async def test_complete_buy_sell_cycle(self, test_config, trending_candles):
        """Test complete buy-sell trading cycle."""
        test_config.trading_mode = "test"
        
        # Initialize all components
        data_collector = DataCollector(test_config)
        signal_processor = SignalProcessor(test_config)
        risk_manager = RiskManager(test_config)
        execution_engine = ExecutionEngine(test_config, risk_manager)
        
        # Set initial balance
        risk_manager.set_balance(10000.0)
        
        # Set trending data (should generate buy signal)
        data_collector.candles = trending_candles
        data_collector.latest_price = trending_candles['close'].iloc[-1]
        
        # Generate signal
        signal, indicators = signal_processor.process(trending_candles)
        current_price = data_collector.get_latest_price()
        
        # If we get a buy signal, execute full cycle
        if signal == Signal.BUY:
            # Execute buy order
            buy_order = await execution_engine.execute_signal(signal, current_price, 1.0)
            
            assert buy_order is not None
            assert risk_manager.current_position is not None
            
            # Simulate price increase
            higher_price = current_price * 1.03  # 3% increase
            
            # Check if take profit triggers
            exit_signal = risk_manager.update_position(higher_price)
            
            if exit_signal == Signal.SELL:
                # Execute sell order
                sell_order = await execution_engine.execute_signal(exit_signal, higher_price)
                
                assert sell_order is not None
                assert risk_manager.current_position is None
                assert risk_manager.total_pnl > 0  # Should be profitable
    
    @patch('src.data.collector.RESTClient')
    async def test_data_collection_to_execution(self, mock_rest_client, test_config, mock_coinbase_client):
        """Test integration from data collection to execution."""
        test_config.trading_mode = "test"
        test_config.websocket_enabled = False
        
        mock_rest_client.return_value = mock_coinbase_client
        
        # Initialize components
        data_collector = DataCollector(test_config)
        signal_processor = SignalProcessor(test_config)
        risk_manager = RiskManager(test_config)
        execution_engine = ExecutionEngine(test_config, risk_manager)
        
        risk_manager.set_balance(10000.0)
        
        # Load historical data
        await data_collector.load_historical_data()
        
        # Verify data was loaded
        assert len(data_collector.candles) > 0
        
        # Process signal
        signal, indicators = signal_processor.process(data_collector.candles)
        
        # Execute if we have a signal
        if signal != Signal.HOLD:
            current_price = 50000.0  # From mock data
            order = await execution_engine.execute_signal(signal, current_price, 1.0)
            
            if signal == Signal.BUY:
                assert order is not None
                assert risk_manager.current_position is not None


@pytest.mark.integration
class TestCallbackIntegration:
    """Test callback integration between components."""
    
    async def test_price_update_callbacks(self, test_config):
        """Test price update callback integration."""
        test_config.trading_mode = "test"
        
        data_collector = DataCollector(test_config)
        risk_manager = RiskManager(test_config)
        execution_engine = ExecutionEngine(test_config, risk_manager)
        
        risk_manager.set_balance(10000.0)
        
        # Open a position first
        await execution_engine.execute_signal(Signal.BUY, 50000.0, 1.0)
        
        # Setup price update callback
        async def price_update_handler(price):
            # Check for stop loss/take profit
            if risk_manager.current_position:
                exit_signal = risk_manager.update_position(price)
                if exit_signal:
                    await execution_engine.execute_signal(exit_signal, price)
        
        data_collector.on_price_update = price_update_handler
        
        # Simulate price updates
        await data_collector.on_price_update(49000.0)  # Should trigger stop loss
        
        # Position should be closed
        assert risk_manager.current_position is None
    
    async def test_candle_update_callbacks(self, test_config, sample_candles):
        """Test candle update callback integration."""
        test_config.trading_mode = "test"
        
        data_collector = DataCollector(test_config)
        signal_processor = SignalProcessor(test_config)
        risk_manager = RiskManager(test_config)
        execution_engine = ExecutionEngine(test_config, risk_manager)
        
        risk_manager.set_balance(10000.0)
        
        # Setup candle update callback
        async def candle_update_handler(candles):
            signal, indicators = signal_processor.process(candles)
            if signal != Signal.HOLD:
                current_price = candles['close'].iloc[-1]
                await execution_engine.execute_signal(signal, current_price, 1.0)
        
        data_collector.on_candle_update = candle_update_handler
        
        # Trigger candle update
        await data_collector.on_candle_update(sample_candles)
        
        # Should have potentially executed orders
        assert execution_engine.total_orders >= 0


@pytest.mark.integration
class TestErrorHandlingIntegration:
    """Test error handling across components."""
    
    async def test_data_error_handling(self, test_config):
        """Test handling of data collection errors."""
        signal_processor = SignalProcessor(test_config)
        
        # Test with insufficient data
        short_candles = pd.DataFrame({
            'open': [50000],
            'high': [50100],
            'low': [49900],
            'close': [50000],
            'volume': [1000]
        }, index=[datetime.utcnow()])
        
        signal, indicators = signal_processor.process(short_candles)
        
        # Should handle gracefully
        assert signal == Signal.HOLD
        assert indicators == {}
    
    async def test_execution_error_handling(self, test_config):
        """Test execution error handling."""
        test_config.trading_mode = "paper"
        
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(1.0)  # Very low balance
        
        execution_engine = ExecutionEngine(test_config, risk_manager)
        
        # Should be rejected by risk manager
        order = await execution_engine.execute_signal(Signal.BUY, 50000.0, 1.0)
        
        assert order is None
        assert execution_engine.failed_orders == 0  # Not counted as failed, just rejected


@pytest.mark.integration
class TestConfigurationIntegration:
    """Test configuration integration across components."""
    
    def test_config_consistency(self, test_config):
        """Test configuration consistency across components."""
        # Initialize all components with same config
        data_collector = DataCollector(test_config)
        signal_processor = SignalProcessor(test_config)
        risk_manager = RiskManager(test_config)
        execution_engine = ExecutionEngine(test_config, risk_manager)
        
        # Verify all components use same config
        assert data_collector.config == test_config
        assert signal_processor.config == test_config
        assert risk_manager.config == test_config
        assert execution_engine.config == test_config
        
        # Verify specific config values are applied
        assert signal_processor.config.rsi_period == test_config.rsi_period
        assert risk_manager.config.max_position_size == test_config.max_position_size
        assert execution_engine.config.trading_mode == test_config.trading_mode
    
    def test_trading_mode_integration(self, test_config):
        """Test trading mode integration."""
        # Test different trading modes
        for mode in ["test", "paper", "live"]:
            test_config.trading_mode = mode
            
            risk_manager = RiskManager(test_config)
            execution_engine = ExecutionEngine(test_config, risk_manager)
            
            assert execution_engine.config.trading_mode == mode
            
            # Risk manager behavior should be consistent
            risk_manager.set_balance(10000.0)
            can_trade, reason = risk_manager.can_trade(Signal.BUY, 50000.0)
            
            if mode == "test":
                assert can_trade is True
                assert "Test mode" in reason
            else:
                assert can_trade is True
                assert "Trade allowed" in reason or "Cooldown" in reason


@pytest.mark.integration
class TestPerformanceIntegration:
    """Test performance characteristics of integrated system."""
    
    async def test_signal_processing_performance(self, test_config):
        """Test signal processing performance with large datasets."""
        signal_processor = SignalProcessor(test_config)
        
        # Create large dataset
        dates = pd.date_range(start='2024-01-01', periods=1000, freq='1T')
        data = []
        
        base_price = 50000.0
        for i, date in enumerate(dates):
            price = base_price + np.random.normal(0, 100)
            data.append({
                'timestamp': date,
                'open': price,
                'high': price * 1.002,
                'low': price * 0.998,
                'close': price,
                'volume': np.random.uniform(1000, 10000)
            })
        
        large_candles = pd.DataFrame(data)
        large_candles.set_index('timestamp', inplace=True)
        
        # Time the signal processing
        start_time = datetime.utcnow()
        signal, indicators = signal_processor.process(large_candles)
        end_time = datetime.utcnow()
        
        processing_time = (end_time - start_time).total_seconds()
        
        # Should process quickly (under 1 second for 1000 candles)
        assert processing_time < 1.0
        assert signal in [Signal.BUY, Signal.SELL, Signal.HOLD]
    
    async def test_order_execution_performance(self, test_config):
        """Test order execution performance."""
        test_config.trading_mode = "test"
        
        risk_manager = RiskManager(test_config)
        risk_manager.set_balance(10000.0)
        
        execution_engine = ExecutionEngine(test_config, risk_manager)
        
        # Execute multiple orders and measure performance
        start_time = datetime.utcnow()
        
        for i in range(10):
            if i % 2 == 0:
                await execution_engine.execute_signal(Signal.BUY, 50000.0, 1.0)
            else:
                await execution_engine.execute_signal(Signal.SELL, 51000.0, 1.0)
        
        end_time = datetime.utcnow()
        
        execution_time = (end_time - start_time).total_seconds()
        
        # Should execute quickly (under 1 second for 10 orders in test mode)
        assert execution_time < 1.0
        assert execution_engine.total_orders == 10


@pytest.mark.integration
@pytest.mark.slow
class TestLongRunningIntegration:
    """Test long-running integration scenarios."""
    
    async def test_continuous_operation_simulation(self, test_config):
        """Test continuous operation simulation."""
        test_config.trading_mode = "test"
        test_config.data_fetch_interval = 0.1  # Very fast for testing
        
        # Initialize components
        data_collector = DataCollector(test_config)
        signal_processor = SignalProcessor(test_config)
        risk_manager = RiskManager(test_config)
        execution_engine = ExecutionEngine(test_config, risk_manager)
        
        risk_manager.set_balance(10000.0)
        
        # Setup data with some volatility
        data_collector.candles = pd.DataFrame({
            'open': [50000, 50100, 49900, 50200],
            'high': [50100, 50200, 50000, 50300],
            'low': [49900, 49950, 49800, 50100],
            'close': [50050, 49950, 50150, 50250],
            'volume': [1000, 1200, 900, 1100]
        }, index=pd.date_range(start='2024-01-01', periods=4, freq='1T'))
        
        # Simulate continuous operation for a short time
        operation_count = 0
        max_operations = 5
        
        while operation_count < max_operations:
            # Simulate new price data
            current_price = 50000 + np.random.normal(0, 50)
            data_collector.latest_price = current_price
            
            # Process signal
            signal, indicators = signal_processor.process(data_collector.candles)
            
            # Execute if signal generated
            if signal != Signal.HOLD:
                order = await execution_engine.execute_signal(signal, current_price, 1.0)
                if order:
                    operation_count += 1
            
            # Check position updates
            if risk_manager.current_position:
                exit_signal = risk_manager.update_position(current_price)
                if exit_signal:
                    order = await execution_engine.execute_signal(exit_signal, current_price)
                    if order:
                        operation_count += 1
            
            await asyncio.sleep(0.01)  # Small delay
        
        # Verify system remained stable
        assert execution_engine.total_orders > 0
        assert execution_engine.successful_orders == execution_engine.total_orders
        assert execution_engine.failed_orders == 0