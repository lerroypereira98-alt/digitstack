#!/usr/bin/env python3
"""Quick test that all modules can be imported."""

import sys
from pathlib import Path

def test_imports():
    print("Testing imports...")
    try:
        # Core modules
        from agents.viral_finder import ViralFinderAgent, Product
        print("  ✓ agents.viral_finder")

        from agents.affiliate_checker import AffiliateChecker
        print("  ✓ agents.affiliate_checker")

        from generators.image_fetcher import ImageFetcher
        print("  ✓ generators.image_fetcher")

        from generators.tts_engine import TTSEngine, ScriptGenerator
        print("  ✓ generators.tts_engine")

        from generators.video_composer import VideoComposer
        print("  ✓ generators.video_composer")

        from generators.slideshow_maker import SlideshowMaker
        print("  ✓ generators.slideshow_maker")

        from scheduler.post_scheduler import CampaignScheduler, PostQueue
        print("  ✓ scheduler.post_scheduler")

        from scheduler.platform_poster import TikTokPoster, InstagramPoster, YouTubePoster
        print("  ✓ scheduler.platform_poster")

        from pipeline.orchestrator import UGCPipeline, load_config
        print("  ✓ pipeline.orchestrator")

        from pipeline.batch_runner import BatchRunner
        print("  ✓ pipeline.batch_runner")

        print("\n✅ All imports successful!\n")
        return True
    except ImportError as e:
        print(f"\n❌ Import failed: {e}\n")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
