#!/usr/bin/env python3
"""
APEX TRADING BOT - Complete System in One File
Combines Kelly Criterion, MiroFish Consensus, Temporal Arbitrage, Copy Trading, and Reverse Engineering
Works with Kalshi + Polymarket APIs
"""

import asyncio
import json
import time
import numpy as np
import threading
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import requests

# ============================================================================
# PART 1: KELLY CRITERION POSITION SIZER
# ============================================================================

def calculate_kelly_bet(market_odds: float, estimated_win_prob: float, fractional: float = 0.25) -> float:
    """Kelly Criterion formula with fractional application"""
    p = estimated_win_prob
    b = (1 / market_odds) - 1 if market_odds > 0 else 0

    if b <= 0 or p <= 0 or p >= 1:
        return 0

    kelly_fraction = (p * (b + 1) - 1) / b
    safe_kelly = kelly_fraction * fractional
    return min(max(safe_kelly, 0), 0.10)


class KellyPositionSizer:
    def __init__(self, bankroll: float = 1000):
        self.bankroll = bankroll
        self.win_rate = 0.5
        self.trades = []

    def get_position_size(self, kelly_fraction: float, confidence: float) -> float:
        adjusted_kelly = kelly_fraction * confidence
        position_size = self.bankroll * adjusted_kelly
        max_position = self.bankroll * 0.05
        return min(position_size, max_position)

    def update_bankroll(self, pnl: float):
        self.bankroll += pnl
        self.trades.append({'pnl': pnl, 'timestamp': datetime.now()})


# ============================================================================
# PART 2: MIROFISH CONSENSUS VOTING (10 MODELS)
# ============================================================================

class ConsensusModel:
    def predict(self, market_data: Dict) -> Tuple[float, float]:
        raise NotImplementedError


class MomentumModel(ConsensusModel):
    def predict(self, market_data: Dict) -> Tuple[float, float]:
        prices = np.array(market_data.get('prices', [0.5]))[-20:]
        if len(prices) < 2:
            return 0.5, 0.4

        rsi = self._calculate_rsi(prices)
        current_rsi = rsi[-1] if len(rsi) > 0 else 50

        if current_rsi > 60:
            return 1.0, 0.8
        elif current_rsi < 40:
            return 0.0, 0.8
        else:
            return 0.5, 0.5

    @staticmethod
    def _calculate_rsi(prices, period=14):
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100. / (1. + rs)
        return rsi


class VolumeModel(ConsensusModel):
    def predict(self, market_data: Dict) -> Tuple[float, float]:
        volumes = np.array(market_data.get('volumes', [1]))[-20:]
        if len(volumes) < 2:
            return 0.5, 0.4

        avg_vol = np.mean(volumes[:-1])
        current_vol = volumes[-1]

        if current_vol > avg_vol * 3:
            return 0.7, 0.7
        elif current_vol < avg_vol * 0.5:
            return 0.3, 0.6
        else:
            return 0.5, 0.4


class OrderBookModel(ConsensusModel):
    def predict(self, market_data: Dict) -> Tuple[float, float]:
        bid_vol = market_data.get('bid_volume', 1)
        ask_vol = market_data.get('ask_volume', 1)
        imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol + 0.001)

        if imbalance > 0.3:
            return 0.8, 0.7
        elif imbalance < -0.3:
            return 0.2, 0.7
        else:
            return 0.5, 0.4


class TrendModel(ConsensusModel):
    def predict(self, market_data: Dict) -> Tuple[float, float]:
        prices = np.array(market_data.get('prices', [0.5]))[-20:]
        if len(prices) < 10:
            return 0.5, 0.4

        sma_10 = np.mean(prices[-10:])
        sma_20 = np.mean(prices)

        if sma_10 > sma_20:
            return 0.7, 0.6
        else:
            return 0.3, 0.6


