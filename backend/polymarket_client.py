"""
Binance-to-Kalshi 15-min Strategy
Watch Binance BTC momentum at candle start, enter Kalshi when direction confirmed.
Removes Polymarket dependency — uses Kalshi 15-min markets instead.

Edge: Early entry (first 60s) with high momentum confirmation vs waiting 73%+ of candle.
"""

import os
import time
import json
import threading
import websocket
from typing import Dict, Optional
from collections import deque
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Momentum thresholds for Kalshi 15-min entry
MOMENTUM_THRESHOLDS = {
    "extreme":   {"min_move_pct": 0.25, "min_seconds": 40, "win_prob": 0.88},
    "very_high": {"min_move_pct": 0.15, "min_seconds": 60, "win_prob": 0.82},
    "high":      {"min_move_pct": 0.08, "min_seconds": 75, "win_prob": 0.75},
    "standard":  {"min_move_pct": 0.04, "min_seconds": 90, "win_prob": 0.70},
}

# Active hours (ET): 7am-4pm (NYSE hours, when BTC is most volatile)
ACTIVE_HOURS_ET = [(7, 16)]


class BinancePriceFeed:
    """
    WebSocket connection to Binance BTC/USDT for millisecond price updates.
    Tracks 15-min candles and momentum.
    """

    def __init__(self, symbol: str = "btcusdt"):
        self.symbol      = symbol
        self.price       = None
        self.price_history: deque = deque(maxlen=300)
        self.connected   = False
        self._ws         = None
        self._thread     = None
        self._candle_open_price: Dict[int, float] = {}

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
        print("[BinanceFeed] Connected to BTC/USDT")

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            price = float(data["p"])
            ts    = int(data["T"]) / 1000
            self.price = price
            self.price_history.append({"price": price, "ts": ts})

            candle_start = int(ts // 900) * 900  # 15-min = 900s
            if candle_start not in self._candle_open_price:
                self._candle_open_price[candle_start] = price
                # Cleanup old
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
        print("[BinanceFeed] Disconnected — reconnecting...")
        time.sleep(5)
        self._run()

    def get_15min_momentum(self) -> Optional[Dict]:
        """
        Calculate momentum for the current 15-min candle.
        Only returns signal if confidence threshold met.
        """
        if not self.price or len(self.price_history) < 3:
            return None

        now = time.time()
        candle_start = int(now // 900) * 900
        seconds_elapsed = now - candle_start

        open_price = self._candle_open_price.get(candle_start)
        if not open_price:
            candle_ticks = [t for t in self.price_history if t["ts"] >= candle_start]
            if not candle_ticks:
                return None
            open_price = candle_ticks[0]["price"]

        current_price = self.price
        move_pct = abs(current_price - open_price) / open_price * 100
        direction = "UP" if current_price > open_price else "DOWN"

        # Find confidence level
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
            "seconds_remaining": round(900 - seconds_elapsed, 1),
            "active_window":    _is_active_hours(),
        }

    def get_price(self) -> Optional[float]:
        return self.price


def _is_active_hours() -> bool:
    """Check if current time is in trading hours (ET)."""
    now_et = datetime.now(timezone.utc)
    hour_utc = now_et.hour
    hour_et = (hour_utc - 4) % 24  # UTC-4 approximation
    for start, end in ACTIVE_HOURS_ET:
        if start <= hour_et < end:
            return True
    return False


def build_signal(momentum: Dict) -> Optional[Dict]:
    """Build a Kalshi 15-min trade signal from momentum."""
    if not momentum or not momentum.get("confidence_level"):
        return None
    if not momentum.get("active_window"):
        return None

    level = momentum["confidence_level"]
    params = MOMENTUM_THRESHOLDS[level]

    direction = momentum["direction"]
    side = "YES" if direction == "UP" else "NO"

    return {
        "market_type":      "BTC_15MIN",
        "direction":        direction,
        "side":             side,
        "confidence_level": level,
        "win_prob":         params["win_prob"],
        "move_pct":         momentum["move_pct"],
        "seconds_elapsed":  momentum["seconds_elapsed"],
        "open_price":       momentum["open_price"],
        "current_price":    momentum["current_price"],
        "entry_guidance":   f"Enter YES at ask if momentum continues UP, NO if continues DOWN",
        "ready_to_trade":   True,
    }


# Singleton
btc_feed = BinancePriceFeed()
