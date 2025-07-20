# Cryptocurrency Trading Bot Project

## Overview
This is a Python-based automated cryptocurrency trading bot that connects to Coinbase Developer API for real-time trading. The bot uses technical analysis indicators (RSI and Bollinger Bands) to generate trading signals and executes trades automatically with built-in risk management.

## Key Technologies
- **Language**: Python 3.10+
- **Libraries**: ccxt, ta, pandas, asyncio, websocket-client/websockets
- **Exchange**: Coinbase Developer API
- **Indicators**: RSI (Relative Strength Index), Bollinger Bands

## Architecture Components
1. **Data Collector**: Fetches live market data via WebSocket or REST
2. **Signal Processor**: Computes technical indicators and generates buy/sell/hold signals
3. **Risk Manager**: Handles position sizing, cooldowns, and stop-loss conditions
4. **Execution Engine**: Places orders on Coinbase with retry logic
5. **Logger/Alerts**: Structured logging with optional Discord/Telegram notifications

## Development Phases
1. **Phase 1**: Environment setup and API authentication
2. **Phase 2**: Real-time data feed implementation
3. **Phase 3**: Strategy engine with RSI + Bollinger Bands
4. **Phase 4**: Risk management and order execution
5. **Phase 5**: Logging and monitoring systems
6. **Phase 6**: Testing (backtesting, paper trading, live trial)

## Key Requirements
- Low-latency response to market data (< 2 seconds)
- Secure API key storage in `.env` file (COINBASE_API_NAME and COINBASE_API_KEY)
- Continuous operation with automatic error recovery
- Modular and extensible architecture
- Optional test/paper trading mode

## Important Notes
- This is a trading bot with full execution capabilities - handle with care
- Always test strategies thoroughly before live trading
- Implement proper risk management and position sizing
- Keep API keys secure and never commit them to version control