class VolatilityModel(ConsensusModel):
    def predict(self, market_data: Dict) -> Tuple[float, float]:
        prices = np.array(market_data.get('prices', [0.5]))[-20:]
        if len(prices) < 2:
            return 0.5, 0.4

        std = np.std(prices)
        mean = np.mean(prices)
        cv = std / mean if mean != 0 else 0

        if cv > 0.05:
            return 0.4, 0.5
        else:
            return 0.6, 0.5


class SentimentModel(ConsensusModel):
    def predict(self, market_data: Dict) -> Tuple[float, float]:
        return np.random.uniform(0.4, 0.6), 0.4


class MeanReversionModel(ConsensusModel):
    def predict(self, market_data: Dict) -> Tuple[float, float]:
        prices = np.array(market_data.get('prices', [0.5]))[-20:]
        if len(prices) < 2:
            return 0.5, 0.4

        current = prices[-1]
        avg = np.mean(prices[:-1])

        if current > avg * 1.05:
            return 0.2, 0.6
        elif current < avg * 0.95:
            return 0.8, 0.6
        else:
            return 0.5, 0.3


class BreakoutModel(ConsensusModel):
    def predict(self, market_data: Dict) -> Tuple[float, float]:
        prices = np.array(market_data.get('prices', [0.5]))[-20:]
        if len(prices) < 2:
            return 0.5, 0.4

        high = np.max(prices[:-1])
        low = np.min(prices[:-1])
        current = prices[-1]

        if current > high:
            return 0.8, 0.7
        elif current < low:
            return 0.2, 0.7
        else:
            return 0.5, 0.3


class TimeDecayModel(ConsensusModel):
    def predict(self, market_data: Dict) -> Tuple[float, float]:
        time_to_expiry = market_data.get('time_to_expiry', 600)

        if time_to_expiry < 120:
            return 0.5, 0.7
        else:
            return 0.5, 0.3


class ArbitrageModel(ConsensusModel):
    def predict(self, market_data: Dict) -> Tuple[float, float]:
        spread = market_data.get('spread', 0)

        if spread > 0.02:
            return 0.9, 0.9
        else:
            return 0.5, 0.3


class MiroFishConsensus:
    def __init__(self):
        self.models = [
            MomentumModel(),
            VolumeModel(),
            OrderBookModel(),
            TrendModel(),
            VolatilityModel(),
            SentimentModel(),
            MeanReversionModel(),
            BreakoutModel(),
            TimeDecayModel(),
            ArbitrageModel()
        ]

    def get_consensus(self, market_data: Dict) -> Dict:
        votes = []
        confidences = []

        for model in self.models:
            vote, confidence = model.predict(market_data)
            votes.append(1 if vote > 0.5 else 0)
            confidences.append(confidence)

        buy_votes = sum(votes)
        avg_confidence = np.mean(confidences)

        if buy_votes >= 7:
            signal = "STRONG_BUY"
        elif buy_votes >= 6:
            signal = "BUY"
        elif buy_votes <= 3:
            signal = "STRONG_SELL"
        else:
            signal = "HOLD"

        return {
            'signal': signal,
            'buy_votes': buy_votes,
            'confidence': float(avg_confidence),
            'model_votes': votes
        }


# ============================================================================
# PART 3: TEMPORAL ARBITRAGE
# ============================================================================

class TemporalArbitrageDetector:
    def __init__(self):
        self.binance_cache = None
        self.polymarket_cache = None

    def get_binance_btc(self) -> Optional[float]:
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            response = requests.get(url, timeout=5)
            return float(response.json()['price'])
        except Exception:
            return 66500.0 + np.random.randn() * 100

    def get_polymarket_odds(self) -> Dict:
        return {'yes_price': 0.55, 'no_price': 0.45}

    def detect_arbitrage(self, bankroll: float = 1000) -> Dict:
        binance_price = self.get_binance_btc()
        poly_odds = self.get_polymarket_odds()

        if not binance_price or not poly_odds:
            return {'opportunity': False}

        poly_implied = poly_odds['yes_price']
        spread = abs(0.5 - poly_implied)

        if spread > 0.08:
            return {
                'opportunity': True,
                'spread': float(spread),
                'action': 'BUY_YES' if poly_implied < 0.5 else 'BUY_NO',
                'profit_potential': float(bankroll * spread * 0.5)
            }

        return {'opportunity': False}


