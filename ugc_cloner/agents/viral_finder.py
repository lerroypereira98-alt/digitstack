"""
Viral Product Finder Agent
Discovers trending products from Amazon Best Sellers and TikTok Creative Center.
"""

import re
import time
import logging
import random
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, quote_plus

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class Product:
    title: str
    asin: str = ""
    price: float = 0.0
    rating: float = 0.0
    review_count: int = 0
    category: str = ""
    image_url: str = ""
    product_url: str = ""
    affiliate_url: str = ""
    commission_pct: float = 0.0
    viral_score: float = 0.0
    source: str = "amazon"
    tags: list = field(default_factory=list)


class AmazonBestSellerScraper:
    """Scrapes Amazon Best Sellers pages without requiring PA-API credentials."""

    BASE_URL = "https://www.amazon.com"
    BEST_SELLERS_URL = "https://www.amazon.com/Best-Sellers/zgbs"

    # Categories with generally higher affiliate commissions
    CATEGORY_URLS = {
        "Beauty": "/zgbs/beauty",
        "Health": "/zgbs/hpc",
        "Kitchen": "/zgbs/kitchen",
        "Electronics": "/zgbs/electronics",
        "Toys": "/zgbs/toys-and-games",
        "Sports": "/zgbs/sporting-goods",
        "Pet Supplies": "/zgbs/pet-supplies",
        "Baby": "/zgbs/baby-products",
        "Home": "/zgbs/home-garden",
        "Office": "/zgbs/office-products",
    }

    def __init__(self, partner_tag: str = "", min_reviews: int = 50):
        self.partner_tag = partner_tag
        self.min_reviews = min_reviews
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _get(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        for attempt in range(retries):
            try:
                time.sleep(random.uniform(2, 5))
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 200:
                    return BeautifulSoup(resp.text, "html.parser")
                logger.warning("HTTP %s for %s", resp.status_code, url)
            except Exception as e:
                logger.warning("Attempt %d failed for %s: %s", attempt + 1, url, e)
                time.sleep(2 ** attempt)
        return None

    def _build_affiliate_url(self, asin: str) -> str:
        base = f"https://www.amazon.com/dp/{asin}"
        if self.partner_tag:
            return f"{base}?tag={self.partner_tag}"
        return base

    def _parse_price(self, text: str) -> float:
        try:
            return float(re.sub(r"[^\d.]", "", text.split("–")[0]))
        except Exception:
            return 0.0

    def _parse_reviews(self, text: str) -> int:
        try:
            clean = re.sub(r"[^\d]", "", text)
            return int(clean) if clean else 0
        except Exception:
            return 0

    def scrape_category(self, category: str, pages: int = 2) -> list[Product]:
        products = []
        path = self.CATEGORY_URLS.get(category, "")
        if not path:
            logger.warning("Unknown category: %s", category)
            return products

        for page in range(1, pages + 1):
            url = f"{self.BASE_URL}{path}?pg={page}"
            logger.info("Scraping Amazon Best Sellers: %s page %d", category, page)
            soup = self._get(url)
            if not soup:
                continue

            items = soup.select("div[id^='p13n-asin-index']") or soup.select(
                ".zg-grid-general-faceout"
            )
            if not items:
                # Fallback selector
                items = soup.select("li.zg-item-immersion") or soup.select(
                    "div.p13n-desktop-grid"
                )

            for item in items:
                try:
                    product = self._parse_item(item, category)
                    if product and product.review_count >= self.min_reviews:
                        products.append(product)
                except Exception as e:
                    logger.debug("Failed to parse item: %s", e)

        logger.info("Found %d products in %s", len(products), category)
        return products

    def _parse_item(self, item, category: str) -> Optional[Product]:
        # Title
        title_el = (
            item.select_one(".p13n-sc-truncated")
            or item.select_one("._cDEzb_p13n-sc-css-line-clamp-3_g3dy1")
            or item.select_one("span.a-size-small")
            or item.select_one("div.a-section span")
        )
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None

        # ASIN from link
        link_el = item.select_one("a.a-link-normal[href*='/dp/']")
        asin = ""
        product_url = ""
        if link_el:
            href = link_el.get("href", "")
            m = re.search(r"/dp/([A-Z0-9]{10})", href)
            asin = m.group(1) if m else ""
            product_url = urljoin(self.BASE_URL, href.split("?")[0])

        if not asin:
            return None

        # Price
        price_el = item.select_one(".p13n-sc-price") or item.select_one(
            "span.a-price span.a-offscreen"
        )
        price = self._parse_price(price_el.get_text()) if price_el else 0.0

        # Rating
        rating_el = item.select_one("span.a-icon-alt") or item.select_one(
            "i.a-icon-star"
        )
        rating = 0.0
        if rating_el:
            m = re.search(r"([\d.]+)", rating_el.get_text())
            rating = float(m.group(1)) if m else 0.0

        # Reviews
        review_el = item.select_one("span.a-size-small") or item.select_one(
            "a[href*='customerReviews']"
        )
        review_count = self._parse_reviews(review_el.get_text()) if review_el else 0

        # Image
        img_el = item.select_one("img")
        image_url = img_el.get("src", "") if img_el else ""
        if image_url.startswith("data:"):
            image_url = img_el.get("data-src", "") if img_el else ""

        # Viral score: weighted combo of rating, reviews, price sweet spot
        viral_score = self._compute_viral_score(rating, review_count, price)

        return Product(
            title=title,
            asin=asin,
            price=price,
            rating=rating,
            review_count=review_count,
            category=category,
            image_url=image_url,
            product_url=product_url,
            affiliate_url=self._build_affiliate_url(asin),
            viral_score=viral_score,
            source="amazon",
        )

    def _compute_viral_score(
        self, rating: float, reviews: int, price: float
    ) -> float:
        """Higher score = better viral + affiliate potential."""
        score = 0.0
        # Rating weight (max 4.8 is sweet spot — too perfect looks fake)
        score += min(rating / 5.0, 0.96) * 30
        # Review count — log scale so 10k reviews >> 100 but not 100x
        import math
        score += min(math.log10(max(reviews, 1)) / 5.0, 1.0) * 40
        # Price sweet spot: $15–$60 impulse-buy range
        if 10 <= price <= 60:
            score += 30
        elif 60 < price <= 120:
            score += 15
        elif price < 10:
            score += 10
        return round(score, 2)

    def scrape_all(self, categories: list[str], pages_per_cat: int = 2) -> list[Product]:
        all_products = []
        for cat in categories:
            products = self.scrape_category(cat, pages_per_cat)
            all_products.extend(products)
        # Deduplicate by ASIN
        seen = set()
        unique = []
        for p in all_products:
            if p.asin not in seen:
                seen.add(p.asin)
                unique.append(p)
        return sorted(unique, key=lambda p: p.viral_score, reverse=True)


class TikTokTrendingScraper:
    """
    Scrapes TikTok Creative Center for trending products and hashtags.
    Uses public endpoints — no authentication required for discovery.
    """

    CC_BASE = "https://ads.tiktok.com/business/creativecenter"
    TRENDING_URL = (
        "https://ads.tiktok.com/business/creativecenter/hashtag/pc/en"
    )

    def __init__(self, viral_hashtags: list[str] = None, min_views: int = 100_000):
        self.viral_hashtags = viral_hashtags or [
            "tiktokmademebuyit",
            "amazonfinds",
            "productreview",
        ]
        self.min_views = min_views
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get_trending_products_via_hashtags(self) -> list[dict]:
        """
        Returns product mentions found via trending hashtag searches.
        Uses TikTok's internal Creative Center API.
        """
        results = []
        for tag in self.viral_hashtags:
            items = self._search_hashtag_videos(tag)
            results.extend(items)
            time.sleep(random.uniform(3, 7))
        return results

    def _search_hashtag_videos(self, hashtag: str) -> list[dict]:
        """Query TikTok Creative Center trending API (public endpoint)."""
        url = (
            "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"
            f"?period=7&country_code=US&hashtag_name={quote_plus(hashtag)}"
            "&page_size=20&page=1"
        )
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                logger.debug("TikTok CC API returned %s", resp.status_code)
                return []
            data = resp.json().get("data", {})
            items = data.get("list", [])
            products = []
            for item in items:
                view_count = item.get("video_views", 0)
                if view_count < self.min_views:
                    continue
                products.append(
                    {
                        "title": item.get("hashtag_name", hashtag),
                        "views": view_count,
                        "source": "tiktok",
                        "hashtag": hashtag,
                        "viral_score": min(view_count / 1_000_000 * 100, 100),
                    }
                )
            return products
        except Exception as e:
            logger.debug("TikTok hashtag API error for %s: %s", hashtag, e)
            return []

    def get_trending_products_from_tiktok_shop(self) -> list[dict]:
        """
        Scrape TikTok Shop top sellers via the public product search API.
        Returns a list of product dicts.
        """
        url = (
            "https://shop.tiktok.com/view/api/products/search?"
            "count=30&cursor=0&locale=en&region=US&sort_type=3"
        )
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return []
            data = resp.json()
            products = []
            for item in data.get("data", {}).get("products", []):
                price = float(item.get("price", {}).get("original_price", 0)) / 100
                products.append(
                    {
                        "title": item.get("title", ""),
                        "price": price,
                        "image_url": item.get("cover_image_urls", [""])[0],
                        "product_url": f"https://www.tiktok.com/t/{item.get('id', '')}",
                        "sales": item.get("sales_30d", 0),
                        "source": "tiktok_shop",
                        "viral_score": min(item.get("sales_30d", 0) / 1000 * 10, 100),
                    }
                )
            return products
        except Exception as e:
            logger.debug("TikTok Shop API error: %s", e)
            return []


class ViralFinderAgent:
    """
    Orchestrates product discovery across Amazon and TikTok.
    Returns ranked list of products with affiliate potential.
    """

    def __init__(self, config: dict):
        self.config = config
        amazon_cfg = config.get("amazon", {})
        tiktok_cfg = config.get("tiktok", {})

        self.amazon_scraper = AmazonBestSellerScraper(
            partner_tag=amazon_cfg.get("partner_tag", ""),
            min_reviews=50,
        )
        self.tiktok_scraper = TikTokTrendingScraper(
            viral_hashtags=tiktok_cfg.get(
                "viral_hashtags", ["tiktokmademebuyit", "amazonfinds"]
            ),
            min_views=tiktok_cfg.get("min_views_viral", 100_000),
        )

    def discover(self, limit: int = 50) -> list[Product]:
        logger.info("Starting viral product discovery...")
        all_products: list[Product] = []

        # Amazon Best Sellers
        categories = self.config.get("amazon", {}).get("categories", ["Beauty", "Health"])
        pages = self.config.get("amazon", {}).get("best_seller_pages", 2)
        amazon_products = self.amazon_scraper.scrape_all(categories, pages)
        logger.info("Amazon discovered: %d products", len(amazon_products))
        all_products.extend(amazon_products)

        # TikTok trending boost — annotate Amazon products that are trending on TT
        tiktok_data = self.tiktok_scraper.get_trending_products_via_hashtags()
        tiktok_titles = {t["title"].lower() for t in tiktok_data}

        for product in all_products:
            words = set(product.title.lower().split())
            if any(w in product.title.lower() for w in tiktok_titles):
                product.viral_score = min(product.viral_score * 1.3, 100)
                product.tags.append("tiktok_trending")

        # TikTok Shop products as additional source
        tt_shop = self.tiktok_scraper.get_trending_products_from_tiktok_shop()
        for item in tt_shop:
            if item.get("title"):
                p = Product(
                    title=item["title"],
                    price=item.get("price", 0.0),
                    image_url=item.get("image_url", ""),
                    product_url=item.get("product_url", ""),
                    affiliate_url=item.get("product_url", ""),
                    viral_score=item.get("viral_score", 0.0),
                    source="tiktok_shop",
                    tags=["tiktok_shop"],
                )
                all_products.append(p)

        # Sort by viral score and return top N
        all_products.sort(key=lambda p: p.viral_score, reverse=True)
        top = all_products[:limit]
        logger.info("Top %d products selected after viral ranking", len(top))
        return top
