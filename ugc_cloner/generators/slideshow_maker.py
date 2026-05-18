"""
Slideshow Maker
Creates static image slideshows (no audio) as an alternative to full videos.
Also used for Instagram carousel-style content.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random

logger = logging.getLogger(__name__)

OVERLAY_COLORS = [
    (255, 60, 100),    # Coral pink
    (60, 120, 255),    # Electric blue
    (255, 200, 0),     # Golden yellow
    (40, 220, 140),    # Mint green
    (200, 80, 255),    # Purple
]


class SlideshowMaker:
    """
    Creates image slideshows — either as a GIF, MP4 video without audio,
    or a series of styled PNG slides.
    """

    def __init__(self, config: dict):
        gen = config.get("generation", {})
        self.width = 1080
        self.height = 1920
        self.fps = gen.get("fps", 30)
        self.output_dir = Path(config.get("output", {}).get("slideshows_dir", "output/slideshows"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_product_slideshow(
        self,
        images: list[Path],
        script: dict,
        product,
        output_name: str,
        slides_per_image: int = 1,
    ) -> list[Path]:
        """
        Creates a set of styled slide images (PNG) ready to post as carousel.
        Returns list of slide paths.
        """
        slides = []
        accent = random.choice(OVERLAY_COLORS)

        # Slide 1: Hook slide
        hook_slide = self._make_text_slide(
            text=script.get("hook", ""),
            subtitle=f"#{product.category.lower().replace(' ', '')} #amazonfinds #ugc",
            accent=accent,
            output_path=self.output_dir / f"{output_name}_slide_hook.png",
        )
        if hook_slide:
            slides.append(hook_slide)

        # Slides 2+: Product image slides with price overlay
        for i, img_path in enumerate(images[:4]):
            slide = self._make_product_slide(
                image_path=img_path,
                title=product.title[:60],
                price=f"${product.price:.2f}" if product.price else "",
                rating=f"★ {product.rating} ({product.review_count:,} reviews)" if product.rating else "",
                accent=accent,
                output_path=self.output_dir / f"{output_name}_slide_{i+2}.png",
            )
            if slide:
                slides.append(slide)

        # Last slide: CTA
        cta_slide = self._make_cta_slide(
            cta_text=script.get("cta", "Link in bio!"),
            product_name=product.title[:40],
            accent=accent,
            output_path=self.output_dir / f"{output_name}_slide_cta.png",
        )
        if cta_slide:
            slides.append(cta_slide)

        logger.info("Created %d slides for %s", len(slides), output_name)
        return slides

    def create_video_slideshow(
        self,
        images: list[Path],
        script: dict,
        product,
        output_name: str,
        duration_sec: float = 25,
    ) -> Optional[Path]:
        """Creates a silent MP4 slideshow from images."""
        if not images:
            return None

        output_path = self.output_dir / f"{output_name}_slideshow.mp4"
        if output_path.exists():
            return output_path

        per_image = duration_sec / len(images)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            concat_file = tmpdir / "concat.txt"

            with open(concat_file, "w") as f:
                for img_path in images:
                    f.write(f"file '{img_path.resolve()}'\n")
                    f.write(f"duration {per_image:.3f}\n")
                f.write(f"file '{images[-1].resolve()}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_file),
                "-vf", (
                    f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                    f"crop={self.width}:{self.height},"
                    f"fps={self.fps},"
                    "format=yuv420p"
                ),
                "-c:v", "libx264",
                "-crf", "20",
                "-preset", "medium",
                str(output_path),
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and output_path.exists():
                return output_path
            logger.warning("Video slideshow failed for %s", output_name)
            return None

    def _load_font(self, size: int, bold: bool = False):
        paths_bold = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        paths_reg = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        paths = paths_bold if bold else paths_reg
        for p in paths:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def _make_text_slide(
        self,
        text: str,
        subtitle: str,
        accent: tuple,
        output_path: Path,
    ) -> Optional[Path]:
        if output_path.exists():
            return output_path
        try:
            img = Image.new("RGB", (self.width, self.height), (10, 10, 20))
            draw = ImageDraw.Draw(img)

            # Background gradient
            for y in range(self.height):
                t = y / self.height
                r = int(10 + t * accent[0] * 0.3)
                g = int(10 + t * accent[1] * 0.3)
                b = int(20 + t * accent[2] * 0.3)
                draw.line([(0, y), (self.width, y)], fill=(r, g, b))

            # Accent bar
            draw.rectangle([0, 0, self.width, 12], fill=accent)
            draw.rectangle([0, self.height - 12, self.width, self.height], fill=accent)

            font_xl = self._load_font(64, bold=True)
            font_sm = self._load_font(36)

            # Wrap and draw main text
            words = text.split()
            lines, current = [], ""
            for word in words:
                test = f"{current} {word}".strip()
                bbox = draw.textbbox((0, 0), test, font=font_xl)
                if bbox[2] > self.width - 100:
                    lines.append(current)
                    current = word
                else:
                    current = test
            if current:
                lines.append(current)

            y = (self.height - len(lines) * 85) // 2
            for line in lines[:6]:
                draw.text(
                    (self.width // 2, y),
                    line,
                    font=font_xl,
                    fill=(255, 255, 255),
                    anchor="mm",
                    stroke_width=3,
                    stroke_fill=(0, 0, 0),
                )
                y += 85

            draw.text(
                (self.width // 2, self.height - 160),
                subtitle,
                font=font_sm,
                fill=(*accent, 200),
                anchor="mm",
            )

            img.save(output_path, "PNG", optimize=True)
            return output_path
        except Exception as e:
            logger.warning("Text slide failed: %s", e)
            return None

    def _make_product_slide(
        self,
        image_path: Path,
        title: str,
        price: str,
        rating: str,
        accent: tuple,
        output_path: Path,
    ) -> Optional[Path]:
        if output_path.exists():
            return output_path
        try:
            # Load and resize product image
            product_img = Image.open(image_path).convert("RGBA")
            product_img = product_img.resize(
                (self.width, int(self.width * 1.1)), Image.LANCZOS
            )

            canvas = Image.new("RGB", (self.width, self.height), (10, 10, 20))

            # Paste product image in upper portion
            canvas.paste(product_img.convert("RGB"), (0, 100))

            # Dark gradient overlay at bottom
            overlay = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            ov_draw = ImageDraw.Draw(overlay)
            for y in range(self.height // 2, self.height):
                alpha = int(220 * ((y - self.height // 2) / (self.height // 2)))
                ov_draw.line([(0, y), (self.width, y)], fill=(10, 10, 20, alpha))
            canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

            draw = ImageDraw.Draw(canvas)
            font_title = self._load_font(50, bold=True)
            font_price = self._load_font(80, bold=True)
            font_rating = self._load_font(38)

            # Accent stripe
            draw.rectangle([0, 0, self.width, 10], fill=accent)

            # Title text
            words = title.split()
            lines, current = [], ""
            for word in words:
                test = f"{current} {word}".strip()
                bbox = draw.textbbox((0, 0), test, font=font_title)
                if bbox[2] > self.width - 80:
                    lines.append(current)
                    current = word
                else:
                    current = test
            if current:
                lines.append(current)

            y = self.height - 420
            for line in lines[:3]:
                draw.text(
                    (self.width // 2, y),
                    line,
                    font=font_title,
                    fill="white",
                    anchor="mm",
                    stroke_width=2,
                    stroke_fill="black",
                )
                y += 65

            if price:
                draw.text(
                    (self.width // 2, y + 20),
                    price,
                    font=font_price,
                    fill=tuple(accent),
                    anchor="mm",
                    stroke_width=3,
                    stroke_fill="black",
                )
                y += 100

            if rating:
                draw.text(
                    (self.width // 2, y + 30),
                    rating,
                    font=font_rating,
                    fill=(255, 220, 50),
                    anchor="mm",
                )

            canvas.save(output_path, "PNG", optimize=True)
            return output_path
        except Exception as e:
            logger.warning("Product slide failed: %s", e)
            return None

    def _make_cta_slide(
        self,
        cta_text: str,
        product_name: str,
        accent: tuple,
        output_path: Path,
    ) -> Optional[Path]:
        if output_path.exists():
            return output_path
        try:
            img = Image.new("RGB", (self.width, self.height), tuple(accent))
            draw = ImageDraw.Draw(img)

            # Contrasting pattern
            for y in range(0, self.height, 60):
                alpha = 30
                draw.line([(0, y), (self.width, y)], fill=(0, 0, 0))

            font_cta = self._load_font(72, bold=True)
            font_sub = self._load_font(44)
            font_tag = self._load_font(36)

            draw.text(
                (self.width // 2, self.height // 2 - 100),
                "👆 LINK IN BIO",
                font=font_cta,
                fill="white",
                anchor="mm",
                stroke_width=4,
                stroke_fill=(0, 0, 0),
            )
            draw.text(
                (self.width // 2, self.height // 2 + 20),
                cta_text,
                font=font_sub,
                fill="white",
                anchor="mm",
            )
            draw.text(
                (self.width // 2, self.height // 2 + 140),
                f"Tap for: {product_name[:30]}",
                font=font_tag,
                fill=(255, 255, 255, 200),
                anchor="mm",
            )

            img.save(output_path, "PNG", optimize=True)
            return output_path
        except Exception as e:
            logger.warning("CTA slide failed: %s", e)
            return None
