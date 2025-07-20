import pandas as pd
import ta
from typing import Dict, Optional, Tuple
from enum import Enum

from src.utils.logger import get_logger
from src.config import TradingConfig


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalProcessor:
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = get_logger("SignalProcessor", config.log_level, config.log_file)
        
        # Signal history
        self.last_signal: Optional[Signal] = None
        self.signal_history: list = []
    
    def process(self, candles: pd.DataFrame) -> Tuple[Signal, Dict[str, float]]:
        """Process candles and generate trading signal."""
        if len(candles) < max(self.config.rsi_period, self.config.bollinger_period):
            self.logger.warning("Insufficient data for analysis", 
                              candles=len(candles),
                              required=max(self.config.rsi_period, self.config.bollinger_period))
            return Signal.HOLD, {}
        
        # Calculate indicators
        indicators = self._calculate_indicators(candles)
        
        # Generate signal
        signal = self._generate_signal(indicators)
        
        # Log signal
        self.logger.info("Signal generated", 
                        signal=signal.value,
                        rsi=round(indicators['rsi'], 2),
                        price=round(indicators['close'], 2),
                        bb_upper=round(indicators['bb_upper'], 2),
                        bb_lower=round(indicators['bb_lower'], 2))
        
        # Update history
        self.last_signal = signal
        self.signal_history.append({
            'timestamp': candles.index[-1],
            'signal': signal,
            'indicators': indicators
        })
        
        return signal, indicators
    
    def _calculate_indicators(self, candles: pd.DataFrame) -> Dict[str, float]:
        """Calculate technical indicators."""
        close_prices = candles['close']
        
        # Calculate RSI
        rsi_indicator = ta.momentum.RSIIndicator(
            close=close_prices,
            window=self.config.rsi_period
        )
        rsi = rsi_indicator.rsi().iloc[-1]
        
        # Calculate Bollinger Bands
        bb_indicator = ta.volatility.BollingerBands(
            close=close_prices,
            window=self.config.bollinger_period,
            window_dev=self.config.bollinger_std
        )
        bb_upper = bb_indicator.bollinger_hband().iloc[-1]
        bb_middle = bb_indicator.bollinger_mavg().iloc[-1]
        bb_lower = bb_indicator.bollinger_lband().iloc[-1]
        
        # Current price and volume
        current_close = close_prices.iloc[-1]
        current_volume = candles['volume'].iloc[-1]
        
        # Price position within Bollinger Bands
        bb_position = (current_close - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
        
        # Volume analysis
        avg_volume = candles['volume'].rolling(window=20).mean().iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        return {
            'rsi': rsi,
            'bb_upper': bb_upper,
            'bb_middle': bb_middle,
            'bb_lower': bb_lower,
            'bb_position': bb_position,
            'close': current_close,
            'volume': current_volume,
            'volume_ratio': volume_ratio,
            'avg_volume': avg_volume
        }
    
    def _generate_signal(self, indicators: Dict[str, float]) -> Signal:
        """Generate trading signal based on indicators."""
        rsi = indicators['rsi']
        close = indicators['close']
        bb_upper = indicators['bb_upper']
        bb_lower = indicators['bb_lower']
        bb_position = indicators['bb_position']
        volume_ratio = indicators['volume_ratio']
        
        # Initialize signal
        signal = Signal.HOLD
        
        # RSI-based signals
        rsi_buy = rsi < self.config.rsi_oversold
        rsi_sell = rsi > self.config.rsi_overbought
        
        # Bollinger Band signals
        bb_buy = close <= bb_lower
        bb_sell = close >= bb_upper
        
        # Combined signals with confirmation
        if rsi_buy and bb_buy:
            # Strong buy signal: Both RSI oversold and price at lower BB
            signal = Signal.BUY
            self.logger.debug("Strong BUY signal: RSI oversold + Lower BB touched")
            
        elif rsi_buy and bb_position < 0.3:
            # Moderate buy signal: RSI oversold and price in lower 30% of BB
            signal = Signal.BUY
            self.logger.debug("Moderate BUY signal: RSI oversold + Low BB position")
            
        elif bb_buy and rsi < 40:
            # Moderate buy signal: Price at lower BB with RSI below 40
            signal = Signal.BUY
            self.logger.debug("Moderate BUY signal: Lower BB + RSI < 40")
            
        elif rsi_sell and bb_sell:
            # Strong sell signal: Both RSI overbought and price at upper BB
            signal = Signal.SELL
            self.logger.debug("Strong SELL signal: RSI overbought + Upper BB touched")
            
        elif rsi_sell and bb_position > 0.7:
            # Moderate sell signal: RSI overbought and price in upper 30% of BB
            signal = Signal.SELL
            self.logger.debug("Moderate SELL signal: RSI overbought + High BB position")
            
        elif bb_sell and rsi > 60:
            # Moderate sell signal: Price at upper BB with RSI above 60
            signal = Signal.SELL
            self.logger.debug("Moderate SELL signal: Upper BB + RSI > 60")
        
        # Volume confirmation
        if signal != Signal.HOLD and volume_ratio < 0.5:
            # Weak volume, downgrade signal
            self.logger.debug("Signal downgraded due to low volume", 
                            original_signal=signal.value,
                            volume_ratio=round(volume_ratio, 2))
            signal = Signal.HOLD
        
        # Prevent rapid signal changes
        if self._should_filter_signal(signal):
            self.logger.debug("Signal filtered to prevent whipsaw", 
                            attempted_signal=signal.value)
            signal = Signal.HOLD
        
        return signal
    
    def _should_filter_signal(self, signal: Signal) -> bool:
        """Check if signal should be filtered to prevent whipsaws."""
        if not self.signal_history or signal == Signal.HOLD:
            return False
        
        # Don't allow opposite signals too quickly
        recent_signals = [h for h in self.signal_history[-5:] if h['signal'] != Signal.HOLD]
        
        if recent_signals:
            last_meaningful_signal = recent_signals[-1]['signal']
            
            # Prevent buy after recent sell and vice versa
            if (signal == Signal.BUY and last_meaningful_signal == Signal.SELL) or \
               (signal == Signal.SELL and last_meaningful_signal == Signal.BUY):
                return True
        
        return False
    
    def get_signal_strength(self, indicators: Dict[str, float]) -> float:
        """Calculate signal strength (0-1) based on indicators."""
        rsi = indicators['rsi']
        bb_position = indicators['bb_position']
        
        # RSI strength
        if rsi <= self.config.rsi_oversold:
            rsi_strength = (self.config.rsi_oversold - rsi) / self.config.rsi_oversold
        elif rsi >= self.config.rsi_overbought:
            rsi_strength = (rsi - self.config.rsi_overbought) / (100 - self.config.rsi_overbought)
        else:
            rsi_strength = 0
        
        # BB strength
        if bb_position <= 0.1:
            bb_strength = (0.1 - bb_position) / 0.1
        elif bb_position >= 0.9:
            bb_strength = (bb_position - 0.9) / 0.1
        else:
            bb_strength = 0
        
        # Combined strength
        return min(1.0, (rsi_strength + bb_strength) / 2)