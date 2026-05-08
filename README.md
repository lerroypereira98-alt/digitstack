# APEX Trading Bot

Multi-strategy prediction market trading bot with a real-time React dashboard.

## Strategies
- **Kelly Criterion** — fractional position sizing
- **MiroFish Consensus** — 10-model voting system
- **Temporal Arbitrage** — cross-platform spread detection
- **Copy Trading** — wallet monitoring with delayed mirroring
- **Reverse Engineering** — winning pattern analysis

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# Dashboard: http://localhost:3000
```

## API Endpoints
| Endpoint | Description |
|---|---|
| `WS /ws` | Live cycle data stream |
| `GET /api/performance` | Strategy performance breakdown |
| `GET /api/trades` | Trade history |
| `GET /api/positions` | Open positions |
| `GET /api/health` | Health check |
