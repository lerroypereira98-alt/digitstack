"""
Video Composer
Creates high-quality UGC-style videos (minimum 720p, target 1080p vertical).
Uses FFmpeg directly for maximum quality and zero cost.

Output: 1080x1920 (9:16) vertical video at 30fps, H.264, CRF 18 (near-lossless)
"""

import logging
import os
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Optional
import random
import shutil

logger = logging.getLogger(__name__)

# Video quality presets
QUALITY_PRESETS = {
    "1080p": {"width": 1080, "height": 1920, "crf": 18, "preset": "slow"},
    "720p":  {"width":  720, "height": 1280, "crf": 20, "preset": "medium"},
    "480p":  {"width":  480, "height":  854, "crf": 23, "preset": "fast"},
}

TEXT_ANIMATION_STYLES = [
    "fade_in",
    "slide_up",
    "pop",
    "typewriter",
]


def _check_ffmpeg() -> bool:
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def _ffmpeg(args: list, timeout: int = 120) -> bool:
    cmd = ["ffmpeg", "-y"] + args
    logger.debug("ffmpeg: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if result.returncode != 0:
        logger.warning("ffmpeg error: %s", result.stderr.decode()[-500:])
    return result.returncode == 0


class VideoComposer:
    """
    Composes full UGC videos from product images + audio + text overlays.
    All processing is local — no API calls, no credits.
    """

    def __init__(self, config: dict):
        gen = config.get("generation", {})
        quality_name = "1080p"
        self.quality = QUALITY_PRESETS[quality_name]
        self.width = self.quality["width"]
        self.height = self.quality["height"]
        self.fps = gen.get("fps", 30)
        self.target_duration = gen.get("video_duration_sec", 30)
        self.output_dir = Path(config.get("output", {}).get("videos_dir", "output/videos"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.has_ffmpeg = _check_ffmpeg()
        if not self.has_ffmpeg:
            logger.error("FFmpeg not found. Please install: sudo apt install ffmpeg")

    def compose_slideshow_video(
        self,
        images: list[Path],
        audio_path: Optional[Path],
        script: dict,
        product,
        output_name: str,
        style: str = "dynamic",
    ) -> Optional[Path]:
        """
        Creates a full UGC video from images + voiceover + text overlays.
        Returns path to the final MP4 file.
        """
        if not self.has_ffmpeg:
            return None
        if not images:
            logger.warning("No images for video: %s", output_name)
            return None

        output_path = self.output_dir / f"{output_name}.mp4"
        if output_path.exists():
            return output_path

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # 1. Determine timing
            audio_duration = self._get_audio_duration(audio_path) if audio_path else self.target_duration
            duration = max(audio_duration, 10)
            per_image = duration / len(images)

            # 2. Build input file list for concat
            concat_file = tmpdir / "concat.txt"
            prepared_images = self._prepare_images(images, tmpdir)

            with open(concat_file, "w") as f:
                for img_path in prepared_images:
                    f.write(f"file '{img_path}'\n")
                    f.write(f"duration {per_image:.3f}\n")
                # FFmpeg concat needs last file repeated
                if prepared_images:
                    f.write(f"file '{prepared_images[-1]}'\n")

            # 3. Create raw slideshow video
            raw_video = tmpdir / "raw.mp4"
            ok = _ffmpeg([
                "-f", "concat", "-safe", "0", "-i", str(concat_file),
                "-vf", (
                    f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                    f"crop={self.width}:{self.height},"
                    f"fps={self.fps},"
                    "format=yuv420p"
                ),
                "-c:v", "libx264",
                "-crf", str(self.quality["crf"]),
                "-preset", self.quality["preset"],
                str(raw_video),
            ])
            if not ok or not raw_video.exists():
                logger.warning("Raw video creation failed for %s", output_name)
                return None

            # 4. Add text overlays (title + price + CTA)
            with_text = tmpdir / "with_text.mp4"
            text_filters = self._build_text_filters(script, product, duration)
            ok = _ffmpeg([
                "-i", str(raw_video),
                "-vf", text_filters,
                "-c:v", "libx264",
                "-crf", str(self.quality["crf"]),
                "-preset", self.quality["preset"],
                "-c:a", "copy",
                str(with_text),
            ])
            video_for_audio = with_text if (ok and with_text.exists()) else raw_video

            # 5. Mix in audio
            if audio_path and audio_path.exists():
                ok = _ffmpeg([
                    "-i", str(video_for_audio),
                    "-i", str(audio_path),
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    str(output_path),
                ], timeout=180)
            else:
                shutil.copy2(video_for_audio, output_path)

            if output_path.exists():
                size_mb = output_path.stat().st_size / 1_048_576
                logger.info("Video created: %s (%.1f MB)", output_path.name, size_mb)
                return output_path

        return None

    def compose_zoom_pan_video(
        self,
        images: list[Path],
        audio_path: Optional[Path],
        script: dict,
        product,
        output_name: str,
    ) -> Optional[Path]:
        """
        Creates video with Ken Burns (zoom+pan) effect on each image.
        More dynamic than static slideshow.
        """
        if not self.has_ffmpeg or not images:
            return None

        output_path = self.output_dir / f"{output_name}_kenbурns.mp4"
        if output_path.exists():
            return output_path

        audio_duration = self._get_audio_duration(audio_path) if audio_path else self.target_duration
        duration = max(audio_duration, 10)
        per_image = duration / len(images)
        frames_per_img = int(per_image * self.fps)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            prepared = self._prepare_images(images, tmpdir)

            # Build complex filtergraph for zoom/pan
            filter_parts = []
            inputs = []
            for i, img_path in enumerate(prepared):
                inputs += ["-loop", "1", "-t", f"{per_image:.3f}", "-i", str(img_path)]
                zoom_dir = random.choice(["in", "out"])
                pan_dir = random.choice(["left", "right", "none"])
                z_filter = self._ken_burns_filter(i, frames_per_img, zoom_dir, pan_dir)
                filter_parts.append(z_filter)

            # Concat all clips
            concat = "".join(f"[v{i}]" for i in range(len(prepared)))
            filter_parts.append(f"{concat}concat=n={len(prepared)}:v=1:a=0[vout]")
            filtergraph = ";".join(filter_parts)

            raw_video = tmpdir / "kb_raw.mp4"
            ok = _ffmpeg(
                inputs + [
                    "-filter_complex", filtergraph,
                    "-map", "[vout]",
                    "-c:v", "libx264",
                    "-crf", str(self.quality["crf"]),
                    "-preset", self.quality["preset"],
                    "-pix_fmt", "yuv420p",
                    str(raw_video),
                ],
                timeout=300,
            )

            if not ok or not raw_video.exists():
                # Fallback to simple slideshow
                return self.compose_slideshow_video(images, audio_path, script, product, output_name)

            # Add text + audio
            with_text = tmpdir / "kb_text.mp4"
            text_filters = self._build_text_filters(script, product, duration)
            _ffmpeg([
                "-i", str(raw_video),
                "-vf", text_filters,
                "-c:v", "libx264", "-crf", str(self.quality["crf"]),
                "-preset", self.quality["preset"],
                str(with_text),
            ])
            video_src = with_text if with_text.exists() else raw_video

            if audio_path and audio_path.exists():
                _ffmpeg([
                    "-i", str(video_src),
                    "-i", str(audio_path),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-map", "0:v:0", "-map", "1:a:0",
                    str(output_path),
                ], timeout=180)
            else:
                shutil.copy2(video_src, output_path)

            if output_path.exists():
                size_mb = output_path.stat().st_size / 1_048_576
                logger.info("Ken Burns video: %s (%.1f MB)", output_path.name, size_mb)
                return output_path

        return None

    def _ken_burns_filter(self, idx: int, frames: int, zoom: str, pan: str) -> str:
        """Generates FFmpeg zoompan filter for one image clip."""
        W, H = self.width, self.height
        d = frames
        # Zoom in: 1.0 → 1.15, zoom out: 1.15 → 1.0
        if zoom == "in":
            z_expr = f"zoom+0.0005"
            z_init = "1"
        else:
            z_expr = "if(eq(on\\,1)\\,1.15\\,zoom-0.0005)"
            z_init = "1.15"

        if pan == "left":
            x_expr = "x+1"
        elif pan == "right":
            x_expr = "if(eq(on\\,1)\\,iw/2\\,x-1)"
        else:
            x_expr = "iw/2-(iw/zoom/2)"

        return (
            f"[{idx}:v]scale={W*2}:{H*2},"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={W}x{H}:fps={self.fps}[v{idx}]"
        )

    def _prepare_images(self, images: list[Path], tmpdir: Path) -> list[Path]:
        """Ensure all images are correct size and format for ffmpeg."""
        prepared = []
        for i, img_path in enumerate(images):
            out = tmpdir / f"prep_{i}.jpg"
            ok = _ffmpeg([
                "-i", str(img_path),
                "-vf", (
                    f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                    f"crop={self.width}:{self.height},"
                    "format=yuvj420p"
                ),
                str(out),
            ])
            if ok and out.exists():
                prepared.append(out)
            else:
                prepared.append(img_path)
        return prepared

    def _build_text_filters(self, script: dict, product, duration: float) -> str:
        """Build FFmpeg drawtext filter chain for overlays."""
        safe = lambda s: (
            s.replace("'", "").replace(":", "\\:").replace(",", "\\,")
             .replace("[", "").replace("]", "")[:60]
        )

        filters = []
        W, H = self.width, self.height

        # Font path — try system fonts
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "C\\:/Windows/Fonts/arialbd.ttf",
        ]
        font = next((f for f in font_paths if os.path.exists(f)), "")
        font_arg = f":fontfile='{font}'" if font else ""

        # Hook text — top of screen, appears at 0.5s, fades out at 4s
        hook_text = safe(script.get("hook", "")[:80])
        if hook_text:
            filters.append(
                f"drawtext=text='{hook_text}'{font_arg}"
                f":fontsize=48:fontcolor=white:bordercolor=black:borderw=3"
                f":x=(w-text_w)/2:y=80"
                f":enable='between(t,0.5,5)'"
                f":alpha='if(lt(t,1),t-0.5,if(gt(t,4),5-t,1))'"
            )

        # Product title — middle, visible from 3s to 15s
        title = safe(script.get("title_overlay", product.title)[:50])
        if title:
            # Wrap long titles
            words = title.split()
            line1 = " ".join(words[:5])
            line2 = " ".join(words[5:10]) if len(words) > 5 else ""
            filters.append(
                f"drawtext=text='{line1}'{font_arg}"
                f":fontsize=52:fontcolor=white:bordercolor=black:borderw=4"
                f":x=(w-text_w)/2:y=(h/2)-60"
                f":enable='between(t,3,{min(duration-5, 15)})'"
            )
            if line2:
                filters.append(
                    f"drawtext=text='{line2}'{font_arg}"
                    f":fontsize=52:fontcolor=white:bordercolor=black:borderw=4"
                    f":x=(w-text_w)/2:y=(h/2)+10"
                    f":enable='between(t,3,{min(duration-5, 15)})'"
                )

        # Price — prominent, yellow
        price = safe(script.get("price_overlay", ""))
        if price:
            filters.append(
                f"drawtext=text='{price}'{font_arg}"
                f":fontsize=80:fontcolor=yellow:bordercolor=black:borderw=5"
                f":x=(w-text_w)/2:y=(h/2)+120"
                f":enable='between(t,5,{min(duration-3, 18)})'"
            )

        # CTA — bottom, last 8 seconds
        cta_start = max(duration - 9, duration * 0.7)
        cta = safe(script.get("cta", "Link in bio!")[:50])
        if cta:
            filters.append(
                f"drawtext=text='{cta}'{font_arg}"
                f":fontsize=44:fontcolor=white:bordercolor=black:borderw=3"
                f":box=1:boxcolor=black@0.6:boxborderw=8"
                f":x=(w-text_w)/2:y={H - 120}"
                f":enable='between(t,{cta_start:.1f},{duration})'"
            )

        return ",".join(filters) if filters else "null"

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration in seconds using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(audio_path),
                ],
                capture_output=True,
                timeout=10,
            )
            return float(result.stdout.decode().strip())
        except Exception:
            return self.target_duration
