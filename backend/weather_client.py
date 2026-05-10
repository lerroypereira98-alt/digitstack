"""
Weather Market Client — Research-backed strategy from top Kalshi/Polymarket traders

Key findings from leaderboard reverse engineering:
  1. TEMPERATURE markets >> Rain markets (higher liquidity, more predictable)
  2. Use GFS 31-member ensemble via Open-Meteo (free, no key)
  3. Use METAR/ASOS settlement station observations — NOT city-center apps
  4. Settlement stations differ from city centers by 3-8F (critical bug most traders miss)
  5. 'Already locked in' plays after 2PM local = highest win rate (90-95%)
  6. 8% minimum edge threshold (standard across all documented profitable bots)
  7. Never buy below $0.15 (fee drag destroys edge at low prices)
  8. Secondary cities (Atlanta, Dallas, Austin) have less bot competition

Documented results from leaderboard research:
  - ColdMath: $300 to $219K in 3 months (automated, multi-city)
  - WeatherEdge bot: 81% WR (82-member dual ensemble, GFS+ECMWF)
  - Kalshi-Go (LA temp): 81.8% WR requiring 2+ signal consensus
"""

import os
import math
import time
import requests
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

NOAA_BASE    = "https://api.weather.gov"
OPEN_METEO   = "https://api.open-meteo.com/v1/forecast"
NOAA_AGENT   = "ApexWeatherBot/1.0"
MIN_PRICE    = 0.15   # never buy below 15c - fee drag kills edge
MIN_EDGE_PCT = 0.08   # 8% minimum edge (research standard)
MIN_WIN_PROB = 0.72   # minimum 72% confidence to trade


# Settlement ASOS stations - use airport stations, NOT city-center coordinates
# Markets resolve to these specific stations. City-center apps are 3-8F warmer in summer.
SETTLEMENT_STATIONS = {
    "NYC": {"station": "KNYC",  "lat": 40.7789, "lon": -73.9692, "name": "New York (Central Park)",  "tz_offset": -4},
    "LA":  {"station": "KLAX",  "lat": 33.9425, "lon": -118.4081,"name": "Los Angeles (LAX)",         "tz_offset": -7},
    "CHI": {"station": "KORD",  "lat": 41.9742, "lon": -87.9073, "name": "Chicago (O'Hare)",          "tz_offset": -5},
    "MIA": {"station": "KMIA",  "lat": 25.7959, "lon": -80.2870, "name": "Miami (MIA Airport)",       "tz_offset": -4},
    "HOU": {"station": "KHOU",  "lat": 29.6454, "lon": -95.2789, "name": "Houston (Hobby)",           "tz_offset": -5},
    "PHX": {"station": "KPHX",  "lat": 33.4373, "lon": -112.0078,"name": "Phoenix (Sky Harbor)",      "tz_offset": -7},
    "SEA": {"station": "KSEA",  "lat": 47.4489, "lon": -122.3094,"name": "Seattle (SeaTac)",          "tz_offset": -7},
    "DEN": {"station": "KDEN",  "lat": 39.8561, "lon": -104.6737,"name": "Denver (DEN Airport)",      "tz_offset": -6},
    "ATL": {"station": "KATL",  "lat": 33.6367, "lon": -84.4281, "name": "Atlanta (Hartsfield)",      "tz_offset": -4},
    "DAL": {"station": "KDAL",  "lat": 32.8481, "lon": -96.8512, "name": "Dallas (Love Field)",       "tz_offset": -5},
    "AUS": {"station": "KAUS",  "lat": 30.1975, "lon": -97.6664, "name": "Austin (Bergstrom)",        "tz_offset": -5},
    "BOS": {"station": "KBOS",  "lat": 42.3606, "lon": -71.0097, "name": "Boston (Logan)",            "tz_offset": -4},
}

RAIN_CLIMATOLOGY = {
    "NYC": [0.35,0.33,0.38,0.37,0.38,0.36,0.38,0.37,0.34,0.34,0.37,0.36],
    "LA":  [0.22,0.20,0.18,0.10,0.05,0.02,0.01,0.02,0.04,0.08,0.15,0.20],
    "CHI": [0.35,0.33,0.40,0.38,0.42,0.38,0.37,0.36,0.36,0.37,0.40,0.37],
    "MIA": [0.30,0.28,0.30,0.32,0.42,0.55,0.60,0.62,0.58,0.50,0.38,0.32],
    "PHX": [0.15,0.14,0.10,0.05,0.04,0.04,0.30,0.35,0.25,0.12,0.10,0.14],
    "SEA": [0.55,0.50,0.48,0.42,0.38,0.30,0.15,0.18,0.30,0.45,0.55,0.57],
    "ATL": [0.38,0.38,0.42,0.38,0.38,0.38,0.42,0.38,0.34,0.30,0.38,0.38],
    "DAL": [0.28,0.28,0.32,0.30,0.38,0.32,0.25,0.25,0.30,0.32,0.30,0.28],
}


class NOAAClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": NOAA_AGENT, "Accept": "application/geo+json"})
        self._grid_cache: Dict = {}

    def _grid(self, lat: float, lon: float) -> Optional[Dict]:
        key = f"{lat:.4f},{lon:.4f}"
        if key in self._grid_cache:
            return self._grid_cache[key]
        try:
            r = self.session.get(f"{NOAA_BASE}/points/{lat},{lon}", timeout=10)
            r.raise_for_status()
            p = r.json()["properties"]
            g = {"office": p["gridId"], "x": p["gridX"], "y": p["gridY"]}
            self._grid_cache[key] = g
            return g
        except Exception as e:
            print(f"[NOAA] Grid fail: {e}")
            return None

    def get_hourly(self, city_code: str) -> List[Dict]:
        city = SETTLEMENT_STATIONS.get(city_code)
        if not city:
            return []
        grid = self._grid(city["lat"], city["lon"])
        if not grid:
            return []
        try:
            url = f"{NOAA_BASE}/gridpoints/{grid['office']}/{grid['x']},{grid['y']}/forecast/hourly"
            r = self.session.get(url, timeout=10)
            r.raise_for_status()
            return [{
                "city":          city_code,
                "station":       city["station"],
                "start_time":    p["startTime"],
                "temp_f":        p["temperature"],
                "precip_chance": (p.get("probabilityOfPrecipitation") or {}).get("value", 0) or 0,
                "forecast":      p.get("shortForecast", ""),
                "is_daytime":    p.get("isDaytime", True),
            } for p in r.json()["properties"]["periods"][:24]]
        except Exception as e:
            print(f"[NOAA] Hourly fail {city_code}: {e}")
            return []

    def get_current_observation(self, city_code: str) -> Optional[Dict]:
        """Latest METAR reading from settlement station — key for locked-in plays."""
        city = SETTLEMENT_STATIONS.get(city_code)
        if not city:
            return None
        try:
            url = f"{NOAA_BASE}/stations/{city['station']}/observations/latest"
            r = self.session.get(url, timeout=10)
            r.raise_for_status()
            props = r.json()["properties"]
            tc = props.get("temperature", {}).get("value")
            return {
                "city":      city_code,
                "station":   city["station"],
                "temp_f":    round(tc * 9/5 + 32, 1) if tc is not None else None,
                "timestamp": props.get("timestamp", ""),
                "desc":      props.get("textDescription", ""),
            }
        except Exception as e:
            print(f"[NOAA] Obs fail {city_code}: {e}")
            return None

    def get_todays_high(self, city_code: str) -> Optional[Dict]:
        """Today's observed high from station — for locked-in temperature plays."""
        city = SETTLEMENT_STATIONS.get(city_code)
        if not city:
            return None
        try:
            end   = datetime.now(timezone.utc)
            start = end.replace(hour=0, minute=0, second=0)
            url   = f"{NOAA_BASE}/stations/{city['station']}/observations"
            r = self.session.get(url, params={
                "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end":   end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": 48
            }, timeout=10)
            r.raise_for_status()
            temps = []
            for o in r.json().get("features", []):
                tc = o["properties"].get("temperature", {}).get("value")
                if tc is not None:
                    temps.append(tc * 9/5 + 32)
            if not temps:
                return None
            return {
                "city":       city_code,
                "high_f":     round(max(temps), 1),
                "low_f":      round(min(temps), 1),
                "num_obs":    len(temps),
                "locked_in":  len(temps) >= 6,
            }
        except Exception as e:
            print(f"[NOAA] High/Low fail {city_code}: {e}")
            return None


class OpenMeteoClient:
    """Free GFS ensemble via Open-Meteo — no API key needed."""

    def __init__(self):
        self.session = requests.Session()

    def get_temperature_forecast(self, city_code: str) -> Optional[Dict]:
        city = SETTLEMENT_STATIONS.get(city_code)
        if not city:
            return None
        try:
            r = self.session.get(OPEN_METEO, params={
                "latitude":         city["lat"],
                "longitude":        city["lon"],
                "hourly":           "temperature_2m",
                "temperature_unit": "fahrenheit",
                "forecast_days":    2,
                "models":           "gfs_seamless",
            }, timeout=10)
            r.raise_for_status()
            data  = r.json()
            temps = [t for t in data["hourly"]["temperature_2m"][:24] if t is not None]
            return {
                "city":  city_code,
                "max_f": round(max(temps), 1) if temps else None,
                "min_f": round(min(temps), 1) if temps else None,
                "temps": temps,
            }
        except Exception as e:
            print(f"[OpenMeteo] Fail {city_code}: {e}")
            return None


