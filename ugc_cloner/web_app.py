"""
UGC Cloner Web App
FastAPI backend with real-time progress via SSE.
Run: python web_app.py
Open: http://localhost:8080
"""

import asyncio
import json
import logging
import os
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="UGC Video Cloner", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global job state ──────────────────────────────────────────────────────────
jobs: dict[str, dict] = {}
sse_queues: dict[str, asyncio.Queue] = {}
CONFIG_PATH = Path(__file__).parent / "config" / "settings.yaml"
OUTPUT_DIR = Path(__file__).parent / "output"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)


def emit(job_id: str, event: str, data: dict):
    """Send SSE event to a job's queue."""
    if job_id in sse_queues:
        try:
            sse_queues[job_id].put_nowait({"event": event, "data": data})
        except Exception:
            pass


# ── Pydantic models ───────────────────────────────────────────────────────────

class DiscoverRequest(BaseModel):
    categories: list[str] = ["Beauty", "Health", "Kitchen", "Electronics"]
    pages_per_cat: int = 2
    limit: int = 60


class GenerateRequest(BaseModel):
    batch_size: int = 50
    video_split: float = 0.6
    tts_engine: str = "gtts"
    products: list[dict] = []   # Pre-selected products (from discover step)


class ScheduleRequest(BaseModel):
    posts_per_day: int = 4
    campaign_days: int = 60
    platforms: list[str] = ["tiktok"]
    dry_run: bool = False


class ConfigUpdate(BaseModel):
    partner_tag: str = ""
    tts_engine: str = "gtts"
    batch_size: int = 250
    min_commission_pct: float = 3.0
    posts_per_day: int = 4
    campaign_days: int = 60
    platforms: list[str] = ["tiktok"]
    tiktok_access_token: str = ""


# ── API Routes ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    index = Path(__file__).parent / "web" / "index.html"
    return HTMLResponse(index.read_text())


@app.get("/api/status")
async def status():
    cfg = load_config()
    stats = _get_output_stats()
    return {
        "configured": bool(cfg.get("amazon", {}).get("partner_tag", "")),
        "ffmpeg": _check_ffmpeg(),
        "stats": stats,
    }


@app.get("/api/config")
async def get_config():
    cfg = load_config()
    amazon = cfg.get("amazon", {})
    gen = cfg.get("generation", {})
    sched = cfg.get("scheduler", {})
    tiktok = cfg.get("tiktok", {})
    return {
        "partner_tag": amazon.get("partner_tag", ""),
        "min_commission_pct": amazon.get("min_commission_pct", 3.0),
        "tts_engine": gen.get("tts_engine", "gtts"),
        "batch_size": gen.get("batch_size", 250),
        "posts_per_day": sched.get("posts_per_day", 4),
        "campaign_days": sched.get("campaign_days", 60),
        "platforms": sched.get("platforms", ["tiktok"]),
        "tiktok_access_token": tiktok.get("access_token", ""),
    }


@app.post("/api/config")
async def update_config(body: ConfigUpdate):
    cfg = load_config()
    cfg.setdefault("amazon", {})["partner_tag"] = body.partner_tag
    cfg.setdefault("amazon", {})["min_commission_pct"] = body.min_commission_pct
    cfg.setdefault("generation", {})["tts_engine"] = body.tts_engine
    cfg.setdefault("generation", {})["batch_size"] = body.batch_size
    cfg.setdefault("scheduler", {})["posts_per_day"] = body.posts_per_day
    cfg.setdefault("scheduler", {})["campaign_days"] = body.campaign_days
    cfg.setdefault("scheduler", {})["platforms"] = body.platforms
    cfg.setdefault("tiktok", {})["access_token"] = body.tiktok_access_token
    save_config(cfg)
    return {"ok": True}


# ── DISCOVER ──────────────────────────────────────────────────────────────────

@app.post("/api/discover/start")
async def discover_start(body: DiscoverRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "running", "step": "discover", "started": datetime.utcnow().isoformat()}
    sse_queues[job_id] = asyncio.Queue()
    background_tasks.add_task(_run_discover, job_id, body)
    return {"job_id": job_id}