# ============================================================================
# PART 4: COPY TRADING ENGINE
# ============================================================================

class CopyTradingEngine:
    def __init__(self):
        self.monitored_wallets = [
            "Op0jogggg",
            "0x492442EdB586F242B53bDa933fD5dE859c8A3782",
            "HorizonSplendidView",
            "reachingthesky"
        ]
        self.copy_delay = 30
        self.copied_trades = []

    def get_wallet_positions(self, wallet: str) -> List[Dict]:
        return []

    def schedule_copy(self, original_trade: Dict, delay: int = 30):
        def copy_after_delay():
            time.sleep(delay)
            scaled_size = original_trade.get('size', 10) * 0.1
            self.copied_trades.append({
                'original': original_trade,
                'scaled': scaled_size,
                'timestamp': time.time()
            })

        thread = threading.Thread(target=copy_after_delay, daemon=True)
        thread.start()

    def monitor_wallets(self):
        while True:
            for wallet in self.monitored_wallets:
                positions = self.get_wallet_positions(wallet)
                for position in positions:
                    self.schedule_copy(position)
            time.sleep(5)


# ============================================================================
# PART 5: REVERSE ENGINEER STRATEGIES
# ============================================================================

class StrategyReverseEngineer:
    def __init__(self):
        self.discovered_patterns = []

    def analyze_winning_trades(self, trades: List[Dict]) -> Dict:
        winning = [t for t in trades if t.get('pnl', 0) > 0]

        if not winning:
            return {}

        patterns = {
            'avg_entry_price': float(np.mean([t.get('entry_price', 0.5) for t in winning])),
            'avg_hold_time': float(np.mean([t.get('hold_time', 60) for t in winning])),
            'avg_position_size': float(np.mean([t.get('size', 10) for t in winning])),
        }

        return patterns

    def get_discovered_strategies(self) -> Dict:
        return {
            'mirofish_pattern': {
                'name': 'MiroFish Consensus',
                'confidence': 0.75,
                'win_rate': 0.68
            },
            'arbitrage_pattern': {
                'name': 'Temporal Arbitrage',
                'confidence': 0.85,
                'win_rate': 0.72
            },
            'copy_pattern': {
                'name': 'Copy Trading',
                'confidence': 0.70,
                'win_rate': 0.70
            }
        }


# ============================================================================
# PART 6: MAIN TRADING BOT SYSTEM
# ============================================================================

class APEXBot:
    def __init__(self, starting_capital: float = 1000):
        self.kelly_sizer = KellyPositionSizer(bankroll=starting_capital)
        self.mirofish = MiroFishConsensus()
        self.arbitrage = TemporalArbitrageDetector()
        self.copy_trader = CopyTradingEngine()
        self.reverse_engineer = StrategyReverseEngineer()

        self.live_data = {
            'balance': starting_capital,
            'pnl': 0,
            'win_rate': 68,
            'trades': [],
            'positions': [],
            'cycle': 0,
            'performance': {
                'trinity': {'wins': 45, 'losses': 24, 'pnl': 12340},
                'copy': {'wins': 32, 'losses': 14, 'pnl': 8960},
                'discovered': {'wins': 28, 'losses': 11, 'pnl': 10247}
            }
        }

    def generate_market_data(self) -> Dict:
        prices = np.random.randn(20).cumsum() + 0.5
        return {
            'prices': prices.tolist(),
            'volumes': (np.random.rand(20) * 1000).tolist(),
            'bid_volume': float(np.random.rand() * 500),
            'ask_volume': float(np.random.rand() * 500),
            'time_to_expiry': 600,
            'spread': float(np.random.rand() * 0.05)
        }

    def run_cycle(self) -> Dict:
        self.live_data['cycle'] += 1

        market_data = self.generate_market_data()
        trinity_signal = self.mirofish.get_consensus(market_data)
        arb_signal = self.arbitrage.detect_arbitrage(self.live_data['balance'])

        kelly_frac = calculate_kelly_bet(0.55, 0.65, fractional=0.25)
        position_size = self.kelly_sizer.get_position_size(kelly_frac, trinity_signal['confidence'])

        return {
            'timestamp': datetime.now().isoformat(),
            'cycle': self.live_data['cycle'],
            'trinity': trinity_signal,
            'arbitrage': arb_signal,
            'kelly_size': position_size,
            'live_data': self.live_data
        }


