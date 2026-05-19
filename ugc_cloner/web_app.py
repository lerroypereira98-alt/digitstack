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
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="UGC Video Cloner", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Global state ──────────────────────────────────────────────────────────────
jobs: dict[str, dict] = {}
# job_id → list of {event, data} dicts (thread-safe via list.append)
job_events: dict[str, list] = {}
# job_id → asyncio.Event to wake the SSE stream
job_signals: dict[str, asyncio.Event] = {}

CONFIG_PATH = Path(__file__).parent / "config" / "settings.yaml"
OUTPUT_DIR = Path(__file__).parent / "output"
WEB_DIR = Path(__file__).parent / "web"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)


def _emit(job_id: str, event: str, data: dict):
    """Thread-safe: append event and signal the SSE coroutine."""
    if job_id not in job_events:
        job_events[job_id] = []
    job_events[job_id].append({"event": event, "data": data})
    # Wake up SSE stream — safe from any thread
    sig = job_signals.get(job_id)
    if sig and not sig.is_set():
        sig.set()


# ── Pydantic models ───────────────────────────────────────────────────────────

class DiscoverRequest(BaseModel):
    categories: list[str] = ["Beauty", "Health", "Kitchen", "Electronics"]
    pages_per_cat: int = 2
    limit: int = 60


class GenerateRequest(BaseModel):
    batch_size: int = 50
    video_split: float = 0.6
    tts_engine: str = "gtts"


class ScheduleRequest(BaseModel):
    posts_per_day: int = 4
    campaign_days: int = 60
    platforms: list[str] = ["tiktok"]
    dry_run: bool = False


class ConfigUpdate(BaseModel):
    partner_tag: str = ""
    min_commission_pct: float = 3.0
    tts_engine: str = "gtts"
    batch_size: int = 250
    posts_per_day: int = 4
    campaign_days: int = 60
    platforms: list[str] = ["tiktok"]
    tiktok_access_token: str = ""


class CloneRequest(BaseModel):
    source_url: str
    product_title: str = "Amazing Product"
    product_asin: str = ""
    product_price: float = 29.99
    product_category: str = "Beauty"
    affiliate_tag: str = ""


class LTXGenerateRequest(BaseModel):
    product_title: str
    category: str = "Beauty"
    hook: str = ""
    cta: str = ""
    duration: int = 15


class AnimateDiffRequest(BaseModel):
    product_title: str
    image_path: str = ""  # Path relative to output/images/
    motion_scale: float = 1.0
    num_frames: int = 16


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse((WEB_DIR / "index.html").read_text())


# ── API: status + config ──────────────────────────────────────────────────────

@app.get("/api/status")
async def status():
    cfg = load_config()
    return {
        "configured": bool(cfg.get("amazon", {}).get("partner_tag", "")),
        "ffmpeg": _check_ffmpeg(),
        "stats": _get_output_stats(),
    }


