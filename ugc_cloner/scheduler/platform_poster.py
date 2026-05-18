"""
Platform Poster
Handles posting videos and images to TikTok, Instagram Reels, and YouTube Shorts.
All platforms use their official APIs where possible.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TikTokPoster:
    """
    Posts videos to TikTok using the TikTok Content Posting API v2.
    Requires: TikTok Developer account + approved app.
    Docs: https://developers.tiktok.com/doc/content-posting-api-get-started
    """

    UPLOAD_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def post_video(
        self,
        video_path: Path,
        caption: str,
        hashtags: list[str] = None,
        privacy: str = "PUBLIC_TO_EVERYONE",
    ) -> dict:
        import requests

        caption_with_tags = caption
        if hashtags:
            tags = " ".join(f"#{t.lstrip('#')}" for t in hashtags[:5])
            caption_with_tags = f"{caption}\n\n{tags}"

        video_size = video_path.stat().st_size

        # Step 1: Initialize upload
        init_payload = {
            "post_info": {
                "title": caption_with_tags[:2200],
                "privacy_level": privacy,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,
                "total_chunk_count": 1,
            },
        }
        resp = requests.post(self.UPLOAD_URL, json=init_payload, headers=self.headers)
        if resp.status_code != 200:
            logger.error("TikTok init failed: %s %s", resp.status_code, resp.text)
            return {"success": False, "error": resp.text}

        data = resp.json().get("data", {})
        publish_id = data.get("publish_id")
        upload_url = data.get("upload_url")

        if not upload_url:
            return {"success": False, "error": "No upload URL returned"}

        # Step 2: Upload video binary
        with open(video_path, "rb") as f:
            video_data = f.read()

        upload_headers = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
            "Content-Length": str(video_size),
        }
        upload_resp = requests.put(upload_url, data=video_data, headers=upload_headers)
        if upload_resp.status_code not in (200, 201):
            return {"success": False, "error": f"Upload failed: {upload_resp.status_code}"}

        # Step 3: Poll status
        for _ in range(10):
            time.sleep(5)
            status_payload = {"publish_id": publish_id}
            status_resp = requests.post(
                self.STATUS_URL, json=status_payload, headers=self.headers
            )
            if status_resp.status_code == 200:
                status_data = status_resp.json().get("data", {})
                if status_data.get("status") == "PUBLISH_COMPLETE":
                    logger.info("TikTok post published: %s", publish_id)
                    return {"success": True, "publish_id": publish_id}
                if status_data.get("status") in ("FAILED", "ERROR"):
                    return {"success": False, "error": status_data}

        return {"success": False, "error": "Timeout waiting for publish"}


class InstagramPoster:
    """
    Posts Reels and carousel posts to Instagram via the Instagram Graph API.
    Requires: Facebook App + Instagram Business Account.
    """

    GRAPH_URL = "https://graph.facebook.com/v19.0"

    def __init__(self, access_token: str, ig_user_id: str):
        self.token = access_token
        self.user_id = ig_user_id

    def post_reel(
        self,
        video_path: Path,
        caption: str,
        hashtags: list[str] = None,
        # Must be a public URL — upload to your CDN/S3 first
        video_url: str = "",
    ) -> dict:
        import requests

        caption_text = caption
        if hashtags:
            caption_text += "\n\n" + " ".join(f"#{h}" for h in hashtags[:30])

        # Step 1: Create media container
        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption_text,
            "access_token": self.token,
        }
        resp = requests.post(
            f"{self.GRAPH_URL}/{self.user_id}/media", params=params
        )
        if resp.status_code != 200:
            return {"success": False, "error": resp.text}

        creation_id = resp.json().get("id")

        # Step 2: Wait for processing
        for _ in range(20):
            time.sleep(10)
            check = requests.get(
                f"{self.GRAPH_URL}/{creation_id}",
                params={"fields": "status_code", "access_token": self.token},
            )
            if check.json().get("status_code") == "FINISHED":
                break

        # Step 3: Publish
        pub_resp = requests.post(
            f"{self.GRAPH_URL}/{self.user_id}/media_publish",
            params={"creation_id": creation_id, "access_token": self.token},
        )
        if pub_resp.status_code == 200:
            post_id = pub_resp.json().get("id")
            logger.info("Instagram Reel published: %s", post_id)
            return {"success": True, "post_id": post_id}
        return {"success": False, "error": pub_resp.text}

    def post_carousel(self, image_paths: list[Path], caption: str, image_urls: list[str] = None) -> dict:
        """Post carousel (multiple images) — requires public image URLs."""
        import requests
        if not image_urls:
            return {"success": False, "error": "Instagram carousel requires public image URLs"}

        item_ids = []
        for url in image_urls[:10]:
            resp = requests.post(
                f"{self.GRAPH_URL}/{self.user_id}/media",
                params={
                    "image_url": url,
                    "is_carousel_item": True,
                    "access_token": self.token,
                },
            )
            if resp.status_code == 200:
                item_ids.append(resp.json().get("id"))

        if not item_ids:
            return {"success": False, "error": "No carousel items created"}

        # Create carousel container
        resp = requests.post(
            f"{self.GRAPH_URL}/{self.user_id}/media",
            params={
                "media_type": "CAROUSEL",
                "children": ",".join(item_ids),
                "caption": caption,
                "access_token": self.token,
            },
        )
        if resp.status_code != 200:
            return {"success": False, "error": resp.text}

        creation_id = resp.json().get("id")
        pub_resp = requests.post(
            f"{self.GRAPH_URL}/{self.user_id}/media_publish",
            params={"creation_id": creation_id, "access_token": self.token},
        )
        return {"success": pub_resp.status_code == 200, "post_id": pub_resp.json().get("id")}


class YouTubePoster:
    """
    Posts Shorts to YouTube via the YouTube Data API v3.
    Requires: Google OAuth2 credentials.
    """

    def __init__(self, credentials_file: str):
        self.credentials_file = credentials_file
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service
        try:
            from googleapiclient.discovery import build
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            import pickle

            SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
            creds = None
            token_path = "config/youtube_token.pkl"

            if os.path.exists(token_path):
                with open(token_path, "rb") as f:
                    creds = pickle.load(f)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                with open(token_path, "wb") as f:
                    pickle.dump(creds, f)

            self._service = build("youtube", "v3", credentials=creds)
            return self._service
        except Exception as e:
            logger.error("YouTube auth failed: %s", e)
            return None

    def post_short(self, video_path: Path, title: str, description: str, tags: list[str] = None) -> dict:
        from googleapiclient.http import MediaFileUpload

        service = self._get_service()
        if not service:
            return {"success": False, "error": "YouTube auth not configured"}

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": (tags or [])[:500],
                "categoryId": "26",  # Howto & Style
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
        }

        try:
            media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
            request = service.videos().insert(part="snippet,status", body=body, media_body=media)
            response = None
            while response is None:
                _, response = request.next_chunk()
            video_id = response.get("id")
            logger.info("YouTube Short published: https://youtu.be/%s", video_id)
            return {"success": True, "video_id": video_id, "url": f"https://youtu.be/{video_id}"}
        except Exception as e:
            logger.error("YouTube upload failed: %s", e)
            return {"success": False, "error": str(e)}