async def _run_discover(job_id: str, body: DiscoverRequest):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _discover_sync, job_id, body)


def _discover_sync(job_id: str, body: DiscoverRequest):
    try:
        cfg = load_config()
        cfg.setdefault("amazon", {})["categories"] = body.categories
        cfg.setdefault("amazon", {})["best_seller_pages"] = body.pages_per_cat

        emit(job_id, "log", {"msg": "Starting product discovery..."})

        from agents.viral_finder import ViralFinderAgent
        from agents.affiliate_checker import AffiliateChecker

        finder = ViralFinderAgent(cfg)
        checker = AffiliateChecker(cfg)

        emit(job_id, "log", {"msg": f"Scraping {len(body.categories)} categories..."})
        products = finder.discover(limit=body.limit)
        emit(job_id, "log", {"msg": f"Found {len(products)} products. Checking affiliate rates..."})

        qualified = checker.filter_and_rank(products, min_quality="fair")

        results = []
        for product, offer in qualified:
            results.append({
                "title": product.title,
                "asin": product.asin,
                "price": product.price,
                "rating": product.rating,
                "reviews": product.review_count,
                "category": product.category,
                "image_url": product.image_url,
                "affiliate_url": offer.affiliate_url,
                "commission_pct": offer.commission_pct,
                "commission_usd": offer.commission_usd,
                "quality": offer.offer_quality,
                "est_monthly": offer.estimated_monthly_earnings,
                "viral_score": product.viral_score,
                "tags": product.tags,
            })

        # Save results
        out = OUTPUT_DIR / "discovery_results.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, indent=2))

        jobs[job_id] = {"status": "done", "results": results}
        emit(job_id, "done", {"count": len(results), "results": results})
    except Exception as e:
        logger.exception("Discover failed")
        jobs[job_id] = {"status": "error", "error": str(e)}
        emit(job_id, "error", {"msg": str(e)})


@app.get("/api/discover/results")
async def discover_results():
    path = OUTPUT_DIR / "discovery_results.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


# ── GENERATE ──────────────────────────────────────────────────────────────────

@app.post("/api/generate/start")
async def generate_start(body: GenerateRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "running", "step": "generate", "started": datetime.utcnow().isoformat(), "progress": 0}
    sse_queues[job_id] = asyncio.Queue()
    background_tasks.add_task(_run_generate, job_id, body)
    return {"job_id": job_id}


async def _run_generate(job_id: str, body: GenerateRequest):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _generate_sync, job_id, body)