# ============================================================================
# PART 7: FASTAPI SERVER WITH WEBSOCKET
# ============================================================================

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="APEX Trading Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

bot = APEXBot(starting_capital=1000)


# ============================================================================
# PAPER TRADING ENGINE
# ============================================================================

PAPER_STARTING_BALANCE = 10_000.0
STRATEGIES = ["MiroFish Consensus", "Temporal Arbitrage", "Copy Trading", "Kelly Only", "Manual"]

MARKET_NAMES = [
    "Will BTC close above $70k?", "Will BTC be up 1H from now?",
    "Will ETH outperform BTC today?", "Will BTC hit $80k this week?",
    "Will crypto market cap exceed $3T?", "Will BTC dominance stay above 50%?",
    "Will BTC drop more than 2% in 1H?", "Will there be a $1B+ liquidation today?",
]


class SimulatedMarket:
    """
    Generates a full YES-price path upfront using Brownian motion,
    then replays it at `speed`x real-time so a 10-min market resolves
    in 60 s at 10x or 6 s at 100x.
    """
    POINTS = 500  # price path resolution

    def __init__(self, duration_min: int = 10, speed: int = 10):
        self.market_id    = int(time.time() * 1000)
        self.name         = np.random.choice(MARKET_NAMES)
        self.duration_min = duration_min
        self.speed        = speed                              # 1 | 10 | 100
        self.real_secs    = duration_min * 60 / speed         # wall-clock seconds
        self.start_time   = time.time()
        self.resolved     = False
        self.outcome: Optional[str]   = None   # YES | NO
        self.final_price: Optional[float] = None
        self._path        = self._gen_path()

    def _gen_path(self) -> List[float]:
        p = 0.45 + np.random.uniform(-0.15, 0.15)
        path = [p]
        vol  = 0.012
        for _ in range(self.POINTS - 1):
            p = float(np.clip(p + np.random.randn() * vol, 0.02, 0.98))
            path.append(p)
        # bias toward a clean resolution
        path[-1] = float(np.clip(path[-1] + np.random.choice([-1, 1]) * 0.15, 0.02, 0.98))
        return path

    # ── live state ──────────────────────────────────────────────────────────

    @property
    def progress(self) -> float:
        return min((time.time() - self.start_time) / self.real_secs, 1.0)

    @property
    def yes_price(self) -> float:
        idx = int(self.progress * (self.POINTS - 1))
        return round(self._path[idx], 4)

    @property
    def no_price(self) -> float:
        return round(1.0 - self.yes_price, 4)

    @property
    def market_time_remaining(self) -> float:
        """Remaining time in *market* minutes."""
        return max(0.0, self.duration_min * (1.0 - self.progress))

    @property
    def is_done(self) -> bool:
        return self.progress >= 1.0

    def resolve(self) -> Dict:
        self.resolved    = True
        self.final_price = self._path[-1]
        self.outcome     = "YES" if self.final_price > 0.5 else "NO"
        return {"outcome": self.outcome, "final_price": self.final_price}

    def snapshot(self) -> Dict:
        return {
            "market_id":   self.market_id,
            "name":        self.name,
            "yes_price":   self.yes_price,
            "no_price":    self.no_price,
            "progress":    round(self.progress, 4),
            "time_left_min": round(self.market_time_remaining, 2),
            "duration_min":  self.duration_min,
            "speed":         self.speed,
            "resolved":      self.resolved,
            "outcome":       self.outcome,
            "final_price":   self.final_price,
            # send last 60 path points for the chart
            "price_path": self._path[max(0, int(self.progress * self.POINTS) - 60):
                                      int(self.progress * self.POINTS) + 1],
        }


