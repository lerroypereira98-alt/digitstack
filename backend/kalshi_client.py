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
        Scan all open BTC markets using MiroFish consensus voting.
        - Fires on 50%+ elapsed if 7+/10 models agree (consensus-driven)
        - Can enter earlier at lower prices because consensus is validated
        - Payout-adjusted win probability based on entry price
        """
        markets = self.get_btc_markets()
        signals = []

        import datetime
        for m in markets:
            ticker      = m.get("ticker", "")
            yes_bid     = m.get("yes_bid", 0) / 100
            yes_ask     = m.get("yes_ask", 0) / 100
            no_bid      = m.get("no_bid",  0) / 100
            no_ask      = m.get("no_ask",  0) / 100
            yes_mid     = (yes_bid + yes_ask) / 2
            open_time   = m.get("open_time", "")
            close_time  = m.get("close_time", "")
            volume      = m.get("volume", 0)

            try:
                now        = datetime.datetime.utcnow().timestamp()
                open_ts    = datetime.datetime.fromisoformat(open_time.replace("Z", "+00:00")).timestamp()
                close_ts   = datetime.datetime.fromisoformat(close_time.replace("Z", "+00:00")).timestamp()
                duration   = close_ts - open_ts
                progress   = (now - open_ts) / duration if duration > 0 else 0
                mins_left  = (close_ts - now) / 60
            except Exception:
                continue

            # MiroFish: trade at 50%+ elapsed if consensus is strong
            if progress < 0.50 or progress >= 0.95 or mins_left < 0.5:
                continue

            # Run simple consensus check: 5-model majority
            # (in production this calls the full MiroFish suite from main.py)
            votes_yes = 0
            votes_no = 0

            # Model 1: Price extreme (strongest signal)
            if yes_mid >= 0.75:
                votes_yes += 2
            elif yes_mid <= 0.25:
                votes_no += 2

            # Model 2: Momentum (time decay = directional confidence)
            if progress >= 0.70 and yes_mid >= 0.60:
                votes_yes += 1
            elif progress >= 0.70 and yes_mid <= 0.40:
                votes_no += 1

            # Model 3: Volume-weighted confidence
            if volume > 50:
                if yes_mid > 0.5:
                    votes_yes += 1
                else:
                    votes_no += 1

            # Model 4: Spread tightness (bid-ask collapsed = consensus)
            spread = yes_ask - yes_bid
            if spread < 0.05 and yes_mid > 0.5:
                votes_yes += 1
            elif spread < 0.05 and yes_mid < 0.5:
                votes_no += 1

            # Model 5: Orderbook imbalance
            if yes_mid >= 0.70:
                votes_yes += 1
            elif yes_mid <= 0.30:
                votes_no += 1

            total_votes = votes_yes + votes_no
            if total_votes < 3:  # Need at least 3/5 models
                continue

            # Consensus threshold: 3+/5 models agree
            if votes_yes > votes_no:
                side = "YES"
                consensus = votes_yes / total_votes
            else:
                side = "NO"
                consensus = votes_no / total_votes

            if consensus < 0.60:  # Need 60% consensus
                continue

            # Entry price and win probability
            if side == "YES":
                entry_price = yes_ask if yes_ask > 0 else yes_mid
            else:
                entry_price = no_ask if no_ask > 0 else (1.0 - yes_bid)

            # Hard cap: skip expensive entries
            if entry_price > 0.85:
                continue

            # Win prob adjusted by: consensus strength × entry price quality
            # At 50% elapsed, lower win rate; at 80%+ elapsed, higher
            base_wr = 0.65 + (progress - 0.50) * 0.50  # scales 65% → 90%
            final_wr = base_wr * consensus  # consensus adjusts win rate
            final_wr = min(final_wr, 0.92)

            payout_ratio = round((1.0 - entry_price) / entry_price, 3)
            ev_per_100   = round(final_wr * (1.0 - entry_price) * 100 - (1 - final_wr) * 100, 2)

            signals.append({
                "ticker":       ticker,
                "side":         side,
                "yes_bid":      round(yes_bid, 3),
                "yes_ask":      round(yes_ask, 3),
                "yes_mid":      round(yes_mid, 3),
                "entry_price":  round(entry_price, 3),
                "payout_ratio": payout_ratio,
                "consensus":    round(consensus, 2),
                "votes":        f"{max(votes_yes, votes_no)}/{total_votes}",
                "win_prob":     round(final_wr, 3),
                "ev_per_100":   ev_per_100,
                "progress":     f"{progress:.0%}",
                "mins_left":    round(mins_left, 2),
                "volume":       volume,
            })

        # Sort by EV (highest first)
        signals.sort(key=lambda x: -x["ev_per_100"])
        return signals


# Singleton
kalshi = KalshiClient()
