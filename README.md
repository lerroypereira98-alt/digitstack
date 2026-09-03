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

## Research: 1-min / 5-min market scanner

`backend/research/` is a standalone, one-off research tool — it does **not** run as
part of the live trading engine and places no trades. It:

- Scans Kalshi and Polymarket's public REST APIs for markets whose resolution
  window is ~1 minute or ~5 minutes (`market_scanner.py`)
- Pulls related Reddit and YouTube discussion (`social_scanner.py`). Twitter/X and
  Instagram are intentionally skipped — both block unauthenticated scraping and
  require paid/authenticated API access.
- Writes a timestamped JSON + Markdown report

```bash
cd backend
python -m research.run_research                       # writes to ../reports
python -m research.run_research --minutes 1 5 15       # custom duration buckets
```

YouTube search is optional — set `YOUTUBE_API_KEY` (a free Google Cloud API key) to
enable it; it's skipped otherwise. Reddit search needs no key.
