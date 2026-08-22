#!/usr/bin/env python3
"""
Cross-Exchange Crypto Arbitrage — Paper Trading Simulator

Tests the "buy low on exchange A, sell high on exchange B" idea (the same
mechanic as latency-arbitrage HFT, just without needing colocation to try
it out) using SYNTHETIC order-book data for three exchanges: Binance,
Coinbase, Kraken.

Why synthetic instead of live: this session's network policy blocks
outbound calls to exchange APIs. The simulation is calibrated to realistic
BTC/USD parameters (volatility, per-venue spreads, taker fees) so the
conclusions about how often a real edge shows up, and how much of it
survives execution latency, are representative — but the actual prices
are not real market data. Swap `ExchangeSim.tick()` for real REST/WS
calls to run this against live venues once network access allows it.
"""

import json
import random
import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

# ============================================================================
# CONFIG
# ============================================================================

STARTING_USD = 5_000.0
STARTING_BTC = 0.10
TRADE_NOTIONAL_USD = 500.0          # size per arb attempt
MIN_NET_EDGE_BPS = 2.0              # require this much edge left after fees+slippage
RETAIL_LATENCY_MS = 180             # our round-trip: detect -> send -> fill (no colocation)
OPPORTUNITY_HALF_LIFE_MS = 220      # how fast a real dislocation typically closes
N_TICKS = 50_000                    # simulated ticks
TICK_MS = 200                       # each tick represents ~200ms of market time
RANDOM_SEED = 42

FEE_SCENARIOS = {
    "retail (default taker tier)": {
        "binance": 10.0,    # 0.10%
        "coinbase": 60.0,   # 0.60% (Advanced Trade base tier)
        "kraken": 26.0,     # 0.26%
    },
    "high-volume / pro taker tier": {
        "binance": 4.0,     # ~$1M+/mo tier
        "coinbase": 14.0,   # ~$50M+/mo Advanced Trade tier
        "kraken": 10.0,     # ~$1M+/mo tier
    },
}

VENUES = list(FEE_SCENARIOS["retail (default taker tier)"].keys())


def bps(x: float) -> float:
    return x * 10_000


# ============================================================================
# SYNTHETIC MARKET
# ============================================================================

@dataclass
class ExchangeSim:
    name: str
    mid: float
    offset: float = 0.0            # temporary dislocation vs shared mid
    spread_bps: float = 3.0        # typical top-of-book half-spread

    def tick(self, shared_mid: float, rng: random.Random):
        # offset mean-reverts toward 0, with occasional latency-style jumps
        self.offset += (0 - self.offset) * 0.35
        if rng.random() < 0.04:                      # ~4% of ticks: a dislocation event
            self.offset += rng.uniform(-1, 1) * shared_mid * rng.uniform(0.0003, 0.0012)
        self.mid = shared_mid + self.offset
        self.spread_bps = max(1.5, rng.gauss(3.0, 1.0))

    @property
    def bid(self) -> float:
        return self.mid * (1 - self.spread_bps / 2 / 10_000)

    @property
    def ask(self) -> float:
        return self.mid * (1 + self.spread_bps / 2 / 10_000)


@dataclass
class Book:
    usd: float
    btc: float


@dataclass
class Trade:
    tick: int
    ts_ms: int
    buy_ex: str
    sell_ex: str
    qty_btc: float
    buy_price: float
    sell_price: float
    gross_edge_bps: float
    net_edge_bps: float
    filled: bool
    pnl_usd: float


