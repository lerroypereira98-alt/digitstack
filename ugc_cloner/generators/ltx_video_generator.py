"""
LTX-Video Integration for UGC Video Generation
Generates cinematic UGC videos from text prompts using LTX-Video locally.

Installation:
  1. Download LTX Desktop from: https://ltx.io/ltx-desktop
  2. Or via ComfyUI: add LTX-Video nodes via Manager
  3. Then this module auto-detects and uses it via WebSocket

Requires: LTX-Video running locally (GPU: 8GB+ VRAM, Disk: 40GB+)
"""

import logging
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VideoPrompt:
    """UGC video generation prompt."""
    product_title: str
    category: str
    hook: str
    cta: str
    style: str = "cinematic UGC ad"
    duration: int = 15

    def to_prompt(self) -> str:
        """Convert to LTX-Video text prompt."""
        return f"""{self.style}: {self.hook}
Product: {self.product_title} ({self.category})
Duration: {self.duration}s
CTA: {self.cta}
Professional lighting, clean composition, natural movement, 24fps"""


class LTXVideoGenerator:
    """
    Generates UGC videos via local LTX-Video installation.
    Supports both:
      - LTX Desktop (standalone app, easiest)
      - ComfyUI (most flexible, WebSocket API)
    """

    def __init__(self, output_dir: str = "output/videos",
                 ltx_server: str = "http://localhost:8188"):
        """
        Args:
            output_dir: Where to save generated videos
            ltx_server: LTX ComfyUI server URL (if using ComfyUI mode)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ltx_server = ltx_server
        self.mode = self._detect_mode()

    def _detect_mode(self) -> str:
        """Detect if LTX Desktop or ComfyUI is available."""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', 8188))
            sock.close()
            if result == 0:
                logger.info("Detected ComfyUI LTX-Video at localhost:8188")
                return "comfyui"
        except Exception:
            pass

        logger.warning("LTX-Video not detected. Install from https://ltx.io/ltx-desktop")
        return "offline"

    def generate(
        self,
        prompt: VideoPrompt,
        output_name: str = "ugc_video",
        emit_fn=None,
    ) -> Optional[Path]:
        """
        Generate a UGC video from prompt.

        Args:
            prompt: VideoPrompt with product & script info
            output_name: Output filename (without extension)
            emit_fn(event, data): Progress callback

        Returns:
            Path to generated video, or None if failed
        """
        def log(msg: str, event: str = "log"):
            logger.info(msg)
            if emit_fn:
                emit_fn(event, {"msg": msg})

        if self.mode == "offline":
            log("⚠️ LTX-Video not running. Start LTX Desktop or ComfyUI first.", "error")
            return None

        log(f"Generating UGC video: {prompt.product_title}...")

        try:
            if self.mode == "comfyui":
                return self._generate_comfyui(prompt, output_name, log)
            else:
                log("LTX-Video mode not available", "error")
                return None
        except Exception as e:
            logger.exception("Video generation failed")
            log(f"Error: {str(e)}", "error")
            return None

    def _generate_comfyui(
        self,
        prompt: VideoPrompt,
        output_name: str,
        log_fn,
    ) -> Optional[Path]:
        """Generate via ComfyUI WebSocket API."""
        import requests
        import time

        log_fn("Connecting to LTX-Video server...")

        # ComfyUI workflow for LTX-Video
        workflow = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "ltx-video-2.3-768-bf16.safetensors"}
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt.to_prompt(),
                    "clip": ["1", 1]
                }
            },
            "3": {
                "class_type": "LTXVideoSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "width": 768,
                    "height": 512,
                    "length": prompt.duration * 24,  # 24fps
                    "steps": 30,
                    "cfg": 7.5,
                    "seed": 42
                }
            },
            "4": {
                "class_type": "VHSVideoOutput",
                "inputs": {
                    "images": ["3", 0],
                    "output_format": "video/mp4",
                    "format": "mp4",
                    "path_pattern": str(self.output_dir / output_name)
                }
            }
        }

        try:
            # Queue workflow
            log_fn("Submitting to LTX-Video server...")
            r = requests.post(
                f"{self.ltx_server}/prompt",
                json={"client_id": "ugc-cloner", "prompt": workflow},
                timeout=10
            )

            if r.status_code != 200:
                log_fn(f"Server error: {r.text}", "error")
                return None

            prompt_id = r.json().get("prompt_id")
            log_fn(f"Job queued: {prompt_id}")

            # Poll for completion
            max_wait = 600  # 10 minutes
            elapsed = 0
            while elapsed < max_wait:
                try:
                    r = requests.get(
                        f"{self.ltx_server}/history/{prompt_id}",
                        timeout=5
                    )
                    if r.status_code == 200 and prompt_id in r.json():
                        history = r.json()[prompt_id]
                        if "outputs" in history:
                            # Success
                            outputs = history["outputs"]
                            if "videos" in outputs and outputs["videos"]:
                                video_path = self.output_dir / f"{output_name}.mp4"
                                log_fn(f"✓ Video generated: {video_path}")
                                return video_path
                except Exception:
                    pass

                log_fn(f"Generating... ({elapsed}s)", "progress")
                time.sleep(5)
                elapsed += 5

            log_fn("Generation timeout", "error")
            return None

        except requests.exceptions.ConnectionError:
            log_fn(
                "❌ Cannot connect to LTX-Video server (localhost:8188)\n"
                "Install from: https://ltx.io/ltx-desktop",
                "error"
            )
            return None


class UGCVideoPromptBuilder:
    """Build VideoPrompt from product + script info."""

    @staticmethod
    def from_product(
        product,
        hook: str = "",
        cta: str = "",
    ) -> VideoPrompt:
        """Create VideoPrompt from Product object."""
        if not hook:
            hook = f"POV: you found the best {product.category.lower()} product"
        if not cta:
            cta = f"Get {product.title} now — limited stock 🔥"

        return VideoPrompt(
            product_title=product.title,
            category=product.category,
            hook=hook,
            cta=cta,
        )
