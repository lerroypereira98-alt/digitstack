#!/usr/bin/env python3
"""
UGC Video Cloner — Main Entry Point

Usage:
  python main.py                        # Full pipeline (discover → generate → schedule)
  python main.py --dry-run              # Preview what would be created (no actual generation)
  python main.py --step discover        # Only run product discovery
  python main.py --step generate        # Only generate content (requires prior discovery)
  python main.py --step schedule        # Only run the post scheduler (posts due content)
  python main.py --config my_config.yaml
  python main.py --schedule-only        # Run scheduler daemon (post due content now)
"""

import argparse
import json
import logging
import sys
import os
from pathlib import Path

# Ensure local modules are importable
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.orchestrator import UGCPipeline, load_config, setup_logging

logger = logging.getLogger(__name__)


def cmd_discover(config: dict) -> list:
    """Run only product discovery + affiliate filter."""
    from agents.viral_finder import ViralFinderAgent
    from agents.affiliate_checker import AffiliateChecker

    finder = ViralFinderAgent(config)
    checker = AffiliateChecker(config)

    products = finder.discover(limit=100)
    qualified = checker.filter_and_rank(products, min_quality="fair")

    print(f"\nDiscovered {len(products)} products.")
    print(f"Qualified (affiliate 'fair' or better): {len(qualified)}\n")
    print(f"{'Rank':<5} {'Quality':<12} {'$/sale':<10} {'Est. Monthly':<15} {'Title'}")
    print("-" * 80)
    for i, (product, offer) in enumerate(qualified[:30]):
        print(
            f"{i+1:<5} {offer.offer_quality:<12} ${offer.commission_usd:<9.2f} "
            f"${offer.estimated_monthly_earnings:<14.0f} {product.title[:45]}"
        )

    # Save discovery results
    results_file = Path("output/discovery_results.json")
    results_file.parent.mkdir(exist_ok=True)
    results_file.write_text(
        json.dumps(
            [
                {
                    "title": p.title,
                    "asin": p.asin,
                    "price": p.price,
                    "rating": p.rating,
                    "reviews": p.review_count,
                    "category": p.category,
                    "viral_score": p.viral_score,
                    "affiliate_url": p.affiliate_url,
                    "commission_pct": o.commission_pct,
                    "commission_usd": o.commission_usd,
                    "quality": o.offer_quality,
                    "est_monthly": o.estimated_monthly_earnings,
                }
                for p, o in qualified
            ],
            indent=2,
        )
    )
    print(f"\nResults saved to {results_file}")
    return qualified


def cmd_schedule_run(config: dict, dry_run: bool = False):
    """Run the scheduler — post any content that is currently due."""
    from scheduler.post_scheduler import CampaignScheduler
    from scheduler.platform_poster import TikTokPoster, InstagramPoster, YouTubePoster

    sched = CampaignScheduler(config)
    tiktok_cfg = config.get("tiktok", {})
    instagram_cfg = config.get("instagram", {})
    youtube_cfg = config.get("youtube", {})

    def poster_factory(platform: str, post: dict):
        content = post["content"]
        video_path = Path(content.get("video_path", "")) if content.get("video_path") else None
        caption = content.get("caption", "")
        hashtags = content.get("hashtags", [])

        if platform == "tiktok":
            poster = TikTokPoster(tiktok_cfg.get("access_token", ""))
            if not video_path or not video_path.exists():
                return {"success": False, "error": "No video file"}
            return poster.post_video(video_path, caption, hashtags)

        elif platform == "instagram":
            poster = InstagramPoster(
                access_token=instagram_cfg.get("access_token", ""),
                ig_user_id=instagram_cfg.get("ig_user_id", ""),
            )
            return poster.post_reel(
                video_path=video_path,
                caption=caption,
                hashtags=hashtags,
                video_url=content.get("video_url", ""),
            )

        elif platform == "youtube_shorts":
            poster = YouTubePoster(
                credentials_file=youtube_cfg.get("credentials_file", "config/youtube_credentials.json")
            )
            if not video_path or not video_path.exists():
                return {"success": False, "error": "No video file"}
            return poster.post_short(
                video_path=video_path,
                title=content.get("product_title", "")[:100],
                description=caption,
                tags=hashtags,
            )

        return {"success": False, "error": f"Unknown platform: {platform}"}

    sched.run_scheduler(poster_factory, dry_run=dry_run)
    sched.print_schedule(limit=10)


def main():
    parser = argparse.ArgumentParser(
        description="UGC Video Cloner — Automated affiliate content pipeline"
    )
    parser.add_argument(
        "--config", default="config/settings.yaml", help="Path to settings.yaml"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview pipeline without generating actual files"
    )
    parser.add_argument(
        "--step",
        choices=["discover", "generate", "schedule", "all"],
        default="all",
        help="Run a specific pipeline step",
    )
    parser.add_argument(
        "--workers", type=int, default=None, help="Number of parallel workers"
    )
    parser.add_argument(
        "--batch-size", type=int, default=None, help="Override batch size from config"
    )
    args = parser.parse_args()

    # Load config
    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"Config not found: {args.config}")
        print("Run from the ugc_cloner/ directory, or specify --config path")
        sys.exit(1)

    # Override config from CLI
    if args.batch_size:
        config.setdefault("generation", {})["batch_size"] = args.batch_size

    setup_logging(config)

    # Ensure output dirs exist
    for d in ["output/videos", "output/slideshows", "output/images", "output/audio"]:
        Path(d).mkdir(parents=True, exist_ok=True)

    if args.step == "discover":
        cmd_discover(config)

    elif args.step == "schedule":
        cmd_schedule_run(config, dry_run=args.dry_run)

    elif args.step in ("generate", "all"):
        pipeline = UGCPipeline(config)
        summary = pipeline.run(dry_run=args.dry_run)
        print("\n" + "=" * 60)
        print("PIPELINE SUMMARY")
        print("=" * 60)
        for k, v in summary.items():
            print(f"  {k:<30} {v}")
        print("=" * 60)

        if not args.dry_run:
            print("\nNext: Run the scheduler to start posting.")
            print("  python main.py --step schedule")
            print("\nOr set up a cron job:")
            print("  */30 * * * * cd /path/to/ugc_cloner && python main.py --step schedule")


if __name__ == "__main__":
    main()