def run_simulation(taker_fee_bps: Dict[str, float]) -> Dict:
    rng = random.Random(RANDOM_SEED)
    shared_mid = 65_000.0
    annual_vol = 0.65
    dt_years = (TICK_MS / 1000) / (365 * 24 * 3600)
    vol_per_tick = annual_vol * dt_years ** 0.5

    exchanges = {name: ExchangeSim(name=name, mid=shared_mid) for name in VENUES}
    books = {name: Book(usd=STARTING_USD, btc=STARTING_BTC) for name in VENUES}

    trades: List[Trade] = []
    opportunities_detected = 0
    opportunities_missed_latency = 0
    opportunities_blocked_inventory = 0

    for t in range(N_TICKS):
        shared_mid *= (1 + rng.gauss(0, vol_per_tick))
        for ex in exchanges.values():
            ex.tick(shared_mid, rng)

        best_net = None
        for buy_name in VENUES:
            for sell_name in VENUES:
                if buy_name == sell_name:
                    continue
                buy_ex, sell_ex = exchanges[buy_name], exchanges[sell_name]
                buy_price, sell_price = buy_ex.ask, sell_ex.bid
                gross_edge_bps = bps((sell_price - buy_price) / buy_price)
                fee_cost_bps = taker_fee_bps[buy_name] + taker_fee_bps[sell_name]
                net_edge_bps = gross_edge_bps - fee_cost_bps
                if net_edge_bps > MIN_NET_EDGE_BPS:
                    if best_net is None or net_edge_bps > best_net[0]:
                        best_net = (net_edge_bps, gross_edge_bps, buy_name, sell_name, buy_price, sell_price)

        if best_net is None:
            continue

        opportunities_detected += 1
        net_edge_bps, gross_edge_bps, buy_name, sell_name, buy_price, sell_price = best_net
        qty_btc = TRADE_NOTIONAL_USD / buy_price

        # Execution-latency reality: by the time our order lands, has the
        # dislocation already closed? Model opportunity survival as
        # exponential decay against our retail round-trip latency.
        survival_prob = 0.5 ** (RETAIL_LATENCY_MS / OPPORTUNITY_HALF_LIFE_MS)
        survives = rng.random() < survival_prob

        # Inventory constraint: need USD on the buy side, BTC on the sell side.
        buy_book, sell_book = books[buy_name], books[sell_name]
        has_inventory = buy_book.usd >= TRADE_NOTIONAL_USD and sell_book.btc >= qty_btc

        if not has_inventory:
            opportunities_blocked_inventory += 1
            continue

        if not survives:
            opportunities_missed_latency += 1
            trades.append(Trade(t, t * TICK_MS, buy_name, sell_name, qty_btc,
                                 buy_price, sell_price, gross_edge_bps, net_edge_bps,
                                 filled=False, pnl_usd=0.0))
            continue

        # Fill: buy BTC on buy_ex, sell same BTC on sell_ex, pay both taker fees.
        buy_cost = qty_btc * buy_price * (1 + taker_fee_bps[buy_name] / 10_000)
        sell_proceeds = qty_btc * sell_price * (1 - taker_fee_bps[sell_name] / 10_000)
        pnl = sell_proceeds - buy_cost

        buy_book.usd -= buy_cost
        buy_book.btc += qty_btc
        sell_book.btc -= qty_btc
        sell_book.usd += sell_proceeds

        trades.append(Trade(t, t * TICK_MS, buy_name, sell_name, qty_btc,
                             buy_price, sell_price, gross_edge_bps, net_edge_bps,
                             filled=True, pnl_usd=pnl))

    filled = [tr for tr in trades if tr.filled]
    missed = [tr for tr in trades if not tr.filled]
    total_pnl = sum(tr.pnl_usd for tr in filled)
    sim_minutes = N_TICKS * TICK_MS / 1000 / 60

    summary = {
        "simulated_market_time_minutes": round(sim_minutes, 1),
        "ticks": N_TICKS,
        "opportunities_detected": opportunities_detected,
        "opportunities_blocked_by_inventory": opportunities_blocked_inventory,
        "opportunities_missed_to_latency": opportunities_missed_latency,
        "trades_filled": len(filled),
        "fill_rate_of_detected_pct": round(100 * len(filled) / opportunities_detected, 1) if opportunities_detected else 0,
        "total_pnl_usd": round(total_pnl, 2),
        "avg_pnl_per_filled_trade_usd": round(total_pnl / len(filled), 4) if filled else 0,
        "avg_net_edge_bps_filled": round(statistics.mean(tr.net_edge_bps for tr in filled), 2) if filled else 0,
        "final_balances": {
            name: {"usd": round(b.usd, 2), "btc": round(b.btc, 6),
                   "mark_to_market_usd": round(b.usd + b.btc * shared_mid, 2)}
            for name, b in books.items()
        },
        "trades_per_venue_pair": {},
        "assumptions": {
            "retail_latency_ms": RETAIL_LATENCY_MS,
            "opportunity_half_life_ms": OPPORTUNITY_HALF_LIFE_MS,
            "taker_fees_bps": taker_fee_bps,
            "trade_notional_usd": TRADE_NOTIONAL_USD,
            "min_net_edge_required_bps": MIN_NET_EDGE_BPS,
            "note": "Synthetic price data calibrated to BTC-like volatility; not live market data.",
        },
    }

    pair_counts: Dict[str, int] = {}
    for tr in filled:
        key = f"{tr.buy_ex}->{tr.sell_ex}"
        pair_counts[key] = pair_counts.get(key, 0) + 1
    summary["trades_per_venue_pair"] = dict(sorted(pair_counts.items(), key=lambda kv: -kv[1]))

    return summary, trades


def print_summary(label: str, summary: Dict):
    print("=" * 70)
    print(f"SCENARIO: {label}")
    print("=" * 70)
    print(f"Simulated market time : {summary['simulated_market_time_minutes']} min ({summary['ticks']:,} ticks)")
    print(f"Opportunities detected: {summary['opportunities_detected']:,}")
    print(f"  blocked (no inventory on one leg): {summary['opportunities_blocked_by_inventory']:,}")
    print(f"  missed  (closed before we filled) : {summary['opportunities_missed_to_latency']:,}")
    print(f"Trades filled         : {summary['trades_filled']:,}  "
          f"({summary['fill_rate_of_detected_pct']}% of detected)")
    print(f"Avg net edge (filled) : {summary['avg_net_edge_bps_filled']} bps")
    print(f"Avg PnL / filled trade: ${summary['avg_pnl_per_filled_trade_usd']}")
    print(f"TOTAL SIMULATED PNL   : ${summary['total_pnl_usd']}")
    print("-" * 70)
    print("Trades by venue pair (buy -> sell):")
    for pair, count in summary["trades_per_venue_pair"].items():
        print(f"  {pair:<22} {count:,}")
    print("-" * 70)
    print("Final balances (mark-to-market):")
    for name, bal in summary["final_balances"].items():
        print(f"  {name:<10} ${bal['usd']:>10,.2f} USD + {bal['btc']:.6f} BTC "
              f"= ${bal['mark_to_market_usd']:>10,.2f}")
    print()


def main():
    all_results = {}
    for label, fees in FEE_SCENARIOS.items():
        summary, trades = run_simulation(fees)
        print_summary(label, summary)
        all_results[label] = summary

    out = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "scenarios": all_results,
    }
    with open("crypto_arb_sim_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("Full summary written to backend/crypto_arb_sim_results.json")


if __name__ == "__main__":
    main()
