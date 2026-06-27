"""Text-to-speech for the AI opponent, via Gemini (same key as everything else).

Gemini TTS returns raw 24 kHz 16-bit mono PCM; we wrap it in a WAV container so
browsers can play it directly from an <audio> element.
"""
from __future__ import annotations

import io
import os
import wave

import llm  # reuse the configured google-genai client

TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
TTS_VOICE = os.environ.get("TTS_VOICE", "Charon")  # firm, lawyerly default
_SAMPLE_RATE = 24000


def _pcm_to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(_SAMPLE_RATE)
        wf.writeframes(pcm)
    return buf.getvalue()


def synthesize(text: str, voice: str | None = None) -> bytes:
    """Return WAV audio bytes for `text`. Raises on failure (caller handles)."""
    from google.genai import types

    resp = llm._gemini_client().models.generate_content(
        model=TTS_MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice or TTS_VOICE
                    )
                )
            ),
        ),
    )
    pcm = resp.candidates[0].content.parts[0].inline_data.data
    return _pcm_to_wav(pcm)
