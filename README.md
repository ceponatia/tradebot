# Cryptocurrency Trading Bot

An automated cryptocurrency trading bot that uses technical analysis indicators (RSI and Bollinger Bands) to execute trades on Coinbase.

## Features

- Real-time market data collection via WebSocket/REST API
- Technical indicators: RSI and Bollinger Bands
- Risk management with position sizing and stop-loss/take-profit
- Multiple trading modes: test, paper, and live
- Structured logging and optional Discord/Telegram notifications
- Modular architecture for easy extension

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and configure your settings:
```bash
cp .env.example .env
```

3. Add your Coinbase API credentials to `.env`

## Usage

Run the bot:
```bash
python main.py
```

## Configuration

Key settings in `.env`:
- `TRADING_MODE`: test, paper, or live
- `TRADING_PAIR`: Trading pair (e.g., BTC-USD)
- Risk management parameters
- Strategy parameters (RSI/Bollinger Bands)

## Architecture

- `src/config.py`: Configuration management
- `src/data/`: Market data collection
- `src/strategies/`: Trading signal generation
- `src/risk/`: Risk management
- `src/execution/`: Order execution
- `src/utils/`: Logging and utilities

## Safety

Always test strategies thoroughly in test/paper mode before live trading. Never risk more than you can afford to lose.