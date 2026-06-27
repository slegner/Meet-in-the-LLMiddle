"""Text-to-speech for the AI opponent.

Default provider is OpenAI `tts-1`, **streamed** so the browser starts playing
~1s after the reply instead of waiting for the whole clip (Gemini's preview TTS
is non-streaming and ~13s — too slow for live use). Gemini TTS is kept as a
non-streaming fallback (TTS_PROVIDER=gemini).
"""
from __future__ import annotations

import io
import os
import wave
from pathlib import Path
from typing import AsyncIterator

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "openai").lower()
OPENAI_TTS_MODEL = os.environ.get("OPENAI_TTS_MODEL", "tts-1")
OPENAI_TTS_VOICE = os.environ.get("TTS_VOICE", "echo")  # younger male
OPENAI_TTS_SPEED = float(os.environ.get("TTS_SPEED", "1.15"))  # 1.0 normal, up to 4.0
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")


def media_type() -> str:
    return "audio/mpeg" if TTS_PROVIDER == "openai" else "audio/wav"


async def stream_tts(text: str) -> AsyncIterator[bytes]:
    """Yield audio bytes for `text` as they are produced."""
    if TTS_PROVIDER == "openai":
        async for chunk in _openai_stream(text):
            yield chunk
    else:
        # Gemini path can't stream the simple API — yield the whole clip.
        yield _gemini_wav(text)


async def _openai_stream(text: str) -> AsyncIterator[bytes]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    payload = {
        "model": OPENAI_TTS_MODEL,
        "voice": OPENAI_TTS_VOICE,
        "input": text,
        "response_format": "mp3",
        "speed": OPENAI_TTS_SPEED,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST", "https://api.openai.com/v1/audio/speech", headers=headers, json=payload
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes():
                if chunk:
                    yield chunk


def _gemini_wav(text: str) -> bytes:
    import llm
    from google.genai import types

    resp = llm._gemini_client().models.generate_content(
        model=GEMINI_TTS_MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
                )
            ),
        ),
    )
    pcm = resp.candidates[0].content.parts[0].inline_data.data
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm)
    return buf.getvalue()
