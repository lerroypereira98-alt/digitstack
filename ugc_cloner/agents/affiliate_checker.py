"""
Affiliate Offer Checker
Validates and ranks products by real affiliate commission potential.
Supports Amazon Associates commission tiers.
"""

import logging
import re
import time
import requests
from dataclasses import dataclass
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Amazon Associates commission rates by category (as of 2024)
AMAZON_COMMISSION_TABLE = {
    "Luxury Beauty": 10.0,
    "Amazon Games": 20.0,
    "Music": 5.0,
    "Physical Video Games": 1.0,
    "Amazon Coins": 5.0,
    "Digital Video Games": 2.0,
    "Books": 4.5,
    "Kitchen": 4.5,
    "Pet Supplies": 4.5,
    "Toys": 3.0,
    "Sports": 3.0,
    "Baby Products": 3.0,
    "Home": 3.0,
    "Electronics": 4.0,
    "Computer": 2.5,
    "Camera": 4.0,
    "Industrial": 4.5,
    "Fashion": 4.0,
    "Clothing": 4.0,
    "Shoes": 4.0,
    "Jewelry": 4.0,
    "Beauty": 3.0,
    "Health": 1.0,
    "Grocery": 1.0,
    "Outdoors": 3.0,
    "Tools": 3.0,
    "Office": 4.0,
    "Handmade": 5.0,
    "Default": 3.0,
}

# TikTok Shop commission ranges by category
TIKTOK_COMMISSION_TABLE = {
    "Beauty": 10.0,
    "Fashion": 8.0,
    "Electronics": 5.0,
    "Home": 7.0,
    "Health": 9.0,
    "Toys": 6.0,
    "Sports": 6.0,
    "Default": 5.0,
}


@dataclass
class AffiliateOffer:
    product_title: str
    asin: str
    category: str
    price: float
    commission_pct: float
    commission_usd: float
    platform: str
    affiliate_url: str
    estimated_monthly_earnings: float
    offer_quality: str   # "excellent" | "good" | "fair" | "skip"
    notes: str = ""


class AffiliateChecker:
    """
    Checks affiliate viability of a product.
    Computes estimated commission and quality tier.
    """

    def __init__(self, config: dict):
        self.min_commission_pct = config.get("amazon", {}).get("min_commission_pct", 3.0)
        self.partner_tag = config.get("amazon", {}).get("partner_tag", "")

    def get_amazon_commission(self, category: str) -> float:
        for key, rate in AMAZON_COMMISSION_TABLE.items():
            if key.lower() in category.lower():
                return rate
        return AMAZON_COMMISSION_TABLE["Default"]

    def get_tiktok_commission(self, category: str) -> float:
        for key, rate in TIKTOK_COMMISSION_TABLE.items():
            if key.lower() in category.lower():
                return rate
        return TIKTOK_COMMISSION_TABLE["Default"]

    def evaluate(self, product) -> AffiliateOffer:
        if product.source in ("amazon",):
            commission_pct = self.get_amazon_commission(product.category)
            platform = "amazon"
        else:
            commission_pct = self.get_tiktok_commission(product.category)
            platform = "tiktok_shop"

        commission_usd = round(product.price * commission_pct / 100, 2)

        # Estimate monthly earnings assuming 5 sales/day from the content
        estimated_monthly = round(commission_usd * 5 * 30, 2)

        # Quality tier
        if commission_pct >= 8.0 and product.price >= 20:
            quality = "excellent"
        elif commission_pct >= 4.0 and product.price >= 15:
            quality = "good"
        elif commission_pct >= 2.0:
            quality = "fair"
        else:
            quality = "skip"

        notes = []
        if product.rating >= 4.5:
            notes.append("high-rated")
        if product.review_count >= 1000:
            notes.append("popular")
        if "tiktok_trending" in product.tags:
            notes.append("tiktok-viral")
        if product.price < 10:
            notes.append("low-price-watch")

        return AffiliateOffer(
            product_title=product.title,
            asin=product.asin,
            category=product.category,
            price=product.price,
            commission_pct=commission_pct,
            commission_usd=commission_usd,
            platform=platform,
            affiliate_url=product.affiliate_url,
            estimated_monthly_earnings=estimated_monthly,
            offer_quality=quality,
            notes=", ".join(notes),
        )

    def filter_and_rank(self, products: list, min_quality: str = "fair") -> list:
        """
        Evaluate all products and return only those meeting quality threshold.
        Sorted by estimated monthly earnings descending.
        """
        quality_order = {"excellent": 3, "good": 2, "fair": 1, "skip": 0}
        threshold = quality_order.get(min_quality, 1)

        offers = []
        for product in products:
            try:
                offer = self.evaluate(product)
                if quality_order.get(offer.offer_quality, 0) >= threshold:
                    offers.append((product, offer))
            except Exception as e:
                logger.debug("Failed to evaluate %s: %s", product.title, e)

        offers.sort(key=lambda x: x[1].estimated_monthly_earnings, reverse=True)
        logger.info(
            "Affiliate check: %d/%d products passed quality threshold '%s'",
            len(offers),
            len(products),
            min_quality,
        )
        return offers

    def enrich_with_coupon(self, product) -> Optional[str]:
        """Check if Amazon product has a current coupon/discount badge."""
        url = f"https://www.amazon.com/dp/{product.asin}"
        try:
            resp = requests.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/124 Safari/537.36"
                    )
                },
                timeout=10,
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            coupon = soup.select_one("#couponText") or soup.select_one(
                ".a-color-price"
            )
            if coupon:
                text = coupon.get_text(strip=True)
                if "%" in text or "$" in text:
                    return text
        except Exception:
            pass
        return None
