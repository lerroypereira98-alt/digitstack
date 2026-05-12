"""
Polymarket BTC 5-min Up/Down Strategy
Reverse-engineered from top trader: 0xf5c1325da8d819e0ce1ec0fde7cde72bcdb96683
100% WR, $15k single wins, trades first second of each 5-min window

Core edge: Binance live price momentum in first 60s confirms direction
before Polymarket market price updates. Enter AFTER direction locked in.
"""

import os
import time
import json
import threading
import requests
import websocket
from typing import Dict, List, Optional
from collections import deque
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

POLYMARKET_API   = os.getenv("POLYMARKET_API_URL", "https://clob.polymarket.com")
POLY_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
POLY_API_KEY     = os.getenv("POLYMARKET_API_KEY", "")

# Momentum thresholds (reverse-engineered from trader profile)
MOMENTUM_THRESHOLDS = {
    "extreme":   {"min_move_pct": 0.30, "min_seconds": 45, "confidence": 0.97, "odds_target": 0.08},
    "very_high": {"min_move_pct": 0.20, "min_seconds": 60, "confidence": 0.90, "odds_target": 0.30},
    "high":      {"min_move_pct": 0.12, "min_seconds": 75, "confidence": 0.82, "odds_target": 0.50},
    "standard":  {"min_move_pct": 0.07, "min_seconds": 90, "confidence": 0.72, "odds_target": 0.60},
}

# Position sizing from trader profile (inverse confidence = higher payout)
POSITION_SIZING = {
    "extreme":   {"min": 4,    "max": 50},
    "very_high": {"min": 2500, "max": 25000},
    "high":      {"min": 500,  "max": 10000},
    "standard":  {"min": 5,    "max": 300},
}

# Active trading hours (ET): 7-10am and 2-6pm
ACTIVE_HOURS_ET = [(7, 10), (14, 18)]


