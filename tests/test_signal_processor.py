import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.strategies.signal_processor import SignalProcessor, Signal


class TestSignalProcessor:
    """Test the SignalProcessor class."""
    
    def test_initialization(self, test_config):
        """Test signal processor initialization."""
        processor = SignalProcessor(test_config)
        
        assert processor.config == test_config
        assert processor.last_signal is None
        assert processor.signal_history == []
    
    def test_insufficient_data(self, test_config):
        """Test signal processing with insufficient data."""
        processor = SignalProcessor(test_config)
        
        # Create data with insufficient candles
        dates = pd.date_range(start='2024-01-01', periods=5, freq='1T')
        data = []
        for date in dates:
            data.append({
                'timestamp': date,
                'open': 50000,
                'high': 50100,
                'low': 49900,
                'close': 50000,
                'volume': 1000
            })
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        
        signal, indicators = processor.process(df)
        
        assert signal == Signal.HOLD
        assert indicators == {}
    
    def test_basic_signal_generation(self, test_config, sample_candles):
        """Test basic signal generation with valid data."""
        processor = SignalProcessor(test_config)
        
        signal, indicators = processor.process(sample_candles)
        
        assert signal in [Signal.BUY, Signal.SELL, Signal.HOLD]
        assert 'rsi' in indicators
        assert 'bb_upper' in indicators
        assert 'bb_lower' in indicators
        assert 'close' in indicators
        assert 'volume' in indicators


class TestTechnicalIndicators:
    """Test technical indicator calculations."""
    
    def test_rsi_calculation(self, test_config, sample_candles):
        """Test RSI calculation."""
        processor = SignalProcessor(test_config)
        indicators = processor._calculate_indicators(sample_candles)
        
        assert 'rsi' in indicators
        assert 0 <= indicators['rsi'] <= 100
    
    def test_bollinger_bands_calculation(self, test_config, sample_candles):
        """Test Bollinger Bands calculation."""
        processor = SignalProcessor(test_config)
        indicators = processor._calculate_indicators(sample_candles)
        
        assert 'bb_upper' in indicators
        assert 'bb_middle' in indicators
        assert 'bb_lower' in indicators
        
        # Upper band should be higher than middle, middle higher than lower
        assert indicators['bb_upper'] > indicators['bb_middle']
        assert indicators['bb_middle'] > indicators['bb_lower']
        
        # Current price should be within reasonable bounds
        assert indicators['bb_lower'] <= indicators['close'] <= indicators['bb_upper'] * 1.1  # Allow some overshoot
    
    def test_bb_position_calculation(self, test_config, sample_candles):
        """Test Bollinger Band position calculation."""
        processor = SignalProcessor(test_config)
        indicators = processor._calculate_indicators(sample_candles)
        
        assert 'bb_position' in indicators
        assert 0 <= indicators['bb_position'] <= 1
    
    def test_volume_analysis(self, test_config, sample_candles):
        """Test volume analysis."""
        processor = SignalProcessor(test_config)
        indicators = processor._calculate_indicators(sample_candles)
        
        assert 'volume' in indicators
        assert 'volume_ratio' in indicators
        assert 'avg_volume' in indicators
        
        assert indicators['volume'] > 0
        assert indicators['volume_ratio'] > 0
        assert indicators['avg_volume'] > 0


class TestSignalGeneration:
    """Test signal generation logic."""
    
    def test_oversold_conditions(self, test_config):
        """Test buy signals in oversold conditions."""
        processor = SignalProcessor(test_config)
        
        # Create oversold conditions
        indicators = {
            'rsi': 25,  # Below oversold threshold
            'close': 49000,
            'bb_upper': 51000,
            'bb_middle': 50000,
            'bb_lower': 49000,  # Price at lower band
            'bb_position': 0.0,
            'volume_ratio': 1.5  # Good volume
        }
        
        signal = processor._generate_signal(indicators)
        assert signal == Signal.BUY
    
    def test_overbought_conditions(self, test_config):
        """Test sell signals in overbought conditions."""
        processor = SignalProcessor(test_config)
        
        # Create overbought conditions
        indicators = {
            'rsi': 75,  # Above overbought threshold
            'close': 51000,
            'bb_upper': 51000,  # Price at upper band
            'bb_middle': 50000,
            'bb_lower': 49000,
            'bb_position': 1.0,
            'volume_ratio': 1.5  # Good volume
        }
        
        signal = processor._generate_signal(indicators)
        assert signal == Signal.SELL
    
    def test_neutral_conditions(self, test_config):
        """Test hold signals in neutral conditions."""
        processor = SignalProcessor(test_config)
        
        # Create neutral conditions
        indicators = {
            'rsi': 50,  # Neutral RSI
            'close': 50000,
            'bb_upper': 51000,
            'bb_middle': 50000,  # Price at middle band
            'bb_lower': 49000,
            'bb_position': 0.5,
            'volume_ratio': 1.0
        }
        
        signal = processor._generate_signal(indicators)
        assert signal == Signal.HOLD
    
    def test_low_volume_filter(self, test_config):
        """Test signal filtering due to low volume."""
        processor = SignalProcessor(test_config)
        
        # Create buy conditions but with low volume
        indicators = {
            'rsi': 25,  # Oversold
            'close': 49000,
            'bb_upper': 51000,
            'bb_middle': 50000,
            'bb_lower': 49000,
            'bb_position': 0.0,
            'volume_ratio': 0.3  # Low volume
        }
        
        signal = processor._generate_signal(indicators)
        assert signal == Signal.HOLD  # Should be filtered due to low volume
    
    def test_moderate_signals(self, test_config):
        """Test moderate signal conditions."""
        processor = SignalProcessor(test_config)
        
        # Moderate buy: RSI oversold but price not at lower BB
        indicators = {
            'rsi': 25,
            'close': 49500,
            'bb_upper': 51000,
            'bb_middle': 50000,
            'bb_lower': 49000,
            'bb_position': 0.25,  # Lower 25% of BB
            'volume_ratio': 1.0
        }
        
        signal = processor._generate_signal(indicators)
        assert signal == Signal.BUY


