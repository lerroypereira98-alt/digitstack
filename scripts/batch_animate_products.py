#!/usr/bin/env python3
"""
Batch generate AnimateDiff videos from product images.

Usage:
    python batch_animate_products.py --products products.json --style cinematic
    python batch_animate_products.py --dir product_images/ --limit 5

Output:
    Videos saved to: output/videos/animated_*.mp4
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional, List

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ugc_cloner.generators.animatediff_generator import (
    AnimateDiffGenerator,
    AnimationStyle,
    ProductImageAnimator,
)


def get_animation_style(style_name: str) -> AnimationStyle:
    """Get animation style preset."""
    styles = {
        "cinematic": AnimationStyle(
            motion_scale=1.5,
            num_frames=24,
            steps=25,
            guidance_scale=8.0,
        ),
        "professional": AnimationStyle(
            motion_scale=0.8,
            num_frames=16,
            steps=20,
            guidance_scale=7.5,
        ),
        "dynamic": AnimationStyle(
            motion_scale=2.0,
            num_frames=32,
            steps=30,
            guidance_scale=9.0,
        ),
        "fast": AnimationStyle(
            motion_scale=1.0,
            num_frames=12,
            steps=15,
            guidance_scale=7.0,
        ),
    }
    return styles.get(style_name, styles["professional"])


def find_product_images(directory: Path) -> List[Path]:
    """Find all product images in directory."""
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    images = []
    for ext in extensions:
        images.extend(directory.glob(f"*{ext}"))
        images.extend(directory.glob(f"*{ext.upper()}"))
    return sorted(set(images))


def batch_from_directory(
    directory: str,
    style: str = "professional",
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> None:
    """Generate videos from all images in directory."""
    product_dir = Path(directory)
    if not product_dir.exists():
        print(f"❌ Directory not found: {product_dir}")
        return

    images = find_product_images(product_dir)
    if not images:
        print(f"❌ No images found in {product_dir}")
        return

    if limit:
        images = images[:limit]

    print(f"\n📂 Found {len(images)} product images")
    print(f"🎨 Animation style: {style}")
    print(f"📁 Output: output/videos/")

    if dry_run:
        print(f"\n[DRY RUN] Would generate:")
        for img in images:
            print(f"  • {img.name}")
        return

    animation_style = get_animation_style(style)
    gen = AnimateDiffGenerator(output_dir="output/videos")

    if not gen.available:
        print("❌ ComfyUI not running! Start: cd ~/ComfyUI && python main.py")
        return

    completed = 0
    failed = 0

    for i, image_path in enumerate(images, 1):
        product_title = image_path.stem  # Filename without extension
        output_name = f"animated_{product_title[:30]}"

        print(f"\n[{i}/{len(images)}] Generating: {product_title}...")

        def emit(event: str, data: dict):
            if event in ("progress", "log"):
                msg = data.get("msg", "")
                if msg:
                    print(f"  {msg}")

        video_path = gen.generate(
            image_path=image_path,
            product_title=product_title,
            output_name=output_name,
            style=animation_style,
            emit_fn=emit,
        )

        if video_path and video_path.exists():
            size_mb = video_path.stat().st_size / 1024 / 1024
            print(f"  ✅ Success! ({size_mb:.1f} MB)")
            completed += 1
        else:
            print(f"  ❌ Failed")
            failed += 1

    print(f"\n{'='*50}")
    print(f"✅ Completed: {completed}/{len(images)}")
    if failed:
        print(f"❌ Failed: {failed}/{len(images)}")
    print(f"📁 Videos: output/videos/animated_*.mp4")


def batch_from_json(
    json_file: str,
    style: str = "professional",
    dry_run: bool = False,
) -> None:
    """Generate videos from JSON product list."""
    config_path = Path(json_file)
    if not config_path.exists():
        print(f"❌ File not found: {config_path}")
        return

    with open(config_path) as f:
        products = json.load(f)

    if not isinstance(products, list):
        print("❌ JSON must be a list of product objects")
        return

    print(f"\n📋 Loaded {len(products)} products from {json_file}")
    print(f"🎨 Animation style: {style}")
    print(f"📁 Output: output/videos/")

    required_fields = ["title", "image_path"]
    for product in products:
        missing = [f for f in required_fields if f not in product]
        if missing:
            print(f"❌ Product missing fields: {missing}")
            print(f"   Required: title, image_path")
            return

    if dry_run:
        print(f"\n[DRY RUN] Would generate:")
        for product in products:
            print(f"  • {product['title']} ({product['image_path']})")
        return

    animation_style = get_animation_style(style)
    gen = AnimateDiffGenerator(output_dir="output/videos")

    if not gen.available:
        print("❌ ComfyUI not running! Start: cd ~/ComfyUI && python main.py")
        return

    completed = 0
    failed = 0

    for i, product in enumerate(products, 1):
        title = product["title"]
        image_path = Path(product["image_path"])

        if not image_path.exists():
            print(f"\n[{i}/{len(products)}] ⚠️  Image not found: {image_path}")
            failed += 1
            continue

        output_name = f"animated_{title[:30]}"
        print(f"\n[{i}/{len(products)}] Generating: {title}...")

        def emit(event: str, data: dict):
            if event in ("progress", "log"):
                msg = data.get("msg", "")
                if msg:
                    print(f"  {msg}")

        video_path = gen.generate(
            image_path=image_path,
            product_title=title,
            output_name=output_name,
            style=animation_style,
            emit_fn=emit,
        )

        if video_path and video_path.exists():
            size_mb = video_path.stat().st_size / 1024 / 1024
            print(f"  ✅ Success! ({size_mb:.1f} MB)")
            completed += 1
        else:
            print(f"  ❌ Failed")
            failed += 1

    print(f"\n{'='*50}")
    print(f"✅ Completed: {completed}/{len(products)}")
    if failed:
        print(f"❌ Failed: {failed}/{len(products)}")
    print(f"📁 Videos: output/videos/animated_*.mp4")


def create_sample_products_json() -> None:
    """Create example products.json."""
    example = [
        {
            "title": "Vitamin C Serum",
            "image_path": "product_images/serum.jpg",
            "category": "Beauty",
        },
        {
            "title": "Probiotic Capsules",
            "image_path": "product_images/probiotics.jpg",
            "category": "Health",
        },
        {
            "title": "Wireless Earbuds",
            "image_path": "product_images/earbuds.jpg",
            "category": "Tech",
        },
    ]

    output_path = Path("products.json")
    with open(output_path, "w") as f:
        json.dump(example, f, indent=2)

    print(f"✅ Created: {output_path}")
    print(f"   Edit and add your products, then run:")
    print(f"   python scripts/batch_animate_products.py --products products.json")


def main():
    parser = argparse.ArgumentParser(
        description="Batch generate AnimateDiff videos from products"
    )
    parser.add_argument(
        "--dir",
        type=str,
        help="Generate from all images in directory",
    )
    parser.add_argument(
        "--products",
        type=str,
        help="Generate from products.json list",
    )
    parser.add_argument(
        "--style",
        type=str,
        default="professional",
        choices=["cinematic", "professional", "dynamic", "fast"],
        help="Animation style (default: professional)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of videos (useful for testing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without doing it",
    )
    parser.add_argument(
        "--create-sample",
        action="store_true",
        help="Create example products.json",
    )

    args = parser.parse_args()

    if args.create_sample:
        create_sample_products_json()
        return

    if not args.dir and not args.products:
        parser.print_help()
        print("\n📝 Examples:")
        print("  # Generate from directory:")
        print("  python scripts/batch_animate_products.py --dir product_images/")
        print("")
        print("  # Generate first 5 with cinematic style:")
        print("  python scripts/batch_animate_products.py --dir product_images/ --limit 5 --style cinematic")
        print("")
        print("  # Generate from products.json:")
        print("  python scripts/batch_animate_products.py --products products.json --style dynamic")
        print("")
        print("  # Preview without generating:")
        print("  python scripts/batch_animate_products.py --products products.json --dry-run")
        return

    if args.dir:
        batch_from_directory(
            args.dir,
            style=args.style,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    elif args.products:
        batch_from_json(
            args.products,
            style=args.style,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
