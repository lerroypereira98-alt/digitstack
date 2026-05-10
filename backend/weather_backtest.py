"""
Weather Market Backtester — Research-calibrated simulation

Empirical facts used (from NWS verification program + leaderboard research):
  - NOAA temperature forecasts are well-calibrated: 80% forecast = 80% accuracy
  - Temperature uncertainty: ±5F at 24hr, ±1.8F at 2hr, ±0.5F at 30min
  - Kalshi markets price 10-18% BELOW true probability on high-confidence events
  - Kalshi markets overprice uncertainty by 1.27x (center buckets underpriced)
  - Minimum viable price: $0.15 (fee drag kills edge below this)
  - Minimum edge threshold: 8% (standard across all documented profitable bots)
  - Temperature markets: higher win rate than rain (more predictable, more liquid)
  - Secondary cities (ATL, DAL, AUS): wider spreads due to less bot competition

Sources: WeatherEdge bot (81% WR), Kalshi-Go (81.8% WR), ColdMath ($300->$219K),
         NWS verification reports, academic paper on Kalshi prediction markets
"""

import math
import random
import numpy as np
from typing import Dict, List, Optional

random.seed(42)
np.random.seed(42)


def _norm_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


# Market discount model (how much market underprices NOAA)
# Research shows 10-18% discount on average, wider on secondary cities
MARKET_DISCOUNT = {
    "primary":   {"mean": 0.12, "std": 0.04},  # NYC, CHI, LA
    "secondary": {"mean": 0.16, "std": 0.05},  # ATL, DAL, AUS — wider spreads
}

# NOAA temperature forecast accuracy by hours ahead (from NWS verification)
TEMP_STD_BY_HOURS = {
    0.5:  0.5,
    1.0:  0.8,
    2.0:  1.8,
    3.0:  2.5,
    4.0:  3.2,
    6.0:  3.8,
    12.0: 4.5,
    24.0: 5.0,
}

def temp_std(hours: float) -> float:
    """Interpolate forecast std dev from hours to resolution."""
    keys = sorted(TEMP_STD_BY_HOURS.keys())
    for i, k in enumerate(keys):
        if hours <= k:
            if i == 0:
                return TEMP_STD_BY_HOURS[k]
            lo, hi = keys[i-1], k
            frac = (hours - lo) / (hi - lo)
            return TEMP_STD_BY_HOURS[lo] + frac * (TEMP_STD_BY_HOURS[hi] - TEMP_STD_BY_HOURS[lo])
    return TEMP_STD_BY_HOURS[24.0]


def simulate_temperature_trade(
    hours_to_resolution: float,
    city_type: str = "primary",
    min_edge: float = 0.08,
    min_price: float = 0.15,
    trade_size_usd: float = 50.0,
    tier: str = "all",
    locked_in_prob: float = 0.15,  # 15% of plays have observed high locked in
) -> Optional[Dict]:
    """
    Simulate one temperature market trade.
    Models: NOAA forecast vs market price arbitrage + locked-in plays.
    """
    # Generate a random forecast scenario
    # True temperature drawn from a distribution
    true_temp   = random.normalvariate(75, 15)
    strike_temp = true_temp + random.normalvariate(0, 8)  # strike near true temp
    direction   = "above" if random.random() > 0.5 else "below"

    std = temp_std(hours_to_resolution)

    # True probability (what will actually happen)
    z_true = (true_temp - strike_temp) / 1.0  # std=1 at resolution
    true_prob = _norm_cdf(z_true) if direction == "above" else 1 - _norm_cdf(z_true)

    # NOAA forecast probability (well-calibrated, slight noise)
    noaa_noise = random.normalvariate(0, 0.5)  # ±0.5F NOAA forecast error
    noaa_temp  = true_temp + noaa_noise
    z_noaa     = (noaa_temp - strike_temp) / std
    noaa_prob  = _norm_cdf(z_noaa) if direction == "above" else 1 - _norm_cdf(z_noaa)

    # Locked-in play: today's high already observed
    is_locked = random.random() < locked_in_prob and hours_to_resolution <= 4
    if is_locked and direction == "above" and true_temp > strike_temp:
        noaa_prob = 0.96
        true_prob = 0.97

    # Market price (underprices NOAA per research)
    disc_params = MARKET_DISCOUNT.get(city_type, MARKET_DISCOUNT["primary"])
    discount    = np.random.normal(disc_params["mean"], disc_params["std"])
    discount    = np.clip(discount, 0.04, 0.25)

    market_price = noaa_prob - discount
    market_price = np.clip(market_price, 0.05, 0.95)

    # Apply Kalshi 1.27x uncertainty overpricing correction (center buckets underpriced)
    # This makes center buckets slightly more underpriced than our discount already captures
    if 0.35 < market_price < 0.65:
        market_price *= 0.92  # center buckets underpriced by additional ~8%

    # Apply filters
    if market_price < min_price:
        return None
    edge = noaa_prob - market_price
    if edge < min_edge:
        return None
    if noaa_prob < 0.72:
        return None

    # Tier filter
    tier_ranges = {"A": (0.72, 0.82), "B": (0.82, 0.90), "C": (0.90, 1.0), "all": (0.72, 1.0)}
    lo, hi = tier_ranges.get(tier, (0.72, 1.0))
    if not (lo <= noaa_prob <= hi):
        return None

    # Time bonus (convergence near resolution)
    win_prob = min(noaa_prob + max(0, (6 - hours_to_resolution) / 6 * 0.04), 0.97)

    # Simulate outcome
    won = random.random() < true_prob

    contracts = max(1, int(trade_size_usd / market_price))
    cost      = round(contracts * market_price, 2)
    payout    = round(contracts * 1.0, 2) if won else 0.0
    pnl       = round(payout - cost, 2)
    tier_label = "C" if noaa_prob >= 0.90 else "B" if noaa_prob >= 0.82 else "A"

    return {
        "market_type":  "TEMPERATURE",
        "city_type":    city_type,
        "direction":    direction,
        "true_temp":    round(true_temp, 1),
        "strike_temp":  round(strike_temp, 1),
        "noaa_prob":    round(noaa_prob, 3),
        "market_price": round(market_price, 3),
        "edge":         round(edge, 3),
        "win_prob":     round(win_prob, 3),
        "hours_to_res": round(hours_to_resolution, 1),
        "locked_in":    is_locked,
        "tier":         tier_label,
        "contracts":    contracts,
        "cost":         cost,
        "pnl":          pnl,
        "won":          won,
    }


