# 📐 System Architecture: Crypto Trading Bot

## Overview

This document outlines the system architecture for a real-time, automated cryptocurrency trading bot using Python and the Coinbase Pro API.

---

## High-Level Architecture

```
[ Coinbase API ]
     |
     | WebSocket or REST (via ccxt or custom)
     ↓
[ Data Collector Module ]
     ↓
[ Signal Processor ]
     ↳ Technical Analysis (ta)
     ↳ Strategy Logic (RSI + BB, etc.)
     ↓
[ Risk Manager ]
     ↳ Position sizing
     ↳ Cooldown logic
     ↳ Stop-loss/take-profit conditions
     ↓
[ Execution Engine ]
     ↳ Executes orders via ccxt
     ↳ Handles failures & retries
     ↓
[ Logger / Alert System ]
     ↳ File logs, optional Discord/Telegram alerts
     ↳ Error & trade audit trail
```

---

## Module Responsibilities

### Data Collector
- Fetch live market data via WebSocket or REST
- Format and buffer candle data

### Signal Processor
- Compute indicators (RSI, Bollinger Bands)
- Generate buy/sell/hold signals

### Risk Manager
- Determine trade size based on portfolio
- Enforce cooldowns and stop-loss conditions

### Execution Engine
- Place orders on Coinbase via authenticated API
- Handle retries and order verification

### Logger / Alerts
- Write structured logs to disk
- Notify user of significant events or errors

---

## Technologies Used

- Python 3.10+
- ccxt
- ta
- pandas
- asyncio
- websocket-client or websockets
