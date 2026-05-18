"""
Product Image Fetcher
Downloads high-resolution product images from Amazon and other sources.
Also handles AI image generation via local Stable Diffusion (optional).
"""

import io
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    )
}


class ImageFetcher:
    """Downloads and prepares product images for video composition."""

    def __init__(self, output_dir: str, use_stable_diffusion: bool = False, sd_url: str = ""):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_sd = use_stable_diffusion
        self.sd_url = sd_url
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def fetch_product_images(self, product, count: int = 6) -> list[Path]:
        """
        Downloads all available images for a product.
        Returns list of local file paths.
        """
        images = []
        asin = getattr(product, "asin", "")
        safe_title = re.sub(r"[^\w]", "_", product.title[:40])
        product_dir = self.output_dir / f"{asin or safe_title}"
        product_dir.mkdir(parents=True, exist_ok=True)

        # Primary image from scraped URL
        if product.image_url:
            img_path = self._download_image(
                product.image_url, product_dir / "main.jpg"
            )
            if img_path:
                images.append(img_path)

        # Amazon high-res images via ASIN pattern
        if asin:
            amazon_images = self._fetch_amazon_images(asin, product_dir, count)
            images.extend(amazon_images)

        # If we still don't have enough, generate with SD
        if self.use_sd and len(images) < 3:
            sd_images = self._generate_sd_images(product, product_dir, count - len(images))
            images.extend(sd_images)

        # Fallback: create placeholder cards
        if not images:
            placeholder = self._create_product_card(product, product_dir)
            if placeholder:
                images.append(placeholder)

        return images[:count]

    def _download_image(self, url: str, dest: Path) -> Optional[Path]:
        if dest.exists():
            return dest
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200 and len(resp.content) > 1000:
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                img.save(dest, "JPEG", quality=95)
                return dest
        except Exception as e:
            logger.debug("Image download failed %s: %s", url, e)
        return None

    def _fetch_amazon_images(self, asin: str, dest_dir: Path, count: int) -> list[Path]:
        """
        Amazon product images follow predictable URL patterns.
        Fetches multiple angles using variant URL suffixes.
        """
        images = []
        variants = ["", "_SL1500_", "_SX679_", "._AC_SL1500_"]
        base = f"https://ws-na.amazon-adsystem.com/widgets/q?_encoding=UTF8&ASIN={asin}&Format=_SL250_&ID=AsinImage&MarketPlace=US&ServiceVersion=20070822"

        # Alternate image URL patterns
        img_urls = [
            f"https://images-na.ssl-images-amazon.com/images/I/{asin}._AC_SL1500_.jpg",
        ]

        # Use the product page to find all image variants
        try:
            page_url = f"https://www.amazon.com/dp/{asin}"
            resp = self.session.get(page_url, timeout=10)
            if resp.status_code == 200:
                # Extract image URLs from page JSON data
                matches = re.findall(
                    r'"hiRes":"(https://[^"]+\.jpg)"', resp.text
                )
                img_urls.extend(matches[:count])
        except Exception as e:
            logger.debug("Amazon page fetch error for %s: %s", asin, e)

        for i, url in enumerate(img_urls[:count]):
            dest = dest_dir / f"img_{i}.jpg"
            path = self._download_image(url, dest)
            if path:
                images.append(path)
            time.sleep(0.5)

        return images

    def _generate_sd_images(self, product, dest_dir: Path, count: int) -> list[Path]:
        """Generate product lifestyle images using local Stable Diffusion API."""
        images = []
        prompt = (
            f"Professional product photography of {product.title}, "
            "white background, studio lighting, 8k, photorealistic, "
            "sharp focus, commercial product shot"
        )
        try:
            payload = {
                "prompt": prompt,
                "negative_prompt": "blurry, low quality, watermark, text",
                "steps": 25,
                "cfg_scale": 7,
                "width": 768,
                "height": 768,
                "n_iter": count,
                "sampler_name": "DPM++ 2M Karras",
            }
            resp = requests.post(
                f"{self.sd_url}/sdapi/v1/txt2img", json=payload, timeout=120
            )
            if resp.status_code == 200:
                import base64
                data = resp.json()
                for i, b64 in enumerate(data.get("images", [])):
                    img_data = base64.b64decode(b64)
                    dest = dest_dir / f"sd_{i}.jpg"
                    img = Image.open(io.BytesIO(img_data)).convert("RGB")
                    img.save(dest, "JPEG", quality=95)
                    images.append(dest)
        except Exception as e:
            logger.warning("Stable Diffusion generation failed: %s", e)
        return images

    def _create_product_card(self, product, dest_dir: Path) -> Optional[Path]:
        """Fallback: create a styled product info card image."""
        from PIL import ImageDraw, ImageFont
        try:
            width, height = 1080, 1080
            img = Image.new("RGB", (width, height), color=(15, 15, 25))
            draw = ImageDraw.Draw(img)

            # Gradient background
            for y in range(height):
                r = int(15 + (y / height) * 30)
                g = int(15 + (y / height) * 20)
                b = int(25 + (y / height) * 60)
                draw.line([(0, y), (width, y)], fill=(r, g, b))

            # Title text (wrapped)
            try:
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
                font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 38)
                font_price = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
            except Exception:
                font_large = ImageFont.load_default()
                font_medium = font_large
                font_price = font_large

            # Wrap title
            words = product.title.split()
            lines = []
            current = ""
            for word in words:
                test = f"{current} {word}".strip()
                bbox = draw.textbbox((0, 0), test, font=font_large)
                if bbox[2] > width - 80:
                    lines.append(current)
                    current = word
                else:
                    current = test
            if current:
                lines.append(current)

            y_start = 200
            for line in lines[:4]:
                draw.text((540, y_start), line, font=font_large, fill=(255, 255, 255), anchor="mm")
                y_start += 70

            # Price
            if product.price > 0:
                draw.text(
                    (540, y_start + 60),
                    f"${product.price:.2f}",
                    font=font_price,
                    fill=(255, 200, 50),
                    anchor="mm",
                )

            # Rating stars
            if product.rating > 0:
                stars = "★" * int(product.rating) + "☆" * (5 - int(product.rating))
                draw.text(
                    (540, y_start + 160),
                    f"{stars} ({product.review_count:,} reviews)",
                    font=font_medium,
                    fill=(255, 180, 0),
                    anchor="mm",
                )

            dest = dest_dir / "product_card.jpg"
            img.save(dest, "JPEG", quality=95)
            return dest
        except Exception as e:
            logger.warning("Product card creation failed: %s", e)
            return None

    def prepare_for_video(self, image_paths: list[Path], target_size: tuple = (1080, 1920)) -> list[Path]:
        """Resize and crop images to vertical video format (9:16)."""
        prepared = []
        for path in image_paths:
            try:
                out_path = path.parent / f"v_{path.name}"
                if out_path.exists():
                    prepared.append(out_path)
                    continue
                img = Image.open(path).convert("RGB")
                # Smart crop to fill 9:16 without distortion
                img_ratio = img.width / img.height
                target_ratio = target_size[0] / target_size[1]
                if img_ratio > target_ratio:
                    # Wider than target: crop sides
                    new_width = int(img.height * target_ratio)
                    left = (img.width - new_width) // 2
                    img = img.crop((left, 0, left + new_width, img.height))
                else:
                    # Taller than target: crop top/bottom
                    new_height = int(img.width / target_ratio)
                    top = (img.height - new_height) // 4  # Bias toward top
                    img = img.crop((0, top, img.width, top + new_height))
                img = img.resize(target_size, Image.LANCZOS)
                img.save(out_path, "JPEG", quality=92)
                prepared.append(out_path)
            except Exception as e:
                logger.debug("Image prep failed for %s: %s", path, e)
        return prepared


