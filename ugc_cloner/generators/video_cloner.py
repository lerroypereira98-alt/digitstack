"""
Video Cloner
Downloads a viral video, analyzes its style (hook timing, text positions,
pacing, transitions), then recreates it with a new product using FFmpeg.
Uses yt-dlp for downloading — works with TikTok, Instagram, YouTube Shorts.
"""

import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VideoStyle:
    """Extracted style from a viral video."""
    duration: float
    hook_duration: float       # First scene length
    scene_count: int
    avg_scene_duration: float
    has_text_overlay: bool
    text_positions: list       # top / middle / bottom
    aspect_ratio: str          # "9:16" or "16:9"
    width: int
    height: int
    has_music: bool
    tempo: str                 # "fast" / "medium" / "slow"
    source_url: str


def check_ytdlp() -> bool:
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def install_ytdlp():
    """Install yt-dlp if not present."""
    logger.info("Installing yt-dlp...")
    subprocess.run(
        ["pip", "install", "yt-dlp", "--quiet"],
        check=True, timeout=60
    )


class VideoDownloader:
    """Downloads videos from TikTok, Instagram, YouTube using yt-dlp."""

    def __init__(self, output_dir: str = "output/clones"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if not check_ytdlp():
            install_ytdlp()

    def download(self, url: str) -> Optional[Path]:
        """Download video from URL. Returns local file path."""
        safe_name = re.sub(r"[^\w]", "_", url[-30:])
        output_template = str(self.output_dir / f"source_{safe_name}.%(ext)s")

        cmd = [
            "yt-dlp",
            "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "--output", output_template,
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            url,
        ]

        try:
            logger.info("Downloading: %s", url)
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode != 0:
                logger.error("yt-dlp error: %s", result.stderr.decode()[-300:])
                return None

            # Find the downloaded file
            for f in self.output_dir.glob(f"source_{safe_name}.*"):
                if f.suffix in (".mp4", ".webm", ".mkv"):
                    logger.info("Downloaded: %s", f.name)
                    return f
        except Exception as e:
            logger.error("Download failed: %s", e)
        return None

    def get_info(self, url: str) -> dict:
        """Get video metadata without downloading."""
        cmd = [
            "yt-dlp", "--dump-json", "--no-playlist",
            "--quiet", "--no-warnings", url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception as e:
            logger.debug("Info fetch failed: %s", e)
        return {}


class VideoAnalyzer:
    """
    Analyzes a downloaded video to extract its style profile.
    Uses ffprobe for metadata and scene detection.
    """

    def analyze(self, video_path: Path, source_url: str = "") -> VideoStyle:
        meta = self._get_metadata(video_path)
        scenes = self._detect_scenes(video_path)
        duration = meta.get("duration", 30.0)

        width = meta.get("width", 1080)
        height = meta.get("height", 1920)

        # Determine aspect ratio
        if height > width:
            aspect = "9:16"
        elif width > height:
            aspect = "16:9"
        else:
            aspect = "1:1"

        # Estimate tempo from scene count
        if len(scenes) > 0:
            avg_scene = duration / max(len(scenes), 1)
        else:
            avg_scene = duration / 5  # assume 5 scenes

        if avg_scene < 2.5:
            tempo = "fast"
        elif avg_scene < 5:
            tempo = "medium"
        else:
            tempo = "slow"

        return VideoStyle(
            duration=duration,
            hook_duration=min(scenes[0] if scenes else 3.0, 4.0),
            scene_count=max(len(scenes), 1),
            avg_scene_duration=avg_scene,
            has_text_overlay=True,  # assume most UGC has text
            text_positions=["top", "middle", "bottom"],
            aspect_ratio=aspect,
            width=width,
            height=height,
            has_music=True,
            tempo=tempo,
            source_url=source_url,
        )

    def _get_metadata(self, path: Path) -> dict:
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-print_format", "json",
                    "-show_format", "-show_streams",
                    str(path),
                ],
                capture_output=True, timeout=15,
            )
            data = json.loads(result.stdout)
            fmt = data.get("format", {})
            streams = data.get("streams", [])
            video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
            return {
                "duration": float(fmt.get("duration", 30)),
                "width": video_stream.get("width", 1080),
                "height": video_stream.get("height", 1920),
            }
        except Exception as e:
            logger.debug("Metadata error: %s", e)
            return {"duration": 30.0, "width": 1080, "height": 1920}

    def _detect_scenes(self, path: Path) -> list[float]:
        """Detect scene change timestamps using ffmpeg scene filter."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-show_frames",
                    "-of", "csv",
                    "-select_streams", "v",
                    "-show_entries", "frame=pkt_pts_time,tags",
                    "-vf", "select='gt(scene,0.35)',showinfo",
                    str(path),
                ],
                capture_output=True, timeout=60,
            )
            # Parse showinfo output for scene changes
            times = []
            for line in result.stderr.decode().splitlines():
                if "pts_time:" in line:
                    m = re.search(r"pts_time:([\d.]+)", line)
                    if m:
                        times.append(float(m.group(1)))
            return times[:20]  # max 20 scenes
        except Exception:
            return [3.0, 8.0, 15.0, 22.0]  # fallback scene times


class VideoCloner:
    """
    Clones the style of a viral video and recreates it with a new product.
    Pipeline:
      1. Download source video
      2. Analyze style (timing, pacing, aspect ratio)
      3. Fetch product images
      4. Generate script matching the viral hook style
      5. Create TTS voiceover
      6. Compose new video in the same style
    """

    def __init__(self, config: dict, output_dir: str = "output/clones"):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.downloader = VideoDownloader(str(self.output_dir / "sources"))
        self.analyzer = VideoAnalyzer()

    def clone(
        self,
        source_url: str,
        product,
        emit_fn=None,
    ) -> Optional[Path]:
        """
        Full clone pipeline. emit_fn(event, data) for progress updates.
        Returns path to the cloned video.
        """
        def log(msg: str):
            logger.info(msg)
            if emit_fn:
                emit_fn("log", {"msg": msg})

        log(f"Downloading source video: {source_url}")
        source_path = self.downloader.download(source_url)
        if not source_path:
            log("Download failed — check the URL and try again")
            return None

        log("Analyzing video style...")
        style = self.analyzer.analyze(source_path, source_url)
        log(
            f"Style: {style.aspect_ratio} · {style.duration:.0f}s · "
            f"{style.scene_count} scenes · {style.tempo} tempo"
        )

        log("Fetching product images...")
        from generators.image_fetcher import ImageFetcher
        fetcher = ImageFetcher(
            output_dir=str(Path(self.config.get("output", {}).get("images_dir", "output/images"))),
        )
        images = fetcher.fetch_product_images(product, count=style.scene_count + 2)
        if not images:
            log("No product images found — using product card")
            images = [fetcher._create_product_card(product, self.output_dir)]

        target_size = (style.width, style.height)
        prepared = fetcher.prepare_for_video(images, target_size=target_size)

        log("Generating UGC script...")
        from generators.tts_engine import ScriptGenerator, TTSEngine
        gen = self.config.get("generation", {})
        script_gen = ScriptGenerator()
        script = script_gen.generate(product)

        log("Generating voiceover...")
        tts = TTSEngine(
            engine=gen.get("tts_engine", "gtts"),
            speed=gen.get("tts_speed", 1.15),
        )
        audio_path = self.output_dir / f"clone_{product.asin or 'prod'}_audio.mp3"
        audio = tts.synthesize(script["full"], audio_path)

        log("Composing cloned video...")
        output_name = f"clone_{re.sub(r'[^\\w]', '_', product.title[:20])}_{source_url[-8:]}"
        output_path = self._compose_clone(
            images=prepared,
            audio_path=audio,
            style=style,
            script=script,
            product=product,
            output_name=output_name,
        )

        if output_path and output_path.exists():
            size_mb = output_path.stat().st_size / 1_048_576
            log(f"✓ Clone complete: {output_path.name} ({size_mb:.1f} MB)")
            return output_path

        log("Clone composition failed")
        return None

    def _compose_clone(
        self,
        images: list,
        audio_path: Optional[Path],
        style: VideoStyle,
        script: dict,
        product,
        output_name: str,
    ) -> Optional[Path]:
        """Compose the final video matching the source style."""
        from generators.video_composer import VideoComposer

        # Override config resolution to match source
        cfg = dict(self.config)
        cfg.setdefault("generation", {}).update({
            "video_duration_sec": int(style.duration),
        })

        # Use Ken Burns for fast/medium, static for slow
        composer = VideoComposer(cfg)
        composer.output_dir = self.output_dir

        if style.tempo in ("fast", "medium"):
            return composer.compose_zoom_pan_video(
                images=images,
                audio_path=audio_path,
                script=script,
                product=product,
                output_name=output_name,
            )
        else:
            return composer.compose_slideshow_video(
                images=images,
                audio_path=audio_path,
                script=script,
                product=product,
                output_name=output_name,
            )
