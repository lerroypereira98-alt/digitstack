"""
Main Orchestrator
Runs the full UGC pipeline:
  1. Discover viral products
  2. Filter by affiliate quality
  3. Download product images
  4. Generate scripts + voiceovers
  5. Compose videos and slideshows
  6. Schedule posts
"""

import logging
import os
import uuid
import yaml
from pathlib import Path
from dataclasses import asdict

from agents.viral_finder import ViralFinderAgent
from agents.affiliate_checker import AffiliateChecker
from generators.image_fetcher import ImageFetcher
from generators.tts_engine import TTSEngine, ScriptGenerator
from generators.video_composer import VideoComposer
from generators.slideshow_maker import SlideshowMaker
from scheduler.post_scheduler import CampaignScheduler

logger = logging.getLogger(__name__)


def load_config(path: str = "config/settings.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def setup_logging(config: dict):
    log_cfg = config.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO"))
    log_file = log_cfg.get("file", "output/ugc_cloner.log")
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file),
        ],
    )


class UGCPipeline:
    """Full automated UGC content production pipeline."""

    def __init__(self, config: dict):
        self.config = config
        gen = config.get("generation", {})
        self.batch_size = gen.get("batch_size", 250)
        self.video_split = gen.get("video_split", 0.6)
        self.videos_per_product = gen.get("videos_per_product", 5)

        self.viral_finder = ViralFinderAgent(config)
        self.affiliate_checker = AffiliateChecker(config)
        self.image_fetcher = ImageFetcher(
            output_dir=config.get("output", {}).get("images_dir", "output/images"),
            use_stable_diffusion=gen.get("use_stable_diffusion", False),
            sd_url=gen.get("sd_api_url", "http://127.0.0.1:7860"),
        )
        self.tts = TTSEngine(
            engine=gen.get("tts_engine", "gtts"),
            language=gen.get("tts_language", "en"),
            speed=gen.get("tts_speed", 1.15),
        )
        self.script_gen = ScriptGenerator()
        self.video_composer = VideoComposer(config)
        self.slideshow_maker = SlideshowMaker(config)
        self.scheduler = CampaignScheduler(config)

    def run(self, dry_run: bool = False) -> dict:
        """Execute the full pipeline. Returns summary stats."""
        logger.info("=" * 60)
        logger.info("UGC Pipeline starting — target: %d pieces of content", self.batch_size)
        logger.info("=" * 60)

        # ── STEP 1: Product Discovery ─────────────────────────────
        logger.info("Step 1: Discovering viral products...")
        products = self.viral_finder.discover(limit=100)
        logger.info("Discovered %d products", len(products))

        # ── STEP 2: Affiliate Filter ──────────────────────────────
        logger.info("Step 2: Filtering by affiliate quality...")
        qualified = self.affiliate_checker.filter_and_rank(products, min_quality="fair")
        logger.info("%d products passed affiliate filter", len(qualified))

        if not qualified:
            logger.error("No products passed affiliate filter. Check your config.")
            return {"error": "No qualified products found"}

        # ── STEP 3: Content Generation Loop ───────────────────────
        target_videos = int(self.batch_size * self.video_split)
        target_slides = self.batch_size - target_videos
        content_items = []
        videos_made = 0
        slides_made = 0

        logger.info(
            "Step 3: Generating content — %d videos + %d slideshows...",
            target_videos,
            target_slides,
        )

        for product, offer in qualified:
            if videos_made >= target_videos and slides_made >= target_slides:
                break

            logger.info(
                "Processing: %s [%s, $%.2f/sale]",
                product.title[:50],
                offer.offer_quality,
                offer.commission_usd,
            )

            # Download images
            images = self.image_fetcher.fetch_product_images(product, count=6)
            if not images:
                logger.warning("No images for %s — skipping", product.title[:30])
                continue

            prepared_images = self.image_fetcher.prepare_for_video(
                images, target_size=(1080, 1920)
            )

            # Generate multiple content pieces per product
            for variant in range(self.videos_per_product):
                if videos_made >= target_videos and slides_made >= target_slides:
                    break

                script = self.script_gen.generate(product)
                safe_name = self._safe_name(product.title, variant)

                hashtags = self._build_hashtags(product, offer)
                caption = self._build_caption(script, offer)

                # Generate voiceover
                audio_path = None
                if not dry_run:
                    audio_path = Path(
                        self.config.get("output", {}).get("audio_dir", "output/audio")
                    ) / f"{safe_name}.mp3"
                    audio_path = self.tts.synthesize(script["full"], audio_path)

                # Decide: video or slideshow for this variant
                make_video = videos_made < target_videos

                if make_video and not dry_run:
                    video_path = self.video_composer.compose_zoom_pan_video(
                        images=prepared_images,
                        audio_path=audio_path,
                        script=script,
                        product=product,
                        output_name=safe_name,
                    )
                    if video_path:
                        videos_made += 1
                        content_items.append({
                            "type": "video",
                            "video_path": str(video_path),
                            "slides": [],
                            "caption": caption,
                            "hashtags": hashtags,
                            "product_title": product.title,
                            "affiliate_url": offer.affiliate_url,
                            "product": product.asin,
                        })
                elif not dry_run:
                    slides = self.slideshow_maker.create_product_slideshow(
                        images=prepared_images,
                        script=script,
                        product=product,
                        output_name=safe_name,
                    )
                    if slides:
                        slides_made += 1
                        content_items.append({
                            "type": "slideshow",
                            "video_path": "",
                            "slides": [str(s) for s in slides],
                            "caption": caption,
                            "hashtags": hashtags,
                            "product_title": product.title,
                            "affiliate_url": offer.affiliate_url,
                            "product": product.asin,
                        })
                else:
                    # Dry run — just count
                    if make_video:
                        videos_made += 1
                    else:
                        slides_made += 1
                    content_items.append({
                        "type": "video" if make_video else "slideshow",
                        "product_title": product.title,
                        "caption": caption,
                        "hashtags": hashtags,
                        "affiliate_url": offer.affiliate_url,
                        "dry_run": True,
                    })

        logger.info(
            "Content created: %d videos, %d slideshows (%d total)",
            videos_made,
            slides_made,
            videos_made + slides_made,
        )

        # ── STEP 4: Schedule Posts ─────────────────────────────────
        logger.info("Step 4: Scheduling posts...")
        scheduled = self.scheduler.schedule_batch(content_items)
        self.scheduler.print_schedule(limit=30)

        summary = {
            "products_discovered": len(products),
            "products_qualified": len(qualified),
            "videos_created": videos_made,
            "slideshows_created": slides_made,
            "total_content": videos_made + slides_made,
            "posts_scheduled": scheduled,
        }

        logger.info("=" * 60)
        logger.info("Pipeline complete: %s", summary)
        logger.info("=" * 60)
        return summary

    def _safe_name(self, title: str, variant: int) -> str:
        import re
        clean = re.sub(r"[^\w]", "_", title[:30]).strip("_")
        uid = uuid.uuid4().hex[:6]
        return f"{clean}_{variant}_{uid}"

    def _build_hashtags(self, product, offer) -> list[str]:
        tags = [
            "ugc",
            "amazonfinds",
            "tiktokmademebuyit",
            "affiliatemarketing",
            product.category.lower().replace(" ", ""),
            "productreview",
            "viral",
        ]
        if "tiktok_trending" in product.tags:
            tags.append("trending")
        return list(dict.fromkeys(tags))[:30]

    def _build_caption(self, script: dict, offer) -> str:
        price_line = f"${offer.price:.2f}" if offer.price else ""
        parts = [script["hook"]]
        if price_line:
            parts.append(f"Only {price_line}!")
        parts.append(script["cta"])
        parts.append("\n\n(Affiliate link in bio — costs you nothing extra)")
        return " ".join(parts)