@app.get("/api/config")
async def get_config():
    cfg = load_config()
    return {
        "partner_tag": cfg.get("amazon", {}).get("partner_tag", ""),
        "min_commission_pct": cfg.get("amazon", {}).get("min_commission_pct", 3.0),
        "tts_engine": cfg.get("generation", {}).get("tts_engine", "gtts"),
        "batch_size": cfg.get("generation", {}).get("batch_size", 250),
        "posts_per_day": cfg.get("scheduler", {}).get("posts_per_day", 4),
        "campaign_days": cfg.get("scheduler", {}).get("campaign_days", 60),
        "platforms": cfg.get("scheduler", {}).get("platforms", ["tiktok"]),
        "tiktok_access_token": cfg.get("tiktok", {}).get("access_token", ""),
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


# ── API: discover ─────────────────────────────────────────────────────────────

@app.post("/api/discover/start")
async def discover_start(body: DiscoverRequest, background_tasks: BackgroundTasks):
    job_id = _new_job("discover")
    background_tasks.add_task(_run_in_thread, job_id, _discover_sync, body)
    return {"job_id": job_id}


def _discover_sync(job_id: str, body: DiscoverRequest):
    try:
        cfg = load_config()
        cfg.setdefault("amazon", {})["categories"] = body.categories
        cfg.setdefault("amazon", {})["best_seller_pages"] = body.pages_per_cat

        _emit(job_id, "log", {"msg": "Starting product discovery..."})

        from agents.viral_finder import ViralFinderAgent
        from agents.affiliate_checker import AffiliateChecker

        finder = ViralFinderAgent(cfg)
        checker = AffiliateChecker(cfg)

        _emit(job_id, "log", {"msg": f"Scraping {len(body.categories)} categories on Amazon Best Sellers..."})
        products = finder.discover(limit=body.limit)
        _emit(job_id, "log", {"msg": f"Found {len(products)} products. Checking affiliate commission rates..."})

        qualified = checker.filter_and_rank(products, min_quality="fair")
        _emit(job_id, "log", {"msg": f"{len(qualified)} products passed affiliate filter."})

        results = [
            {
                "title": p.title, "asin": p.asin, "price": p.price,
                "rating": p.rating, "reviews": p.review_count,
                "category": p.category, "image_url": p.image_url,
                "affiliate_url": o.affiliate_url,
                "commission_pct": o.commission_pct,
                "commission_usd": o.commission_usd,
                "quality": o.offer_quality,
                "est_monthly": o.estimated_monthly_earnings,
                "viral_score": p.viral_score, "tags": p.tags,
            }
            for p, o in qualified
        ]

        out = OUTPUT_DIR / "discovery_results.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, indent=2))

        jobs[job_id]["status"] = "done"
        _emit(job_id, "done", {"count": len(results), "results": results})
    except Exception as e:
        logger.exception("Discover failed")
        jobs[job_id]["status"] = "error"
        _emit(job_id, "error", {"msg": str(e)})


@app.get("/api/discover/results")
async def discover_results():
    path = OUTPUT_DIR / "discovery_results.json"
    return json.loads(path.read_text()) if path.exists() else []


# ── API: generate ─────────────────────────────────────────────────────────────

@app.post("/api/generate/start")
async def generate_start(body: GenerateRequest, background_tasks: BackgroundTasks):
    job_id = _new_job("generate")
    background_tasks.add_task(_run_in_thread, job_id, _generate_sync, body)
    return {"job_id": job_id}


def _generate_sync(job_id: str, body: GenerateRequest):
    try:
        cfg = load_config()
        cfg.setdefault("generation", {})["batch_size"] = body.batch_size
        cfg.setdefault("generation", {})["video_split"] = body.video_split
        cfg.setdefault("generation", {})["tts_engine"] = body.tts_engine

        path = OUTPUT_DIR / "discovery_results.json"
        if not path.exists():
            _emit(job_id, "error", {"msg": "No products found. Run discovery first."})
            return

        products_data = json.loads(path.read_text())
        if not products_data:
            _emit(job_id, "error", {"msg": "Discovery results are empty. Run discovery first."})
            return

        from agents.viral_finder import Product
        from generators.image_fetcher import ImageFetcher
        from generators.tts_engine import TTSEngine, ScriptGenerator
        from generators.video_composer import VideoComposer
        from generators.slideshow_maker import SlideshowMaker
        import uuid as _uuid, re

        fetcher = ImageFetcher(
            output_dir=str(OUTPUT_DIR / "images"),
            use_stable_diffusion=cfg.get("generation", {}).get("use_stable_diffusion", False),
        )
        tts = TTSEngine(engine=body.tts_engine, speed=cfg.get("generation", {}).get("tts_speed", 1.15))
        script_gen = ScriptGenerator()
        composer = VideoComposer(cfg)
        slideshow = SlideshowMaker(cfg)

        target_videos = int(body.batch_size * body.video_split)
        target_slides = body.batch_size - target_videos
        videos_made = slides_made = 0
        content_items = []

        _emit(job_id, "log", {"msg": f"Starting: {body.batch_size} pieces from {len(products_data)} products"})
        _emit(job_id, "log", {"msg": f"Target: {target_videos} videos + {target_slides} slideshows"})

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

            pct = int((i / max(len(products_data), 1)) * 100)
            _emit(job_id, "progress", {
                "pct": pct, "msg": f"Processing: {product.title[:45]}",
                "videos": videos_made, "slides": slides_made,
            })

            images = fetcher.fetch_product_images(product, count=5)
            if not images:
                _emit(job_id, "log", {"msg": f"No images for '{product.title[:30]}' — skipping"})
                continue

            prepared = fetcher.prepare_for_video(images, target_size=(1080, 1920))
            script = script_gen.generate(product)
            safe = re.sub(r"[^\w]", "_", product.title[:25]).strip("_") + "_" + _uuid.uuid4().hex[:6]

            audio_path = OUTPUT_DIR / "audio" / f"{safe}.mp3"
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            audio = tts.synthesize(script["full"], audio_path)

            if videos_made < target_videos:
                video_path = composer.compose_zoom_pan_video(
                    images=prepared, audio_path=audio,
                    script=script, product=product, output_name=safe,
                )
                if video_path:
                    videos_made += 1
                    _emit(job_id, "log", {"msg": f"✓ Video {videos_made}: {product.title[:40]}"})
                    content_items.append({
                        "type": "video", "file": str(video_path), "name": safe,
                        "product_title": product.title,
                        "caption": script["hook"] + " " + script["cta"],
                        "affiliate_url": product.affiliate_url,
                        "created_at": datetime.utcnow().isoformat(),
                    })
            else:
                slides = slideshow.create_product_slideshow(
                    images=prepared, script=script, product=product, output_name=safe,
                )
                if slides:
                    slides_made += 1
                    _emit(job_id, "log", {"msg": f"✓ Slideshow {slides_made}: {product.title[:40]}"})
                    content_items.append({
                        "type": "slideshow", "files": [str(s) for s in slides], "name": safe,
                        "product_title": product.title,
                        "caption": script["hook"] + " " + script["cta"],
                        "affiliate_url": product.affiliate_url,
                        "created_at": datetime.utcnow().isoformat(),
                    })

        lib = OUTPUT_DIR / "library.json"
        existing = json.loads(lib.read_text()) if lib.exists() else []
        existing.extend(content_items)
        lib.write_text(json.dumps(existing, indent=2))

        jobs[job_id]["status"] = "done"
        _emit(job_id, "progress", {"pct": 100, "msg": "Done!", "videos": videos_made, "slides": slides_made})
        _emit(job_id, "done", {"videos": videos_made, "slides": slides_made, "total": videos_made + slides_made})
    except Exception as e:
        logger.exception("Generate failed")
        jobs[job_id]["status"] = "error"
        _emit(job_id, "error", {"msg": str(e)})


# ── API: clone ────────────────────────────────────────────────────────────────

@app.post("/api/clone/start")
async def clone_start(body: CloneRequest, background_tasks: BackgroundTasks):
    job_id = _new_job("clone")
    background_tasks.add_task(_run_in_thread, job_id, _clone_sync, body)
    return {"job_id": job_id}


def _clone_sync(job_id: str, body: CloneRequest):
    try:
        cfg = load_config()

        _emit(job_id, "log", {"msg": f"Starting clone of: {body.source_url}"})

        from generators.video_cloner import VideoCloner
        from agents.viral_finder import Product

        product = Product(
            title=body.product_title,
            asin=body.product_asin,
            price=body.product_price,
            rating=4.5,
            review_count=500,
            category=body.product_category,
            image_url="",
            product_url="",
            affiliate_url=f"https://www.amazon.com/dp/{body.product_asin}?tag={body.affiliate_tag or cfg.get('amazon', {}).get('partner_tag', 'test-20')}",
            viral_score=80.0,
            tags=[],
        )

        cloner = VideoCloner(cfg, output_dir=str(OUTPUT_DIR / "clones"))

        def emit_fn(event: str, data: dict):
            _emit(job_id, event, data)

        output_path = cloner.clone(
            source_url=body.source_url,
            product=product,
            emit_fn=emit_fn,
        )

        if output_path and output_path.exists():
            size_mb = output_path.stat().st_size / 1_048_576
            # Copy to videos dir so Library shows it
            import shutil
            dest = OUTPUT_DIR / "videos" / output_path.name
            shutil.copy2(str(output_path), str(dest))

            jobs[job_id]["status"] = "done"
            _emit(job_id, "done", {
                "file": str(dest),
                "name": output_path.name,
                "size_mb": round(size_mb, 1),
                "url": f"/output/videos/{output_path.name}",
            })
        else:
            jobs[job_id]["status"] = "error"
            _emit(job_id, "error", {"msg": "Clone failed — check the URL and try again"})
    except Exception as e:
        logger.exception("Clone failed")
        jobs[job_id]["status"] = "error"
        _emit(job_id, "error", {"msg": str(e)})


# ── API: LTX video generation ──────────────────────────────────────────────────

@app.post("/api/ltx/generate")
async def ltx_generate(body: LTXGenerateRequest, background_tasks: BackgroundTasks):
    """Generate UGC video via local LTX-Video."""
    job_id = _new_job("ltx_generate")
    background_tasks.add_task(_run_in_thread, job_id, _ltx_generate_sync, body)
    return {"job_id": job_id}


def _ltx_generate_sync(job_id: str, body: LTXGenerateRequest):
    try:
        from generators.ltx_video_generator import LTXVideoGenerator, VideoPrompt

        _emit(job_id, "log", {"msg": f"Generating UGC video: {body.product_title}"})

        gen = LTXVideoGenerator(output_dir=str(OUTPUT_DIR / "videos"))

        prompt = VideoPrompt(
            product_title=body.product_title,
            category=body.category,
            hook=body.hook or f"POV: you found the best {body.category.lower()} product",
            cta=body.cta or f"Get {body.product_title} now — limited stock 🔥",
            duration=body.duration,
        )

        def emit_fn(event: str, data: dict):
            _emit(job_id, event, data)

        output_path = gen.generate(prompt, output_name=f"ugc_{body.product_title[:20]}", emit_fn=emit_fn)

        if output_path and output_path.exists():
            size_mb = output_path.stat().st_size / 1_048_576
            jobs[job_id]["status"] = "done"
            _emit(job_id, "done", {
                "file": str(output_path),
                "name": output_path.name,
                "size_mb": round(size_mb, 1),
                "url": f"/output/videos/{output_path.name}",
            })
        else:
            jobs[job_id]["status"] = "error"
            _emit(job_id, "error", {"msg": "LTX-Video generation failed or server unavailable"})
    except Exception as e:
        logger.exception("LTX generation failed")
        jobs[job_id]["status"] = "error"
        _emit(job_id, "error", {"msg": str(e)})


# ── API: AnimateDiff video generation ──────────────────────────────────────────

@app.post("/api/animatediff/generate")
async def animatediff_generate(body: AnimateDiffRequest, background_tasks: BackgroundTasks):
    """Generate UGC video via local AnimateDiff (M1 Mac optimized)."""
    job_id = _new_job("animatediff_generate")
    background_tasks.add_task(_run_in_thread, job_id, _animatediff_generate_sync, body)
    return {"job_id": job_id}


def _animatediff_generate_sync(job_id: str, body: AnimateDiffRequest):
    try:
        from generators.animatediff_generator import AnimateDiffGenerator, AnimationStyle
        from pathlib import Path

        _emit(job_id, "log", {"msg": f"Animating {body.product_title}..."})

        # Resolve image path
        if body.image_path:
            image_path = OUTPUT_DIR / "images" / body.image_path
        else:
            # Look for any image for this product
            images = list((OUTPUT_DIR / "images").glob(f"*{body.product_title[:10]}*"))
            if images:
                image_path = images[0]
            else:
                _emit(job_id, "error", {"msg": "No product image found"})
                jobs[job_id]["status"] = "error"
                return

        if not image_path.exists():
            _emit(job_id, "error", {"msg": f"Image not found: {image_path}"})
            jobs[job_id]["status"] = "error"
            return

        gen = AnimateDiffGenerator(output_dir=str(OUTPUT_DIR / "videos"))

        style = AnimationStyle(
            motion_scale=body.motion_scale,
            num_frames=body.num_frames,
            steps=20,
            guidance_scale=7.5,
        )

        def emit_fn(event: str, data: dict):
            _emit(job_id, event, data)

        output_path = gen.generate(
            image_path=image_path,
            product_title=body.product_title,
            output_name=f"anim_{body.product_title[:20]}",
            style=style,
            emit_fn=emit_fn,
        )

        if output_path and output_path.exists():
            size_mb = output_path.stat().st_size / 1_048_576
            jobs[job_id]["status"] = "done"
            _emit(job_id, "done", {
                "file": str(output_path),
                "name": output_path.name,
                "size_mb": round(size_mb, 1),
                "url": f"/output/videos/{output_path.name}",
            })
        else:
            jobs[job_id]["status"] = "error"
            _emit(job_id, "error", {"msg": "AnimateDiff generation failed or ComfyUI unavailable"})
    except Exception as e:
        logger.exception("AnimateDiff generation failed")
        jobs[job_id]["status"] = "error"
        _emit(job_id, "error", {"msg": str(e)})


# ── API: library ──────────────────────────────────────────────────────────────

@app.get("/api/library/videos")
async def list_videos():
    d = OUTPUT_DIR / "videos"
    if not d.exists():
        return []
    return [
        {"name": f.name, "size_mb": round(f.stat().st_size / 1_048_576, 1),
         "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
         "url": f"/output/videos/{f.name}"}
        for f in sorted(d.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True)
    ]


@app.get("/api/library/slides")
async def list_slides():
    d = OUTPUT_DIR / "slideshows"
    if not d.exists():
        return []
    return [
        {"name": f.name, "size_mb": round(f.stat().st_size / 1_048_576, 1),
         "url": f"/output/slideshows/{f.name}"}
        for f in sorted(d.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)
    ]


# ── API: schedule ─────────────────────────────────────────────────────────────

@app.get("/api/schedule")
async def get_schedule():
    from scheduler.post_scheduler import PostQueue
    q = PostQueue(str(OUTPUT_DIR / "post_queue.json"))
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


# ── SSE: job stream ───────────────────────────────────────────────────────────

@app.get("/api/jobs/{job_id}/stream")
async def job_stream(job_id: str):
    if job_id not in job_signals:
        job_signals[job_id] = asyncio.Event()
    if job_id not in job_events:
        job_events[job_id] = []

    async def event_generator():
        sent = 0
        sig = job_signals[job_id]
        while True:
            # Wait for new events (or timeout for keepalive)
            try:
                await asyncio.wait_for(sig.wait(), timeout=20)
            except asyncio.TimeoutError:
                yield "event: ping\ndata: {}\n\n"
                continue

            sig.clear()
            events = job_events.get(job_id, [])
            while sent < len(events):
                msg = events[sent]
                sent += 1
                yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
                if msg["event"] in ("done", "error"):
                    return

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    return jobs.get(job_id, {"status": "not_found"})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _new_job(step: str) -> str:
    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = {"status": "running", "step": step, "started": datetime.utcnow().isoformat()}
    job_events[job_id] = []
    job_signals[job_id] = asyncio.Event()
    return job_id


async def _run_in_thread(job_id: str, fn, *args):
    """Run a blocking function in a thread pool, passing job_id as first arg."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, fn, job_id, *args)
    # Make sure SSE wakes up after thread completes
    sig = job_signals.get(job_id)
    if sig:
        sig.set()


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


# ── Static mounts ─────────────────────────────────────────────────────────────
for d in [OUTPUT_DIR / "videos", OUTPUT_DIR / "slideshows", OUTPUT_DIR / "images",
          OUTPUT_DIR / "audio", WEB_DIR / "static"]:
    d.mkdir(parents=True, exist_ok=True)

app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 50)
    print("  UGC Video Cloner — Web Dashboard")
    print("  Open: http://localhost:8080")
    print("  Press Ctrl+C to stop")
    print("=" * 50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=False)