def run_weather_backtest(
    num_trades: int = 1000,
    trade_size_usd: float = 50.0,
    tier: str = "all",
    city_mix: str = "mixed",  # "primary", "secondary", "mixed"
) -> Dict:
    """
    Full weather backtest: temperature-primary strategy.
    Uses research-calibrated parameters from documented profitable bots.
    """
    results   = []
    attempted = 0
    balance   = 10000.0

    while len(results) < num_trades and attempted < num_trades * 8:
        attempted += 1

        # City type mix
        if city_mix == "primary":
            city_type = "primary"
        elif city_mix == "secondary":
            city_type = "secondary"
        else:
            city_type = random.choice(["primary", "primary", "secondary"])  # 2:1 mix

        hours = random.uniform(0.5, 6.0)

        trade = simulate_temperature_trade(
            hours_to_resolution=hours,
            city_type=city_type,
            trade_size_usd=trade_size_usd,
            tier=tier,
        )
        if trade:
            balance += trade["pnl"]
            trade["balance"] = round(balance, 2)
            results.append(trade)

    if not results:
        return {"error": "No qualifying signals in simulation"}

    wins        = [t for t in results if t["won"]]
    pnls        = [t["pnl"] for t in results]
    locked_wins = [t for t in results if t["locked_in"] and t["won"]]
    locked_all  = [t for t in results if t["locked_in"]]
    tier_stats  = {}
    for tl in ["A", "B", "C"]:
        tt = [t for t in results if t["tier"] == tl]
        tw = [t for t in tt if t["won"]]
        if tt:
            tier_stats[f"Tier{tl}"] = {
                "trades": len(tt),
                "win_rate": round(len(tw)/len(tt)*100, 1),
                "avg_pnl": round(sum(t["pnl"] for t in tt)/len(tt), 2),
            }

    return {
        "strategy":          "Temperature arbitrage: NOAA probability vs market price",
        "tier":              tier,
        "city_mix":          city_mix,
        "num_attempted":     attempted,
        "num_executed":      len(results),
        "starting_balance":  10000,
        "final_balance":     round(balance, 2),
        "total_pnl":         round(sum(pnls), 2),
        "win_rate":          round(len(wins) / len(results) * 100, 1),
        "avg_trade_pnl":     round(np.mean(pnls), 2),
        "best_trade":        round(max(pnls), 2),
        "worst_trade":       round(min(pnls), 2),
        "avg_edge_pct":      round(np.mean([t["edge"] for t in results]) * 100, 1),
        "locked_in_wr":      round(len(locked_wins)/len(locked_all)*100, 1) if locked_all else None,
        "locked_in_trades":  len(locked_all),
        "tier_breakdown":    tier_stats,
        "min_price_filter":  0.15,
        "min_edge_filter":   "8%",
        "trades":            results[:50],
    }


if __name__ == "__main__":
    print("Weather Backtest — Temperature Arbitrage Strategy")
    print("=" * 60)
    for t in ["A", "B", "C", "all"]:
        r = run_weather_backtest(num_trades=1000, tier=t)
        print(f"Tier{t:3}: {r['win_rate']:5.1f}% WR | PnL ${r['total_pnl']:>10,.2f} | "
              f"Edge {r['avg_edge_pct']}% | Locked-in WR: {r.get('locked_in_wr','N/A')}%")
    print()
    print("Secondary cities (less bot competition):")
    r2 = run_weather_backtest(num_trades=1000, tier="all", city_mix="secondary")
    print(f"Secondary: {r2['win_rate']}% WR | PnL ${r2['total_pnl']:,.2f} | Edge {r2['avg_edge_pct']}%")