def _generate_sync(job_id: str, body: GenerateRequest):
    try:
        cfg = load_config()
        cfg.setdefault("generation", {})["batch_size"] = body.batch_size
        cfg.setdefault("generation", {})["video_split"] = body.video_split
        cfg.setdefault("generation", {})["tts_engine"] = body.tts_engine

        # Load pre-selected products or use saved results
        if body.products:
            products_data = body.products
        else:
            path = OUTPUT_DIR / "discovery_results.json"
            if path.exists():
                products_data = json.loads(path.read_text())
            else:
                emit(job_id, "error", {"msg": "No products found. Run discovery first."})
                return

        from agents.viral_finder import Product
        from agents.affiliate_checker import AffiliateChecker, AffiliateOffer
        from generators.image_fetcher import ImageFetcher
        from generators.tts_engine import TTSEngine, ScriptGenerator
        from generators.video_composer import VideoComposer
        from generators.slideshow_maker import SlideshowMaker
        import uuid as _uuid, re

        checker = AffiliateChecker(cfg)
        fetcher = ImageFetcher(
            output_dir=str(OUTPUT_DIR / "images"),
            use_stable_diffusion=cfg.get("generation", {}).get("use_stable_diffusion", False),
        )
        tts = TTSEngine(
            engine=body.tts_engine,
            speed=cfg.get("generation", {}).get("tts_speed", 1.15),
        )
        script_gen = ScriptGenerator()
        composer = VideoComposer(cfg)
        slideshow = SlideshowMaker(cfg)

        target_videos = int(body.batch_size * body.video_split)
        target_slides = body.batch_size - target_videos
        videos_made = 0
        slides_made = 0
        content_items = []
        total = min(len(products_data), body.batch_size)

        emit(job_id, "log", {"msg": f"Generating {body.batch_size} pieces of content from {len(products_data)} products..."})

        for i, pdata in enumerate(products_data):
            if videos_made >= target_videos and slides_made >= target_slides:
                break

            product = Product(
                title=pdata.get("title", ""),
                asin=pdata.get("asin", ""),
                price=pdata.get("price", 0.0),
                rating=pdata.get("rating", 0.0),
                review_count=pdata.get("reviews", 0),
                category=pdata.get("category", ""),
                image_url=pdata.get("image_url", ""),
                product_url=pdata.get("affiliate_url", ""),
                affiliate_url=pdata.get("affiliate_url", ""),
                viral_score=pdata.get("viral_score", 0.0),
                tags=pdata.get("tags", []),
            )

            pct = int((i / max(total, 1)) * 100)
            emit(job_id, "progress", {
                "pct": pct,
                "msg": f"Processing: {product.title[:40]}",
                "videos": videos_made,
                "slides": slides_made,
            })

            images = fetcher.fetch_product_images(product, count=5)
            if not images:
                emit(job_id, "log", {"msg": f"Skipping {product.title[:30]} — no images"})
                continue

            prepared = fetcher.prepare_for_video(images, target_size=(1080, 1920))
            script = script_gen.generate(product)
            safe = re.sub(r"[^\w]", "_", product.title[:25]).strip("_") + "_" + _uuid.uuid4().hex[:6]

            # TTS
            audio_path = OUTPUT_DIR / "audio" / f"{safe}.mp3"
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            audio = tts.synthesize(script["full"], audio_path)

            make_video = videos_made < target_videos

            if make_video:
                video_path = composer.compose_zoom_pan_video(
                    images=prepared,
                    audio_path=audio,
                    script=script,
                    product=product,
                    output_name=safe,
                )
                if video_path:
                    videos_made += 1
                    content_items.append({
                        "type": "video",
                        "file": str(video_path),
                        "name": safe,
                        "product_title": product.title,
                        "caption": script["hook"] + " " + script["cta"],
                        "affiliate_url": product.affiliate_url,
                        "created_at": datetime.utcnow().isoformat(),
                    })
            else:
                slides = slideshow.create_product_slideshow(
                    images=prepared,
                    script=script,
                    product=product,
                    output_name=safe,
                )
                if slides:
                    slides_made += 1
                    content_items.append({
                        "type": "slideshow",
                        "files": [str(s) for s in slides],
                        "name": safe,
                        "product_title": product.title,
                        "caption": script["hook"] + " " + script["cta"],
                        "affiliate_url": product.affiliate_url,
                        "created_at": datetime.utcnow().isoformat(),
                    })

        # Save library
        lib = OUTPUT_DIR / "library.json"
        existing = json.loads(lib.read_text()) if lib.exists() else []
        existing.extend(content_items)
        lib.write_text(json.dumps(existing, indent=2))

        jobs[job_id] = {"status": "done", "videos": videos_made, "slides": slides_made}
        emit(job_id, "done", {
            "videos": videos_made,
            "slides": slides_made,
            "total": videos_made + slides_made,
        })
    except Exception as e:
        logger.exception("Generate failed")
        jobs[job_id] = {"status": "error", "error": str(e)}
        emit(job_id, "error", {"msg": str(e)})


# ── LIBRARY ───────────────────────────────────────────────────────────────────

@app.get("/api/library")
async def get_library():
    lib = OUTPUT_DIR / "library.json"
    if lib.exists():
        return json.loads(lib.read_text())
    return []


