"""
Text-to-Speech Engine
Generates voiceovers for UGC videos using gTTS (free, online) or pyttsx3 (offline).
"""

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Optional
import random

logger = logging.getLogger(__name__)

UGC_HOOK_TEMPLATES = [
    "POV you just found the best {category} product on Amazon.",
    "I can't believe this {product} exists and it's only {price} dollars.",
    "This {product} completely changed my routine, no exaggeration.",
    "Amazon finds that feel illegal to know about. Number one: {product}.",
    "Stop scrolling. You need to see this {product}.",
    "I've been sleeping on this {product} for way too long.",
    "Rating viral TikTok {category} products so you don't have to.",
    "Okay so I found this {product} and I'm obsessed.",
]

UGC_CTA_TEMPLATES = [
    "Link is in my bio. Grab it before it sells out.",
    "I'll drop the link in my bio. It's on sale right now.",
    "Affiliate link in bio — it literally costs you nothing extra.",
    "Check my bio for the direct Amazon link, it's so worth it.",
    "Link in bio. Thank me later.",
]

UGC_MIDDLE_TEMPLATES = [
    "{product} is honestly one of those products you didn't know you needed until you have it. "
    "The quality is insane for {price} dollars. It has over {reviews} reviews and almost all of them are five stars.",
    "So this is the {product}. I've been using it for a few weeks and honestly it's a game changer. "
    "You can get it on Amazon for {price} dollars with over {reviews} reviews.",
    "Let me show you why everyone is obsessed with this {product}. "
    "It's rated {rating} stars with {reviews} reviews and honestly the price is unbeatable at {price} dollars.",
]


class ScriptGenerator:
    """Generates UGC-style video scripts for products."""

    def generate(self, product, style: str = "hook_review") -> dict:
        title = product.title
        price = f"{product.price:.0f}" if product.price else "a great price"
        reviews = f"{product.review_count:,}" if product.review_count else "thousands of"
        rating = f"{product.rating}" if product.rating else "5"
        category = product.category or "product"

        def fill(template: str) -> str:
            return (
                template
                .replace("{product}", title[:40])
                .replace("{price}", price)
                .replace("{reviews}", reviews)
                .replace("{rating}", rating)
                .replace("{category}", category)
            )

        hook = fill(random.choice(UGC_HOOK_TEMPLATES))
        middle = fill(random.choice(UGC_MIDDLE_TEMPLATES))
        cta = fill(random.choice(UGC_CTA_TEMPLATES))

        full_script = f"{hook} {middle} {cta}"

        return {
            "hook": hook,
            "middle": middle,
            "cta": cta,
            "full": full_script,
            "title_overlay": title[:50],
            "price_overlay": f"${product.price:.2f}" if product.price else "",
        }


class TTSEngine:
    """
    Text-to-speech engine with multiple backends.
    - "gtts": Google TTS (free, requires internet, sounds natural)
    - "pyttsx3": Offline system TTS (no internet needed)
    - "edge_tts": Microsoft Edge TTS (free, very natural, requires internet)
    """

    def __init__(self, engine: str = "gtts", language: str = "en", speed: float = 1.15):
        self.engine = engine
        self.language = language
        self.speed = speed
        self._verify_engine()

    def _verify_engine(self):
        if self.engine == "gtts":
            try:
                import gtts  # noqa
            except ImportError:
                logger.warning("gTTS not installed. Falling back to pyttsx3.")
                self.engine = "pyttsx3"
        if self.engine == "edge_tts":
            try:
                import edge_tts  # noqa
            except ImportError:
                logger.warning("edge-tts not installed. Falling back to gtts.")
                self.engine = "gtts"

    def synthesize(self, text: str, output_path: Path) -> Optional[Path]:
        """Convert text to speech and save to output_path (.mp3)."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists():
            return output_path

        try:
            if self.engine == "gtts":
                return self._synth_gtts(text, output_path)
            elif self.engine == "edge_tts":
                return self._synth_edge_tts(text, output_path)
            else:
                return self._synth_pyttsx3(text, output_path)
        except Exception as e:
            logger.error("TTS synthesis failed: %s", e)
            return None

    def _synth_gtts(self, text: str, output_path: Path) -> Optional[Path]:
        from gtts import gTTS
        tts = gTTS(text=text, lang=self.language, slow=False)
        tts.save(str(output_path))
        # Speed up using ffmpeg if speed != 1.0
        if abs(self.speed - 1.0) > 0.05:
            self._change_speed(output_path)
        return output_path

    def _synth_edge_tts(self, text: str, output_path: Path) -> Optional[Path]:
        import asyncio
        import edge_tts

        # High-quality natural voices
        voices = [
            "en-US-AriaNeural",   # Female, natural
            "en-US-GuyNeural",    # Male, natural
            "en-US-JennyNeural",  # Female, conversational
        ]
        voice = random.choice(voices)

        async def _run():
            communicate = edge_tts.Communicate(text, voice, rate=f"+{int((self.speed - 1) * 100)}%")
            await communicate.save(str(output_path))

        asyncio.run(_run())
        return output_path

    def _synth_pyttsx3(self, text: str, output_path: Path) -> Optional[Path]:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", int(150 * self.speed))
        engine.setProperty("volume", 0.95)
        # Use best available voice
        voices = engine.getProperty("voices")
        if voices:
            engine.setProperty("voice", voices[0].id)
        engine.save_to_file(text, str(output_path))
        engine.runAndWait()
        return output_path if output_path.exists() else None

    def _change_speed(self, audio_path: Path):
        """Use ffmpeg to change audio speed in-place."""
        import subprocess
        tmp = audio_path.with_suffix(".tmp.mp3")
        cmd = [
            "ffmpeg", "-y", "-i", str(audio_path),
            "-filter:a", f"atempo={self.speed}",
            "-q:a", "0",
            str(tmp),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode == 0 and tmp.exists():
                tmp.replace(audio_path)
        except Exception as e:
            logger.debug("Speed change failed: %s", e)
        finally:
            if tmp.exists():
                tmp.unlink()
