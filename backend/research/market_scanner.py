"""
Market discovery scanner.

Finds currently-listed prediction markets whose resolution window is
~1 minute or ~5 minutes, across Kalshi and Polymarket, using each
platform's public REST API (no HTML scraping, no auth required for
public market listings).

Standalone research tool — not wired into the live trading engine in
main.py, and makes no trading calls.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
POLYMARKET_GAMMA_BASE = "https://gamma-api.polymarket.com"

REQUEST_TIMEOUT = 10
TOLERANCE_SEC = 20  # +/- slack when bucketing a market's lifetime into a duration

DURATION_TARGETS_SEC = {1: 60, 5: 300}


def _duration_bucket(duration_sec: float) -> Optional[int]:
    """Map a market's lifetime in seconds to a duration_min bucket (1 or 5), else None."""
    for minutes, target_sec in DURATION_TARGETS_SEC.items():
        if abs(duration_sec - target_sec) <= TOLERANCE_SEC:
            return minutes
    return None


def _parse_iso(ts: str) -> Optional[float]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


# ── Kalshi ────────────────────────────────────────────────────────────────

def _kalshi_row(m: Dict) -> Optional[Dict]:
    open_ts = _parse_iso(m.get("open_time", ""))
    close_ts = _parse_iso(m.get("close_time", ""))
    if open_ts is None or close_ts is None:
        return None

    duration_min = _duration_bucket(close_ts - open_ts)
    if duration_min is None:
        return None

    ticker = m.get("ticker", "")
    yes_bid, yes_ask = m.get("yes_bid"), m.get("yes_ask")
    yes_price = (yes_bid + yes_ask) / 200.0 if yes_bid is not None and yes_ask is not None else None
    series = ticker.split("-")[0].lower() if ticker else None

    return {
        "platform": "Kalshi",
        "id": ticker,
        "title": m.get("title") or m.get("subtitle") or ticker,
        "duration_min": duration_min,
        "close_time": m.get("close_time"),
        "yes_price": yes_price,
        "volume": m.get("volume"),
        "url": f"https://kalshi.com/markets/{series}" if series else None,
    }


def scan_kalshi(max_markets: int = 2000, page_size: int = 200) -> List[Dict]:
    """Page through Kalshi's public open-markets listing, no auth required."""
    results: List[Dict] = []
    cursor = None
    fetched = 0

    while fetched < max_markets:
        params = {"status": "open", "limit": page_size}
        if cursor:
            params["cursor"] = cursor
        try:
            resp = requests.get(f"{KALSHI_BASE}/markets", params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"[market_scanner] Kalshi request failed: {e}")
            break

        markets = data.get("markets", [])
        fetched += len(markets)
        for m in markets:
            row = _kalshi_row(m)
            if row:
                results.append(row)

        cursor = data.get("cursor")
        if not cursor or not markets:
            break

    return results


# ── Polymarket ────────────────────────────────────────────────────────────

def _polymarket_row(m: Dict) -> Optional[Dict]:
    start_ts = _parse_iso(m.get("startDate", ""))
    end_ts = _parse_iso(m.get("endDate", ""))

    duration_min = None
    if start_ts is not None and end_ts is not None:
        duration_min = _duration_bucket(end_ts - start_ts)

    # Fall back to keyword matching on the slug/question — Polymarket's
    # 1M/5M recurring markets don't always express duration cleanly via
    # startDate/endDate on the instance returned by /markets.
    if duration_min is None:
        text = f"{m.get('slug', '')} {m.get('question', '')}".lower()
        if any(k in text for k in ("-1m-", " 1 minute", "1-minute")):
            duration_min = 1
        elif any(k in text for k in ("-5m-", " 5 minute", "5-minute")):
            duration_min = 5

    if duration_min is None:
        return None

    yes_price = None
    outcome_prices = m.get("outcomePrices")
    if isinstance(outcome_prices, str):
        try:
            parsed = json.loads(outcome_prices)
            yes_price = float(parsed[0]) if parsed else None
        except (ValueError, IndexError):
            pass
    elif isinstance(outcome_prices, list) and outcome_prices:
        try:
            yes_price = float(outcome_prices[0])
        except (ValueError, TypeError):
            pass

    slug = m.get("slug", "")
    return {
        "platform": "Polymarket",
        "id": slug or str(m.get("id", "")),
        "title": m.get("question", slug),
        "duration_min": duration_min,
        "close_time": m.get("endDate"),
        "yes_price": yes_price,
        "volume": m.get("volume24hr") or m.get("volume"),
        "url": f"https://polymarket.com/event/{slug}" if slug else None,
    }


def scan_polymarket(max_markets: int = 1000, page_size: int = 100) -> List[Dict]:
    """Page through Polymarket's public Gamma API for active markets."""
    results: List[Dict] = []
    offset = 0

    while offset < max_markets:
        params = {
            "active": "true",
            "closed": "false",
            "limit": page_size,
            "offset": offset,
        }
        try:
            resp = requests.get(f"{POLYMARKET_GAMMA_BASE}/markets", params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            page = resp.json()
        except requests.RequestException as e:
            print(f"[market_scanner] Polymarket request failed: {e}")
            break

        if not page:
            break

        for m in page:
            row = _polymarket_row(m)
            if row:
                results.append(row)

        if len(page) < page_size:
            break
        offset += page_size

    return results


# ── Combined scan ────────────────────────────────────────────────────────

def scan_all(target_minutes: Tuple[int, ...] = (1, 5)) -> Dict[str, List[Dict]]:
    """Scan every supported platform and bucket results by platform name."""
    rows = scan_kalshi() + scan_polymarket()
    rows = [r for r in rows if r["duration_min"] in target_minutes]

    by_platform: Dict[str, List[Dict]] = {}
    for row in rows:
        by_platform.setdefault(row["platform"], []).append(row)
    return by_platform


if __name__ == "__main__":
    found = scan_all()
    for platform, markets in found.items():
        print(f"{platform}: {len(markets)} markets")
        for m in markets[:10]:
            print(f"  [{m['duration_min']}m] {m['title']} — {m['url']}")
