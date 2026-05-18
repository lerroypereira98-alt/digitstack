"""
Batch Runner
Runs the pipeline in parallel workers to hit 200-300 content pieces faster.
Uses Python multiprocessing for CPU-bound image/video work.
"""

import logging
import multiprocessing
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class BatchRunner:
    """
    Parallel content generation runner.
    Image downloading + TTS are I/O bound → ThreadPoolExecutor.
    Video encoding is CPU bound → subprocess handles parallelism via ffmpeg.
    """

    def __init__(self, config: dict, max_workers: int = None):
        self.config = config
        self.max_workers = max_workers or min(4, os.cpu_count() or 2)
        logger.info("BatchRunner: %d workers", self.max_workers)

    def run_image_batch(self, tasks: list[dict]) -> list[dict]:
        """
        Download images for all products in parallel.
        tasks: list of {"product": Product, "count": int}
        Returns list of {"product": Product, "images": [Path]}
        """
        from generators.image_fetcher import ImageFetcher

        fetcher = ImageFetcher(
            output_dir=self.config.get("output", {}).get("images_dir", "output/images"),
        )
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    fetcher.fetch_product_images,
                    task["product"],
                    task.get("count", 6),
                ): task
                for task in tasks
            }
            for future in as_completed(futures):
                task = futures[future]
                try:
                    images = future.result()
                    results.append({"product": task["product"], "images": images})
                    logger.debug("Images fetched for %s: %d", task["product"].title[:30], len(images))
                except Exception as e:
                    logger.warning("Image fetch failed for %s: %s", task["product"].title[:30], e)

        return results

    def run_tts_batch(self, scripts: list[dict]) -> list[dict]:
        """
        Generate TTS audio for all scripts in parallel (I/O bound).
        scripts: list of {"text": str, "output_path": Path}
        """
        from generators.tts_engine import TTSEngine

        gen = self.config.get("generation", {})
        tts = TTSEngine(
            engine=gen.get("tts_engine", "gtts"),
            language=gen.get("tts_language", "en"),
            speed=gen.get("tts_speed", 1.15),
        )
        results = []

        # gTTS has rate limits — add delay between calls
        delay = 1.5 if gen.get("tts_engine", "gtts") == "gtts" else 0.1

        with ThreadPoolExecutor(max_workers=min(3, self.max_workers)) as executor:
            futures = {
                executor.submit(tts.synthesize, s["text"], Path(s["output_path"])): s
                for s in scripts
            }
            for future in as_completed(futures):
                s = futures[future]
                try:
                    path = future.result()
                    results.append({"text": s["text"], "audio_path": path})
                except Exception as e:
                    logger.warning("TTS failed: %s", e)
                time.sleep(delay)

        return results

    def run_video_batch(
        self, video_tasks: list[dict], style: str = "kenburns"
    ) -> list[Optional[Path]]:
        """
        Encode videos sequentially (FFmpeg already uses multiple CPU threads).
        video_tasks: list of {images, audio_path, script, product, output_name}
        """
        from generators.video_composer import VideoComposer

        composer = VideoComposer(self.config)
        results = []

        for i, task in enumerate(video_tasks):
            logger.info(
                "Encoding video %d/%d: %s",
                i + 1,
                len(video_tasks),
                task.get("output_name", ""),
            )
            try:
                if style == "kenburns":
                    path = composer.compose_zoom_pan_video(
                        images=task["images"],
                        audio_path=task.get("audio_path"),
                        script=task["script"],
                        product=task["product"],
                        output_name=task["output_name"],
                    )
                else:
                    path = composer.compose_slideshow_video(
                        images=task["images"],
                        audio_path=task.get("audio_path"),
                        script=task["script"],
                        product=task["product"],
                        output_name=task["output_name"],
                    )
                results.append(path)
            except Exception as e:
                logger.error("Video encoding failed for %s: %s", task.get("output_name"), e)
                results.append(None)

        return results

    def run_slideshow_batch(self, tasks: list[dict]) -> list[list[Path]]:
        """Create image slideshows in parallel (Pillow is CPU-bound but fast)."""
        from generators.slideshow_maker import SlideshowMaker

        maker = SlideshowMaker(self.config)
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    maker.create_product_slideshow,
                    task["images"],
                    task["script"],
                    task["product"],
                    task["output_name"],
                ): task
                for task in tasks
            }
            for future in as_completed(futures):
                task = futures[future]
                try:
                    slides = future.result()
                    results.append(slides)
                    logger.debug(
                        "Slideshow created for %s: %d slides",
                        task["product"].title[:30],
                        len(slides),
                    )
                except Exception as e:
                    logger.warning("Slideshow failed: %s", e)
                    results.append([])

        return results

    def estimate_time(self, count: int) -> str:
        """Rough time estimate for a batch."""
        # ~45s per video (FFmpeg), ~2s per slideshow set, ~3s per TTS
        video_count = int(count * 0.6)
        slide_count = count - video_count
        seconds = video_count * 45 + slide_count * 2 + count * 3
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0:
            return f"~{hours}h {minutes}m"
        return f"~{minutes}m"