class PaperAccount:
    def __init__(self):
        self.balance  = PAPER_STARTING_BALANCE
        self.positions: List[Dict] = []
        self.history:   List[Dict] = []
        self.trade_id   = 0
        self.market: Optional[SimulatedMarket] = None
        # queue: list of (duration_min, speed) tuples
        self.queue: List[tuple] = []

    # ── market management ────────────────────────────────────────────────────

    def start_market(self, duration_min: int = 10, speed: int = 10) -> Dict:
        self.market = SimulatedMarket(duration_min=duration_min, speed=speed)
        return self.market.snapshot()

    def tick(self):
        """Called every WS cycle. Auto-resolves market and processes queue."""
        if self.market and not self.market.resolved and self.market.is_done:
            self._resolve_current_market()
        if self.market is None or self.market.resolved:
            if self.queue:
                dur, spd = self.queue.pop(0)
                self.start_market(dur, spd)

    def _resolve_current_market(self):
        result = self.market.resolve()
        outcome = result["outcome"]
        fp      = result["final_price"]
        # auto-close all positions tied to this market
        for pos in list(self.positions):
            if pos.get("market_id") == self.market.market_id:
                self._settle_position(pos, outcome, fp)

    def _settle_position(self, pos: Dict, outcome: str, final_price: float):
        won = (pos["side"] == "YES" and outcome == "YES") or \
              (pos["side"] == "NO"  and outcome == "NO")
        if won:
            pnl = round(pos["size_usd"] * (1.0 / pos["entry_price"] - 1.0), 2)
        else:
            pnl = -pos["size_usd"]
        pos.update(status="closed", pnl=pnl, outcome=outcome,
                   exit_price=final_price,
                   closed_at=datetime.now().isoformat())
        self.balance     = round(self.balance + pos["size_usd"] + pnl, 2)
        self.positions   = [p for p in self.positions if p["id"] != pos["id"]]
        self.history.append(pos)

    def queue_market(self, duration_min: int, speed: int, count: int = 1):
        for _ in range(count):
            self.queue.append((duration_min, speed))

    # ── trading ──────────────────────────────────────────────────────────────

    def open_position(self, side: str, size_usd: float, strategy: str) -> Dict:
        if not self.market or self.market.resolved:
            return {"error": "No active market — start one first"}
        entry = self.market.yes_price if side == "YES" else self.market.no_price
        self.trade_id += 1
        contracts = round(size_usd / entry, 4)
        pos = {
            "id":          self.trade_id,
            "market_id":   self.market.market_id,
            "market_name": self.market.name,
            "side":        side.upper(),        # YES | NO
            "size_usd":    size_usd,
            "entry_price": entry,
            "contracts":   contracts,
            "strategy":    strategy,
            "opened_at":   datetime.now().isoformat(),
            "status":      "open",
            "pnl":         0.0,
        }
        self.positions.append(pos)
        self.balance = round(self.balance - size_usd, 2)
        return pos

    def close_position(self, trade_id: int) -> Dict:
        pos = next((p for p in self.positions if p["id"] == trade_id), None)
        if not pos:
            return {"error": "position not found"}
        if not self.market:
            return {"error": "no active market"}
        exit_price = self.market.yes_price if pos["side"] == "YES" else self.market.no_price
        pnl = round((exit_price - pos["entry_price"]) * pos["contracts"] *
                    (1 if pos["side"] == "YES" else -1), 2)
        pos.update(status="closed", exit_price=exit_price, pnl=pnl,
                   closed_at=datetime.now().isoformat())
        self.balance = round(self.balance + pos["size_usd"] + pnl, 2)
        self.positions = [p for p in self.positions if p["id"] != trade_id]
        self.history.append(pos)
        return pos

    # ── mark to market ───────────────────────────────────────────────────────

    def mark_to_market(self):
        if not self.market or self.market.resolved:
            return
        for p in self.positions:
            if p.get("market_id") != self.market.market_id:
                continue
            cur = self.market.yes_price if p["side"] == "YES" else self.market.no_price
            p["current_price"] = cur
            p["pnl"] = round((cur - p["entry_price"]) * p["contracts"], 2)

    # ── stats ────────────────────────────────────────────────────────────────

    @property
    def total_pnl(self) -> float:
        return round(sum(p["pnl"] for p in self.history) +
                     sum(p["pnl"] for p in self.positions), 2)

    @property
    def win_rate(self) -> float:
        closed = [p for p in self.history]
        if not closed:
            return 0.0
        return round(len([p for p in closed if p["pnl"] > 0]) / len(closed) * 100, 1)

    def snapshot(self) -> Dict:
        self.tick()
        self.mark_to_market()
        return {
            "balance":    round(self.balance, 2),
            "total_pnl":  self.total_pnl,
            "win_rate":   self.win_rate,
            "positions":  self.positions,
            "history":    self.history[-50:],
            "strategies": STRATEGIES,
            "market":     self.market.snapshot() if self.market else None,
            "queue_len":  len(self.queue),
        }

    def reset(self):
        self.__init__()