class BinancePriceFeed:
    """
    WebSocket connection to Binance BTC/USDT for millisecond price updates.
    Tracks price history for momentum calculations.
    """

    def __init__(self, symbol: str = "btcusdt"):
        self.symbol      = symbol
        self.price       = None
        self.price_history: deque = deque(maxlen=300)  # last 300 ticks
        self.connected   = False
        self._ws         = None
        self._thread     = None
        self._candle_open_price: Dict[int, float] = {}  # candle_start_ts → open price

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        url = f"wss://stream.binance.com:9443/ws/{self.symbol}@trade"
        self._ws = websocket.WebSocketApp(
            url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open,
        )
        self._ws.run_forever(ping_interval=30, ping_timeout=10)

    def _on_open(self, ws):
        self.connected = True
        print("[BinanceFeed] Connected to BTC/USDT stream")

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            price = float(data["p"])
            ts    = int(data["T"]) / 1000  # ms → seconds
            self.price = price
            self.price_history.append({"price": price, "ts": ts})

            # Track 5-min candle open prices
            candle_start = int(ts // 300) * 300
            if candle_start not in self._candle_open_price:
                self._candle_open_price[candle_start] = price
                # Cleanup old candles
                cutoff = candle_start - 3600
                self._candle_open_price = {
                    k: v for k, v in self._candle_open_price.items() if k >= cutoff
                }
        except Exception:
            pass

    def _on_error(self, ws, error):
        print(f"[BinanceFeed] Error: {error}")
        self.connected = False

    def _on_close(self, ws, *args):
        self.connected = False
        print("[BinanceFeed] Disconnected — reconnecting in 5s")
        time.sleep(5)
        self._run()

    def get_candle_momentum(self) -> Optional[Dict]:
        """
        Calculate momentum for the current 5-min candle.
        Returns direction, move_pct, seconds_elapsed, confidence_level.
        """
        if not self.price or len(self.price_history) < 5:
            return None

        now          = time.time()
        candle_start = int(now // 300) * 300
        seconds_elapsed = now - candle_start

        open_price = self._candle_open_price.get(candle_start)
        if not open_price:
            # Fallback: use earliest price in this candle
            candle_ticks = [t for t in self.price_history if t["ts"] >= candle_start]
            if not candle_ticks:
                return None
            open_price = candle_ticks[0]["price"]

        current_price = self.price
        move_pct      = abs(current_price - open_price) / open_price * 100
        direction     = "UP" if current_price > open_price else "DOWN"

        # Classify confidence level
        confidence_level = None
        for level, params in MOMENTUM_THRESHOLDS.items():
            if move_pct >= params["min_move_pct"] and seconds_elapsed >= params["min_seconds"]:
                confidence_level = level
                break

        return {
            "candle_start":     candle_start,
            "seconds_elapsed":  round(seconds_elapsed, 1),
            "open_price":       round(open_price, 2),
            "current_price":    round(current_price, 2),
            "move_pct":         round(move_pct, 4),
            "direction":        direction,
            "confidence_level": confidence_level,
            "seconds_remaining": round(300 - seconds_elapsed, 1),
            "active_window":    _is_active_hours(),
        }

    def get_price(self) -> Optional[float]:
        return self.price

    def get_recent_volatility(self, seconds: int = 60) -> float:
        """Calculate price volatility over recent N seconds."""
        now = time.time()
        recent = [t["price"] for t in self.price_history if t["ts"] >= now - seconds]
        if len(recent) < 2:
            return 0.0
        prices = list(recent)
        return round((max(prices) - min(prices)) / prices[0] * 100, 4)


class PolymarketClient:
    """
    Polymarket CLOB API client for BTC 5-min Up/Down markets.
    Requires POLYMARKET_PRIVATE_KEY (Ethereum private key) and POLYMARKET_API_KEY.
    """

    def __init__(self):
        self.base_url   = POLYMARKET_API
        self.api_key    = POLY_API_KEY
        self.private_key = POLY_PRIVATE_KEY
        self.session    = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "POLY_ADDRESS": "",
            "POLY_SIGNATURE": "",
            "POLY_TIMESTAMP": "",
            "POLY_NONCE": "",
        })

    def get_btc_5min_markets(self) -> List[Dict]:
        """Get active BTC 5-minute Up/Down markets from Polymarket."""
        try:
            r = self.session.get(
                f"{self.base_url}/markets",
                params={"active": True, "closed": False, "tag_slug": "crypto"},
                timeout=10
            )
            r.raise_for_status()
            markets = r.json().get("data", [])
            # Filter for BTC 5-min markets
            btc_5min = [
                m for m in markets
                if "bitcoin" in m.get("question", "").lower()
                and ("5" in m.get("question", "") or "five" in m.get("question", "").lower())
                and any(kw in m.get("question", "").lower() for kw in ["up", "down", "higher", "lower"])
            ]
            return btc_5min
        except Exception as e:
            print(f"[Polymarket] Failed to fetch markets: {e}")
            return []

    def get_market_price(self, condition_id: str) -> Dict:
        """Get current bid/ask for a market."""
        try:
            r = self.session.get(
                f"{self.base_url}/book",
                params={"token_id": condition_id},
                timeout=5
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    def place_order(self, token_id: str, side: str, size_usd: float,
                    price: float) -> Dict:
        """
        Place a market order on Polymarket.
        Requires valid private key — returns mock if no key configured.
        """
        if not self.private_key:
            return {
                "status": "mock",
                "message": "No POLYMARKET_PRIVATE_KEY set — paper trade only",
                "token_id": token_id,
                "side": side,
                "size_usd": size_usd,
                "price": price,
            }

        # Real order placement requires py-clob-client
        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import OrderArgs, OrderType

            client = ClobClient(
                host=self.base_url,
                key=self.private_key,
                chain_id=137,  # Polygon
            )
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size_usd,
                side=side,
                order_type=OrderType.GTC,
            )
            return client.create_and_post_order(order_args)
        except ImportError:
            return {"status": "error", "message": "py-clob-client not installed. Run: pip install py-clob-client"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def _is_active_hours() -> bool:
    """Check if current time is in active trading window (ET)."""
    now_et = datetime.now(timezone.utc)
    hour_utc = now_et.hour
    # Convert UTC to ET (UTC-4 in summer, UTC-5 in winter — approximate)
    hour_et = (hour_utc - 4) % 24
    for start, end in ACTIVE_HOURS_ET:
        if start <= hour_et < end:
            return True
    return False


def build_signal(momentum: Dict, market: Dict = None) -> Optional[Dict]:
    """
    Build a trade signal from momentum data.
    Only fires when confidence_level is set (threshold met).
    """
    if not momentum or not momentum.get("confidence_level"):
        return None
    if not momentum.get("active_window"):
        return None  # Outside trading hours

    level  = momentum["confidence_level"]
    params = MOMENTUM_THRESHOLDS[level]
    sizing = POSITION_SIZING[level]

    direction = momentum["direction"]
    side      = "YES" if direction == "UP" else "NO"  # UP market = YES

    # Position size: use middle of range for now
    size_usd = (sizing["min"] + sizing["max"]) / 2

    return {
        "platform":          "polymarket",
        "market_type":       "BTC_5MIN",
        "direction":         direction,
        "side":              side,
        "confidence_level":  level,
        "confidence_pct":    round(params["confidence"] * 100, 1),
        "odds_target":       params["odds_target"],
        "move_pct":          momentum["move_pct"],
        "seconds_elapsed":   momentum["seconds_elapsed"],
        "seconds_remaining": momentum["seconds_remaining"],
        "open_price":        momentum["open_price"],
        "current_price":     momentum["current_price"],
        "size_usd":          size_usd,
        "expected_payout":   round(size_usd / params["odds_target"], 2),
        "expected_roi_pct":  round((1 / params["odds_target"] - 1) * 100, 1),
        "candle_start":      momentum["candle_start"],
    }


# Singletons
btc_feed      = BinancePriceFeed()
poly_client   = PolymarketClient()
