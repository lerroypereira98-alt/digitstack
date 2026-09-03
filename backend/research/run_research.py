#!/usr/bin/env python3
"""
One-off research CLI.

Discovers prediction-market platforms currently listing 1-minute /
5-minute markets (Kalshi, Polymarket), plus related Reddit/YouTube
discussion, and writes a JSON + Markdown report.

Standalone — does not touch the live trading engine in main.py and
places no trades.

Usage:
    cd backend
    python -m research.run_research
    python -m research.run_research --minutes 1 5 15 --out-dir ../reports
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/

from research.market_scanner import scan_all
from research.social_scanner import scan_social

DEFAULT_QUERIES = [
    "Polymarket 5 minute market",
    "Kalshi 1 minute crypto market",
    "5 min prediction market bitcoin",
    "1 minute crypto prediction market",
]


def build_report(target_minutes=(1, 5), social_queries=None) -> dict:
    platforms = scan_all(target_minutes=target_minutes)
    social = scan_social(social_queries or DEFAULT_QUERIES)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_minutes": list(target_minutes),
        "platforms": platforms,
        "platform_counts": {k: len(v) for k, v in platforms.items()},
        "social": social,
        "social_counts": {k: len(v) for k, v in social.items()},
    }


def to_markdown(report: dict) -> str:
    lines = [
        "# 1-min / 5-min prediction market research",
        f"_Generated {report['generated_at']}_",
        "",
        "## Platforms",
    ]
    if not report["platforms"]:
        lines.append(
            "No matching markets found — platforms may not currently list any in this "
            "window, or the network path to their API was unavailable from this machine."
        )
    for platform, rows in report["platforms"].items():
        lines.append(f"\n### {platform} ({len(rows)} markets)")
        for r in rows[:25]:
            price = f"{r['yes_price']:.2f}" if r.get("yes_price") is not None else "?"
            lines.append(
                f"- **{r['duration_min']}m** [{r['title']}]({r.get('url') or '#'}) "
                f"— yes≈{price}, closes {r.get('close_time')}"
            )

    lines.append("\n## Social mentions")
    lines.append("_Twitter/X and Instagram are intentionally excluded — both block "
                  "unauthenticated scraping and require paid/authenticated API access._")
    for source, rows in report["social"].items():
        lines.append(f"\n### {source} ({len(rows)} results)")
        for r in rows[:20]:
            lines.append(f"- [{r['title']}]({r.get('url') or '#'})")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", default="../reports", help="Directory to write the report into")
    parser.add_argument("--minutes", nargs="+", type=int, default=[1, 5], help="Duration buckets to keep, in minutes")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    report = build_report(target_minutes=tuple(args.minutes))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = os.path.join(args.out_dir, f"market_research_{stamp}.json")
    md_path = os.path.join(args.out_dir, f"market_research_{stamp}.md")

    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    with open(md_path, "w") as f:
        f.write(to_markdown(report))

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    for platform, count in report["platform_counts"].items():
        print(f"  {platform}: {count} markets in target window(s)")
    for source, count in report["social_counts"].items():
        print(f"  {source}: {count} mentions")


if __name__ == "__main__":
    main()