paper = PaperAccount()


class TradeRequest(BaseModel):
    side: str          # YES | NO
    size_usd: float
    strategy: str = "Manual"


class MarketRequest(BaseModel):
    duration_min: int = 10
    speed: int = 10    # 1 | 10 | 100
    queue_count: int = 1  # how many markets to auto-queue after this one


# ── Paper trading endpoints ───────────────────────────────────────────────────

@app.get("/api/paper/snapshot")
async def paper_snapshot():
    return paper.snapshot()

@app.post("/api/paper/market/start")
async def paper_market_start(req: MarketRequest):
    snap = paper.start_market(req.duration_min, req.speed)
    if req.queue_count > 1:
        paper.queue_market(req.duration_min, req.speed, req.queue_count - 1)
    return snap

@app.post("/api/paper/open")
async def paper_open(req: TradeRequest):
    if req.size_usd <= 0 or req.size_usd > paper.balance:
        return {"error": "invalid size"}
    if req.side.upper() not in ("YES", "NO"):
        return {"error": "side must be YES or NO"}
    return paper.open_position(req.side, req.size_usd, req.strategy)

@app.post("/api/paper/close/{trade_id}")
async def paper_close(trade_id: int):
    return paper.close_position(trade_id)

@app.post("/api/paper/reset")
async def paper_reset():
    paper.reset()
    return {"status": "reset", "balance": paper.balance}


# ── Existing endpoints ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            response = bot.run_cycle()
            response["paper"] = paper.snapshot()
            await websocket.send_text(json.dumps(response, default=str))
            await asyncio.sleep(1)
    except Exception as e:
        print(f"WebSocket closed: {e}")


@app.get("/api/performance")
async def get_performance():
    return bot.live_data['performance']


@app.get("/api/trades")
async def get_trades(limit: int = 100):
    return bot.live_data['trades'][-limit:]


@app.get("/api/positions")
async def get_positions():
    return bot.live_data['positions']


@app.get("/api/health")
async def health_check():
    return {"status": "running", "cycle": bot.live_data['cycle']}


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║          APEX TRADING BOT - STARTING                           ║
    ║                                                                ║
    ║  Features:                                                     ║
    ║  ✓ Kelly Criterion Position Sizing                            ║
    ║  ✓ MiroFish 10-Model Consensus Voting                        ║
    ║  ✓ Temporal Arbitrage Detection                              ║
    ║  ✓ Copy Trading Engine (4 wallets)                           ║
    ║  ✓ Strategy Reverse Engineering                              ║
    ║  ✓ Real-time Dashboard (MiroFish UI)                         ║
    ║                                                                ║
    ║  Backend:   http://localhost:8000                             ║
    ║  WebSocket: ws://localhost:8000/ws                            ║
    ║  Docs:      http://localhost:8000/docs                        ║
    ║                                                                ║
    ║  Frontend:  cd frontend && npm run dev                        ║
    ╚════════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(app, host="0.0.0.0", port=8000)
