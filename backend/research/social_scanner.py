"""
Social mention scanner for one-off research into 1-minute / 5-minute
prediction market discussion. Read-only, public endpoints only.

Reddit: public search.json endpoint — no auth required for read access.
YouTube: official Data API v3 search endpoint — requires an API key
(set the YOUTUBE_API_KEY env var). Skipped gracefully if no key is set.

Deliberately does NOT touch Twitter/X or Instagram: both require
authenticated access and their terms of service prohibit unauthenticated
scraping.
"""

import os
from typing import Dict, List

import requests

REQUEST_TIMEOUT = 10
REDDIT_HEADERS = {"User-Agent": "digitstack-research/1.0 (one-off market research script)"}


def search_reddit(query: str, limit: int = 15, sort: str = "new") -> List[Dict]:
    try:
        resp = requests.get(
            "https://www.reddit.com/search.json",
            params={"q": query, "limit": limit, "sort": sort},
            headers=REDDIT_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[social_scanner] Reddit search failed for {query!r}: {e}")
        return []

    posts = []
    for child in data.get("data", {}).get("children", []):
        p = child.get("data", {})
        posts.append({
            "source": "Reddit",
            "query": query,
            "subreddit": p.get("subreddit_name_prefixed"),
            "title": p.get("title"),
            "score": p.get("score"),
            "num_comments": p.get("num_comments"),
            "url": f"https://reddit.com{p.get('permalink', '')}",
            "created_utc": p.get("created_utc"),
        })
    return posts


def search_youtube(query: str, limit: int = 10) -> List[Dict]:
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        print("[social_scanner] YOUTUBE_API_KEY not set — skipping YouTube search")
        return []

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": "date",
                "maxResults": limit,
                "key": api_key,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[social_scanner] YouTube search failed for {query!r}: {e}")
        return []

    videos = []
    for item in data.get("items", []):
        snippet = item.get("snippet", {})
        video_id = item.get("id", {}).get("videoId")
        videos.append({
            "source": "YouTube",
            "query": query,
            "channel": snippet.get("channelTitle"),
            "title": snippet.get("title"),
            "published_at": snippet.get("publishedAt"),
            "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
        })
    return videos


def scan_social(queries: List[str]) -> Dict[str, List[Dict]]:
    reddit_results: List[Dict] = []
    youtube_results: List[Dict] = []
    for q in queries:
        reddit_results.extend(search_reddit(q))
        youtube_results.extend(search_youtube(q))
    return {"Reddit": reddit_results, "YouTube": youtube_results}