@app.get("/api/library/videos")
async def list_videos():
    videos_dir = OUTPUT_DIR / "videos"
    if not videos_dir.exists():
        return []
    items = []
    for f in sorted(videos_dir.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
        items.append({
            "name": f.name,
            "size_mb": round(f.stat().st_size / 1_048_576, 1),
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            "url": f"/output/videos/{f.name}",
        })
    return items


@app.get("/api/library/slides")
async def list_slides():
    slides_dir = OUTPUT_DIR / "slideshows"
    if not slides_dir.exists():
        return []
    items = []
    for f in sorted(slides_dir.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True):
        items.append({
            "name": f.name,
            "size_mb": round(f.stat().st_size / 1_048_576, 1),
            "url": f"/output/slideshows/{f.name}",
        })
    return items


# ── SCHEDULE ──────────────────────────────────────────────────────────────────

@app.get("/api/schedule")
async def get_schedule():
    from scheduler.post_scheduler import PostQueue
    q = PostQueue()
    return {"stats": q.stats(), "pending": q.get_pending()[:50]}


@app.post("/api/schedule/build")
async def build_schedule(body: ScheduleRequest):
    from scheduler.post_scheduler import CampaignScheduler
    cfg = load_config()
    cfg.setdefault("scheduler", {}).update({
        "posts_per_day": body.posts_per_day,
        "campaign_days": body.campaign_days,
        "platforms": body.platforms,
    })
    lib = OUTPUT_DIR / "library.json"
    content = json.loads(lib.read_text()) if lib.exists() else []
    if not content:
        raise HTTPException(400, "No content in library. Generate videos first.")
    sched = CampaignScheduler(cfg)
    count = sched.schedule_batch(content)
    return {"scheduled": count}


@app.post("/api/schedule/run")
async def run_schedule(background_tasks: BackgroundTasks, dry_run: bool = True):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "running", "step": "schedule"}
    sse_queues[job_id] = asyncio.Queue()
    background_tasks.add_task(_run_schedule_async, job_id, dry_run)
    return {"job_id": job_id}


async def _run_schedule_async(job_id: str, dry_run: bool):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_schedule_sync, job_id, dry_run)


def _run_schedule_sync(job_id: str, dry_run: bool):
    try:
        emit(job_id, "log", {"msg": "Running scheduler..."})
        from scheduler.post_scheduler import CampaignScheduler
        cfg = load_config()
        sched = CampaignScheduler(cfg)
        sched.run_scheduler(lambda p, post: {"success": True, "dry_run": True}, dry_run=True)
        stats = sched.queue.stats()
        jobs[job_id] = {"status": "done"}
        emit(job_id, "done", stats)
    except Exception as e:
        emit(job_id, "error", {"msg": str(e)})


# ── SSE stream ────────────────────────────────────────────────────────────────

@app.get("/api/jobs/{job_id}/stream")
async def job_stream(job_id: str):
    if job_id not in sse_queues:
        sse_queues[job_id] = asyncio.Queue()

    async def event_generator():
        q = sse_queues[job_id]
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=30)
                yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
                if msg["event"] in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield "event: ping\ndata: {}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    return jobs.get(job_id, {"status": "not_found"})


# ── Static file serving ───────────────────────────────────────────────────────

def _check_ffmpeg() -> bool:
    import subprocess
    try:
        return subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3).returncode == 0
    except Exception:
        return False


def _get_output_stats() -> dict:
    return {
        "videos": len(list((OUTPUT_DIR / "videos").glob("*.mp4"))) if (OUTPUT_DIR / "videos").exists() else 0,
        "slideshows": len(list((OUTPUT_DIR / "slideshows").glob("*.png"))) if (OUTPUT_DIR / "slideshows").exists() else 0,
        "audio": len(list((OUTPUT_DIR / "audio").glob("*.mp3"))) if (OUTPUT_DIR / "audio").exists() else 0,
    }


# Mount output folder so videos/images are accessible
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "videos").mkdir(exist_ok=True)
(OUTPUT_DIR / "slideshows").mkdir(exist_ok=True)

app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "web" / "static")), name="static")

if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 50)
    print("  UGC Video Cloner Web App")
    print("  Open: http://localhost:8080")
    print("=" * 50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=False)
