"""
Kalshi Live API Client
Handles RSA-signed authentication and all endpoints needed for live BTC trading.
"""

import os
import time
import base64
import requests
from typing import Dict, List, Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from dotenv import load_dotenv

load_dotenv()

KALSHI_BASE_URL  = os.getenv("KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2")
KALSHI_API_KEY   = os.getenv("KALSHI_API_KEY", "")
KALSHI_PEM       = os.getenv("KALSHI_PRIVATE_KEY", "")        # raw PEM content
KALSHI_PEM_PATH  = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")   # OR path to .pem file


class KalshiClient:
    """
    Authenticated Kalshi API client using RSA-PSS key signing.
    Kalshi auth flow:
      1. Build message = f"{timestamp}{method}{path}"
      2. Sign with RSA-PSS SHA256 private key
      3. Send headers: KALSHI-ACCESS-KEY, KALSHI-ACCESS-SIGNATURE, KALSHI-ACCESS-TIMESTAMP
    """

    def __init__(self):
        self.base_url = KALSHI_BASE_URL
        self.api_key  = KALSHI_API_KEY
        self._private_key = self._load_private_key()
        self.session  = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _load_private_key(self):
        # Try raw PEM content first, then fall back to file path
        pem_bytes = None

        if KALSHI_PEM:
            pem_bytes = KALSHI_PEM.encode() if isinstance(KALSHI_PEM, str) else KALSHI_PEM
        elif KALSHI_PEM_PATH:
            try:
                with open(KALSHI_PEM_PATH.strip(), "rb") as f:
                    pem_bytes = f.read()
            except Exception as e:
                print(f"[KalshiClient] Failed to read key file {KALSHI_PEM_PATH}: {e}")
                return None

        if not pem_bytes:
            print("[KalshiClient] No private key configured (set KALSHI_PRIVATE_KEY or KALSHI_PRIVATE_KEY_PATH)")
            return None

        try:
            return serialization.load_pem_private_key(pem_bytes, password=None, backend=default_backend())
        except Exception as e:
            print(f"[KalshiClient] Failed to load private key: {e}")
            return None

    def _sign(self, timestamp_ms: str, method: str, path: str) -> str:
        """Sign with RSA-PSS SHA256 — Kalshi's required algorithm."""
        message = f"{timestamp_ms}{method}{path}".encode()
        signature = self._private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode()

    def _headers(self, method: str, path: str) -> Dict:
        ts = str(int(time.time() * 1000))
        headers = {
            "KALSHI-ACCESS-KEY":       self.api_key,
            "KALSHI-ACCESS-TIMESTAMP": ts,
        }
        if self._private_key:
            headers["KALSHI-ACCESS-SIGNATURE"] = self._sign(ts, method.upper(), path)
        return headers

    def _get(self, path: str, params: Dict = None) -> Dict:
        full_path = f"/trade-api/v2{path}"
        headers = self._headers("GET", full_path)
        r = self.session.get(f"{self.base_url}{path}", headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: Dict = None) -> Dict:
        full_path = f"/trade-api/v2{path}"
        headers = self._headers("POST", full_path)
        r = self.session.post(f"{self.base_url}{path}", headers=headers, json=body or {}, timeout=10)
        r.raise_for_status()
        return r.json()

    # ── Account ──────────────────────────────────────────────────────────────

    def get_balance(self) -> Dict:
        """Get account balance in cents."""
        return self._get("/portfolio/balance")

    def get_positions(self) -> List[Dict]:
        """Get all open positions."""
        return self._get("/portfolio/positions").get("positions", [])

    def get_fills(self, limit: int = 20) -> List[Dict]:
        """Get recent trade fills."""
        return self._get("/portfolio/fills", {"limit": limit}).get("fills", [])

    # ── Markets ───────────────────────────────────────────────────────────────

    def get_weather_markets(self, status: str = "open") -> List[Dict]:
        """
        Get all open Kalshi weather markets.
        Kalshi weather series tickers: HIGH* (temp high), LOW* (temp low), RAIN* (precipitation)
        Covers all US cities available on Kalshi.
        """
        weather_series = [
            "HIGHNY", "LOWNY",   # New York
            "HIGHCHI","LOWCHI",  # Chicago
            "HIGHMIA","LOWMIA",  # Miami
            "HIGHLA", "LOWLA",   # Los Angeles
            "HIGHHOU","LOWHOU",  # Houston
            "HIGHPHX","LOWPHX",  # Phoenix
            "HIGHSEA","LOWSEA",  # Seattle
            "HIGHDEN","LOWDEN",  # Denver
            "HIGHATL","LOWATL",  # Atlanta
            "HIGHDAL","LOWDAL",  # Dallas
            "HIGHAUS","LOWAUS",  # Austin
            "HIGHBOS","LOWBOS",  # Boston
        ]
        all_markets = []
        for series in weather_series:
            try:
                data = self._get("/markets", {"status": status, "series_ticker": series, "limit": 20})
                all_markets.extend(data.get("markets", []))
            except Exception:
                pass
        return all_markets

    def search_weather_markets(self, status: str = "open") -> List[Dict]:
        """
        Broader weather market search — discovers any weather market format.
        Falls back to keyword search if series tickers don't match.
        """
        try:
            data = self._get("/markets", {
                "status":  status,
                "limit":   100,
                "category": "weather",
            })
            markets = data.get("markets", [])
            if markets:
                return markets
        except Exception:
            pass
        # Fallback: get all open markets and filter by title keywords
        try:
            data = self._get("/markets", {"status": status, "limit": 200})
            all_m = data.get("markets", [])
            weather_kw = ["temperature", "high", "low", "rain", "snow", "wind", "°f", "degrees"]
            return [m for m in all_m if any(kw in m.get("title", "").lower() for kw in weather_kw)]
        except Exception:
            return []

    def get_btc_markets(self, status: str = "open") -> List[Dict]:
        """Get active BTC 15-min markets."""
        data = self._get("/markets", {
            "status":        status,
            "series_ticker": "KXBTC",
            "limit":         50,
        })
        return data.get("markets", [])

    def get_market(self, ticker: str) -> Dict:
        """Get a specific market by ticker."""
        return self._get(f"/markets/{ticker}").get("market", {})

    def get_orderbook(self, ticker: str) -> Dict:
        """Get order book for a market (bid/ask depth)."""
        return self._get(f"/markets/{ticker}/orderbook")

    def get_market_history(self, ticker: str, limit: int = 100) -> List[Dict]:
        """Get price history for a market."""
        data = self._get(f"/markets/{ticker}/history", {"limit": limit})
        return data.get("history", [])

    # ── Trading ───────────────────────────────────────────────────────────────

    def place_order(self, ticker: str, side: str, count: int, price_cents: int,
                    order_type: str = "limit") -> Dict:
        """
        Place a trade on Kalshi.

        ticker:       Market ticker e.g. "KXBTC-25MAY10-T94498"
        side:         "yes" or "no"
        count:        Number of contracts (each = $0.01 min)
        price_cents:  Price in cents (1-99)
        order_type:   "limit" or "market"
        """
        body = {
            "ticker":     ticker,
            "client_order_id": f"apex_{int(time.time()*1000)}",
            "type":       order_type,
            "action":     "buy",
            "side":       side.lower(),
            "count":      count,
            "yes_price":  price_cents if side.lower() == "yes" else (100 - price_cents),
            "no_price":   price_cents if side.lower() == "no"  else (100 - price_cents),
        }
        return self._post("/portfolio/orders", body)

    def cancel_order(self, order_id: str) -> Dict:
        return self._post(f"/portfolio/orders/{order_id}/cancel")

    def sell_position(self, ticker: str, side: str, count: int) -> Dict:
        """
        Close/sell an existing position at market price.
        side: the side you HOLD ("yes" or "no") — we sell that side back.
        """
        body = {
            "ticker":          ticker,
            "client_order_id": f"apex_sl_{int(time.time()*1000)}",
            "type":            "market",
            "action":          "sell",
            "side":            side.lower(),
            "count":           count,
        }
        return self._post("/portfolio/orders", body)

    def get_order(self, order_id: str) -> Dict:
        return self._get(f"/portfolio/orders/{order_id}").get("order", {})

    # ── Strategy helpers ──────────────────────────────────────────────────────

    def scan_btc_15min_signals(self) -> List[Dict]:
        """
        Scan all open BTC markets and return ones matching our TierB/C entry criteria:
        - 73%+ of market elapsed
        - YES price ≥ 0.74 or ≤ 0.26
        Returns ranked list of opportunities with signal tier and win probability.
        """
        markets = self.get_btc_markets()
        signals = []

        for m in markets:
            ticker      = m.get("ticker", "")
            yes_bid     = m.get("yes_bid", 0) / 100        # convert cents → decimal
            yes_ask     = m.get("yes_ask", 0) / 100
            yes_price   = (yes_bid + yes_ask) / 2          # midpoint
            no_price    = 1.0 - yes_price
            open_time   = m.get("open_time", "")
            close_time  = m.get("close_time", "")
            volume      = m.get("volume", 0)

            # Calculate market progress
            import datetime
            try:
                now        = datetime.datetime.utcnow().timestamp()
                open_ts    = datetime.datetime.fromisoformat(open_time.replace("Z", "+00:00")).timestamp()
                close_ts   = datetime.datetime.fromisoformat(close_time.replace("Z", "+00:00")).timestamp()
                duration   = close_ts - open_ts
                progress   = (now - open_ts) / duration if duration > 0 else 0
                mins_left  = (close_ts - now) / 60
            except Exception:
                continue

            if progress < 0.73 or mins_left < 0.5:
                continue

            # Tier classification
            tier = None
            side = None
            win_prob = 0.0

            if progress >= 0.85:
                if yes_price >= 0.70:
                    tier, side, win_prob = "TierC", "yes", 0.95
                elif yes_price <= 0.30:
                    tier, side, win_prob = "TierC", "no",  0.95
            elif progress >= 0.80:
                if yes_price >= 0.74:
                    tier, side, win_prob = "TierB", "yes", 0.92
                elif yes_price <= 0.26:
                    tier, side, win_prob = "TierB", "no",  0.92
            elif progress >= 0.73:
                if yes_price >= 0.76:
                    tier, side, win_prob = "TierA", "yes", 0.88
                elif yes_price <= 0.24:
                    tier, side, win_prob = "TierA", "no",  0.88

            if not tier:
                continue

            entry_price = yes_price if side == "yes" else no_price
            payout_ratio = round((1.0 - entry_price) / entry_price, 3)
            ev_per_100   = round(win_prob * (1.0 - entry_price) * 100 - (1 - win_prob) * 100, 2)

            signals.append({
                "ticker":      ticker,
                "tier":        tier,
                "side":        side.upper(),
                "yes_price":   round(yes_price, 3),
                "no_price":    round(no_price, 3),
                "entry_price": round(entry_price, 3),
                "payout_ratio": payout_ratio,
                "win_prob":    win_prob,
                "ev_per_100":  ev_per_100,
                "progress":    f"{progress:.0%}",
                "mins_left":   round(mins_left, 1),
                "volume":      volume,
            })

        # Sort by tier priority then EV
        tier_order = {"TierC": 0, "TierB": 1, "TierA": 2}
        signals.sort(key=lambda x: (tier_order.get(x["tier"], 9), -x["ev_per_100"]))
        return signals


# Singleton
kalshi = KalshiClient()