class TestSignalHistory:
    """Test signal history and filtering."""
    
    def test_signal_history_tracking(self, test_config, sample_candles):
        """Test that signal history is properly tracked."""
        processor = SignalProcessor(test_config)
        
        # Process same data multiple times
        for _ in range(3):
            signal, indicators = processor.process(sample_candles)
        
        assert len(processor.signal_history) == 3
        assert processor.last_signal is not None
        
        # Check history structure
        for history_entry in processor.signal_history:
            assert 'timestamp' in history_entry
            assert 'signal' in history_entry
            assert 'indicators' in history_entry
    
    def test_whipsaw_filtering(self, test_config):
        """Test whipsaw filtering to prevent rapid signal changes."""
        processor = SignalProcessor(test_config)
        
        # Simulate a sell signal first
        processor.signal_history = [{
            'timestamp': datetime.utcnow(),
            'signal': Signal.SELL,
            'indicators': {}
        }]
        
        # Now try to generate a buy signal
        indicators = {
            'rsi': 25,
            'close': 49000,
            'bb_upper': 51000,
            'bb_middle': 50000,
            'bb_lower': 49000,
            'bb_position': 0.0,
            'volume_ratio': 1.5
        }
        
        signal = processor._generate_signal(indicators)
        
        # Should be filtered due to recent opposite signal
        filtered = processor._should_filter_signal(signal)
        assert filtered is True
    
    def test_no_filtering_for_hold(self, test_config):
        """Test that HOLD signals are never filtered."""
        processor = SignalProcessor(test_config)
        
        # Add some signal history
        processor.signal_history = [{
            'timestamp': datetime.utcnow(),
            'signal': Signal.SELL,
            'indicators': {}
        }]
        
        # HOLD signals should never be filtered
        filtered = processor._should_filter_signal(Signal.HOLD)
        assert filtered is False


class TestSignalStrength:
    """Test signal strength calculation."""
    
    def test_strong_oversold_strength(self, test_config):
        """Test signal strength for strong oversold conditions."""
        processor = SignalProcessor(test_config)
        
        indicators = {
            'rsi': 15,  # Very oversold
            'bb_position': 0.0,  # At lower band
            'close': 49000,
            'bb_upper': 51000,
            'bb_lower': 49000
        }
        
        strength = processor.get_signal_strength(indicators)
        assert 0.5 <= strength <= 1.0  # Should be strong
    
    def test_weak_signal_strength(self, test_config):
        """Test signal strength for weak conditions."""
        processor = SignalProcessor(test_config)
        
        indicators = {
            'rsi': 50,  # Neutral
            'bb_position': 0.5,  # Middle of bands
            'close': 50000,
            'bb_upper': 51000,
            'bb_lower': 49000
        }
        
        strength = processor.get_signal_strength(indicators)
        assert strength == 0.0  # Should be weak
    
    def test_strong_overbought_strength(self, test_config):
        """Test signal strength for strong overbought conditions."""
        processor = SignalProcessor(test_config)
        
        indicators = {
            'rsi': 85,  # Very overbought
            'bb_position': 1.0,  # At upper band
            'close': 51000,
            'bb_upper': 51000,
            'bb_lower': 49000
        }
        
        strength = processor.get_signal_strength(indicators)
        assert 0.5 <= strength <= 1.0  # Should be strong


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_extreme_price_movements(self, test_config, volatile_candles):
        """Test signal processing with extreme price movements."""
        processor = SignalProcessor(test_config)
        
        signal, indicators = processor.process(volatile_candles)
        
        # Should handle volatile data without errors
        assert signal in [Signal.BUY, Signal.SELL, Signal.HOLD]
        assert all(key in indicators for key in ['rsi', 'bb_upper', 'bb_lower'])
    
    def test_trending_market(self, test_config, trending_candles):
        """Test signal processing in trending market."""
        processor = SignalProcessor(test_config)
        
        signal, indicators = processor.process(trending_candles)
        
        # Should handle trending data
        assert signal in [Signal.BUY, Signal.SELL, Signal.HOLD]
        assert indicators['rsi'] >= 0 and indicators['rsi'] <= 100
    
    def test_identical_prices(self, test_config):
        """Test signal processing with identical prices (no volatility)."""
        processor = SignalProcessor(test_config)
        
        # Create data with identical prices
        dates = pd.date_range(start='2024-01-01', periods=50, freq='1T')
        data = []
        for date in dates:
            data.append({
                'timestamp': date,
                'open': 50000,
                'high': 50000,
                'low': 50000,
                'close': 50000,
                'volume': 1000
            })
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        
        signal, indicators = processor.process(df)
        
        # Should handle zero volatility without errors
        assert signal in [Signal.BUY, Signal.SELL, Signal.HOLD]
        assert 'rsi' in indicators
    
    def test_zero_volume(self, test_config, sample_candles):
        """Test signal processing with zero volume data."""
        processor = SignalProcessor(test_config)
        
        # Set all volumes to zero
        sample_candles['volume'] = 0
        
        signal, indicators = processor.process(sample_candles)
        
        # Should handle zero volume
        assert signal in [Signal.BUY, Signal.SELL, Signal.HOLD]
        assert indicators['volume_ratio'] > 0  # Should handle division by zero