# 📆 Project Schedule and Task Breakdown

## Phase 1: Initialization

- [ ] Create virtual environment and install dependencies
- [ ] Scaffold project structure
- [ ] Configure `.env` for secrets
- [ ] Set up Coinbase API authentication with `ccxt`

## Phase 2: Data Feed

- [ ] Implement WebSocket and/or REST feed for real-time data
- [ ] Buffer OHLCV data for strategy use
- [ ] Unit test feed reliability

## Phase 3: Strategy Engine

- [ ] Add RSI indicator (via `ta`)
- [ ] Add Bollinger Bands
- [ ] Combine into buy/sell signal logic
- [ ] Simulate signal triggers with historical data

## Phase 4: Risk and Execution

- [ ] Create risk manager for position sizing, stop-loss, cooldowns
- [ ] Build order executor via `ccxt`
- [ ] Handle failed trades, retries, and logging

## Phase 5: Logging & Monitoring

- [ ] Implement structured log files
- [ ] Add optional Discord/Telegram alerts
- [ ] Monitor for stale data or feed failures

## Phase 6: Testing & Deployment

- [ ] Simulate strategy on historical data
- [ ] Enable paper trading mode
- [ ] Conduct live dry run with small capital
- [ ] Final test and go live

## Milestones

| Date | Milestone |
|------|-----------|
| Week 1 | Environment setup + data feed complete |
| Week 2 | Strategy and signal processing functional |
| Week 3 | Risk and execution modules in place |
| Week 4 | Testing, monitoring, and live trial |
