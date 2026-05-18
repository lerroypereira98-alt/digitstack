"""
Post Scheduler
Schedules generated content for posting across platforms.
Uses APScheduler for time-based job scheduling.
Distributes 200-300 videos over a configurable campaign window.
"""

import json
import logging
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import pytz

logger = logging.getLogger(__name__)

QUEUE_FILE = "output/post_queue.json"


class PostQueue:
    """Persistent queue of scheduled posts."""

    def __init__(self, queue_file: str = QUEUE_FILE):
        self.path = Path(queue_file)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> list:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except Exception:
                pass
        return []

    def save(self):
        self.path.write_text(json.dumps(self._data, indent=2, default=str))

    def add(self, post: dict):
        self._data.append(post)
        self.save()

    def get_pending(self) -> list:
        return [p for p in self._data if p.get("status") == "pending"]

    def get_due(self, now: datetime = None) -> list:
        now = now or datetime.utcnow()
        return [
            p for p in self._data
            if p.get("status") == "pending"
            and datetime.fromisoformat(p["scheduled_at"]) <= now
        ]

    def mark_posted(self, post_id: str, result: dict):
        for post in self._data:
            if post.get("id") == post_id:
                post["status"] = "posted"
                post["posted_at"] = datetime.utcnow().isoformat()
                post["result"] = result
        self.save()

    def mark_failed(self, post_id: str, error: str):
        for post in self._data:
            if post.get("id") == post_id:
                post["status"] = "failed"
                post["error"] = error
                post["retries"] = post.get("retries", 0) + 1
        self.save()

    def stats(self) -> dict:
        statuses = [p.get("status", "unknown") for p in self._data]
        return {
            "total": len(self._data),
            "pending": statuses.count("pending"),
            "posted": statuses.count("posted"),
            "failed": statuses.count("failed"),
        }


class CampaignScheduler:
    """
    Plans and schedules a batch of posts across platforms and days.
    Distributes evenly to avoid spam detection.
    """

    def __init__(self, config: dict):
        sched_cfg = config.get("scheduler", {})
        self.platforms = sched_cfg.get("platforms", ["tiktok"])
        self.posts_per_day = sched_cfg.get("posts_per_day", 4)
        self.posting_times = sched_cfg.get("posting_times", ["09:00", "13:00", "18:00", "21:00"])
        self.timezone = pytz.timezone(sched_cfg.get("timezone", "America/New_York"))
        self.campaign_days = sched_cfg.get("campaign_days", 60)
        self.queue = PostQueue()

    def schedule_batch(self, content_items: list[dict], start_date: datetime = None) -> int:
        """
        Takes a list of content items (videos/slideshows) and schedules them.
        Returns number of posts scheduled.
        """
        start = start_date or datetime.now(self.timezone)
        scheduled_count = 0
        post_slots = self._generate_slots(start)

        for i, item in enumerate(content_items):
            if i >= len(post_slots):
                logger.warning("Ran out of post slots — increase campaign_days or posts_per_day")
                break

            for j, platform in enumerate(self.platforms):
                slot_idx = i * len(self.platforms) + j
                if slot_idx >= len(post_slots):
                    break
                slot = post_slots[slot_idx]

                post = {
                    "id": f"post_{i}_{platform}_{slot.strftime('%Y%m%d%H%M')}",
                    "platform": platform,
                    "scheduled_at": slot.astimezone(pytz.utc).isoformat(),
                    "local_time": slot.strftime("%Y-%m-%d %H:%M %Z"),
                    "status": "pending",
                    "content": {
                        "video_path": item.get("video_path", ""),
                        "slides": item.get("slides", []),
                        "caption": item.get("caption", ""),
                        "hashtags": item.get("hashtags", []),
                        "product_title": item.get("product_title", ""),
                        "affiliate_url": item.get("affiliate_url", ""),
                    },
                    "created_at": datetime.utcnow().isoformat(),
                }
                self.queue.add(post)
                scheduled_count += 1

        logger.info(
            "Scheduled %d posts across %d days (%d platforms)",
            scheduled_count,
            self.campaign_days,
            len(self.platforms),
        )
        return scheduled_count

    def _generate_slots(self, start: datetime) -> list[datetime]:
        """Generate all available posting time slots for the campaign window."""
        slots = []
        for day_offset in range(self.campaign_days):
            day = start + timedelta(days=day_offset)
            random.shuffle(self.posting_times)  # Vary order slightly each day
            for time_str in self.posting_times[:self.posts_per_day]:
                h, m = map(int, time_str.split(":"))
                # Add random jitter ±15 min to appear more human
                jitter = random.randint(-15, 15)
                slot = day.replace(hour=h, minute=m, second=0, microsecond=0)
                slot += timedelta(minutes=jitter)
                slots.append(slot)
        return slots

    def run_scheduler(self, poster_factory, dry_run: bool = False):
        """
        Runs the scheduler loop. Checks for due posts and publishes them.
        Call this in a cron job or background thread.
        """
        from .platform_poster import TikTokPoster, InstagramPoster, YouTubePoster

        config = {}  # Passed via factory
        due_posts = self.queue.get_due()

        if not due_posts:
            logger.info("No posts due at this time.")
            return

        logger.info("Processing %d due posts...", len(due_posts))

        for post in due_posts:
            platform = post["platform"]
            content = post["content"]

            if dry_run:
                logger.info("[DRY RUN] Would post to %s: %s", platform, content.get("product_title"))
                self.queue.mark_posted(post["id"], {"dry_run": True})
                continue

            try:
                result = poster_factory(platform, post)
                if result.get("success"):
                    self.queue.mark_posted(post["id"], result)
                    logger.info("Posted to %s: %s", platform, post["id"])
                else:
                    self.queue.mark_failed(post["id"], str(result.get("error")))
            except Exception as e:
                self.queue.mark_failed(post["id"], str(e))
                logger.error("Failed to post %s: %s", post["id"], e)

        stats = self.queue.stats()
        logger.info("Queue stats: %s", stats)

    def print_schedule(self, limit: int = 20):
        """Print upcoming scheduled posts."""
        pending = sorted(
            self.queue.get_pending(),
            key=lambda p: p["scheduled_at"]
        )[:limit]
        print(f"\n{'='*60}")
        print(f"Upcoming posts ({len(self.queue.get_pending())} pending):")
        print(f"{'='*60}")
        for p in pending:
            print(
                f"  [{p['platform']:12}] {p['local_time']}  |  "
                f"{p['content'].get('product_title', '')[:35]}"
            )
        stats = self.queue.stats()
        print(f"\nTotal: {stats['total']} | Posted: {stats['posted']} | Failed: {stats['failed']}")
        print(f"{'='*60}\n")