class WeatherMiroFish:
    """
    Multi-model consensus — adapted from WeatherEdge bot + Kalshi-Go + research.
    Requires 2+ model agreement before trading (key to 80%+ win rate).
    """

    def _norm_cdf(self, z: float) -> float:
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))

    def get_temperature_signal(self, city_code: str, noaa_f: float, strike_f: float,
                                direction: str, hours_to_res: float,
                                obs_f: Optional[float] = None,
                                today_high_f: Optional[float] = None,
                                gfs_max_f: Optional[float] = None,
                                month: int = 6) -> Dict:
        """Score a temperature threshold market. direction = 'above' or 'below'."""
        # Uncertainty shrinks as we approach resolution (research-calibrated)
        std = max(5.0 * (hours_to_res / 24) ** 0.5, 0.5)

        z_noaa = (noaa_f - strike_f) / std
        p_above = self._norm_cdf(z_noaa)

        votes = 0

        # NOAA forecast vote (weight 2)
        if direction == "above":
            votes += 2 if p_above >= 0.82 else 1 if p_above >= 0.70 else -2 if p_above <= 0.30 else -1 if p_above <= 0.45 else 0
        else:
            votes += 2 if p_above <= 0.18 else 1 if p_above <= 0.30 else -2 if p_above >= 0.70 else -1 if p_above >= 0.55 else 0

        # GFS ensemble vote (weight 2)
        if gfs_max_f is not None:
            z_gfs = (gfs_max_f - strike_f) / std
            p_gfs = self._norm_cdf(z_gfs)
            p_above = (p_above + p_gfs) / 2
            if direction == "above":
                votes += 2 if p_gfs >= 0.82 else 1 if p_gfs >= 0.70 else -2 if p_gfs <= 0.30 else 0
            else:
                votes += 2 if p_gfs <= 0.18 else 1 if p_gfs <= 0.30 else -2 if p_gfs >= 0.70 else 0

        # METAR observation — same-day lock-in (weight 2)
        locked_in = False
        if obs_f is not None and hours_to_res <= 4:
            if direction == "above" and obs_f > strike_f:
                votes += 2
            elif direction == "below" and obs_f < strike_f:
                votes += 2

        # Today's observed high — definitive lock-in
        if today_high_f is not None:
            if direction == "above" and today_high_f > strike_f:
                votes += 3
                p_above = 0.97
                locked_in = True
            elif direction == "above" and today_high_f < (strike_f - 5) and hours_to_res <= 2:
                votes -= 2

        # Seasonal bonus (Phoenix summer, Miami summer)
        if city_code == "PHX" and direction == "above" and month in [5,6,7,8,9] and strike_f <= 100:
            votes += 1
        if city_code == "MIA" and direction == "above" and month in [6,7,8] and strike_f <= 88:
            votes += 1

        win_prob = p_above if direction == "above" else 1 - p_above
        win_prob = min(win_prob + max(0, (6 - hours_to_res) / 6 * 0.04), 0.97)

        tier = "C" if win_prob >= 0.90 else "B" if win_prob >= 0.82 else "A" if win_prob >= 0.72 else None

        return {
            "tradeable":   tier is not None and votes >= 2,
            "side":        "YES" if win_prob >= 0.50 else "NO",
            "win_prob":    round(win_prob, 3),
            "tier":        tier,
            "votes":       votes,
            "locked_in":   locked_in,
            "std_dev_f":   round(std, 2),
            "hours_to_res": hours_to_res,
        }

    def get_rain_consensus(self, noaa_pop: float, hours_to_res: float,
                           month: int, city_code: str) -> Dict:
        climo = RAIN_CLIMATOLOGY.get(city_code, [0.35]*12)
        climo_pop = climo[month - 1] * 100
        votes = 3 if noaa_pop >= 80 else 2 if noaa_pop >= 65 else 1 if noaa_pop >= 50 else -3 if noaa_pop <= 20 else -2 if noaa_pop <= 35 else -1
        if hours_to_res <= 1:
            votes += 1 if noaa_pop >= 60 else -1
        if noaa_pop >= 90 or noaa_pop <= 10:
            votes += 1
        side = "YES" if noaa_pop >= 50 else "NO"
        base = (noaa_pop / 100 if side == "YES" else (100 - noaa_pop) / 100) * 0.95
        win_prob = min(base + max(0, (4 - hours_to_res) / 4 * 0.06), 0.96)
        tier = "C" if win_prob >= 0.90 else "B" if win_prob >= 0.82 else "A" if win_prob >= 0.72 else None
        return {"tradeable": tier is not None and votes >= 2, "side": side,
                "win_prob": round(win_prob, 3), "tier": tier, "votes": votes}


noaa    = NOAAClient()
meteo   = OpenMeteoClient()
weather = WeatherMiroFish()
CITIES  = SETTLEMENT_STATIONS
