"""Provider-agnostic LLM seam for Legal Dojo.

Every agent in the app calls `llm_generate()`. Which provider/model actually
runs is decided here by the `LLM_PROVIDER` env var (default "gemini").
Switching from Gemini to Anthropic/OpenAI later is a one-line env change.

Today: Gemini via the google-genai SDK, using GEMINI_API_KEY.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

# Load backend/.env if present, overriding any stale key already in the shell
# (e.g. an exhausted free-tier GEMINI_API_KEY) so the .env value wins.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").lower()

# Per-role model selection. We'd normally give heavier reasoning (predictor,
# evaluators) the "pro" tier, but gemini-2.5-pro has zero quota on the free
# tier of the current key, so every role uses flash for now. Bump the pro
# roles back to "gemini-2.5-pro" once a paid tier / Gemini swap is in place.
_PRO = os.environ.get("LLM_PRO_MODEL", "gemini-2.5-flash")
_FLASH = os.environ.get("LLM_FLASH_MODEL", "gemini-2.5-flash")
# Long-context model for case parsing (1M+ token window). Override with
# LLM_CASE_PARSER_MODEL=gemini-1.5-pro for the full 2M-token window.
_CASE_PARSER = os.environ.get("LLM_CASE_PARSER_MODEL", "gemini-2.5-flash")
_GEMINI_MODELS: dict[str, str] = {
    "director": _FLASH,
    "adversary": _FLASH,
    "notetaker": _FLASH,
    "predictor": _PRO,
    "evaluator": _PRO,
    "case_parser": _CASE_PARSER,
    "default": _FLASH,
}


_NVIDIA_MODEL = os.environ.get("NVIDIA_NEMOTRON_MODEL", "nvidia/nemotron-3-super-120b-a12b")


class LLMError(RuntimeError):
    """Raised when a provider is misconfigured or a call fails."""


# ---------------------------------------------------------------------------
# Gemini adapter
# ---------------------------------------------------------------------------

# Bound how long a single call may hang (ms). Stops a throttled call from
# stalling on long internal retries — it fails fast and surfaces a clear error.
_TIMEOUT_MS = int(os.environ.get("LLM_TIMEOUT_MS", "30000"))
# Hidden "thinking" adds latency; off by default. Set LLM_THINKING=1 to re-enable.
_THINKING = os.environ.get("LLM_THINKING", "0") == "1"


@lru_cache(maxsize=1)
def _gemini_client():
    from google import genai  # imported lazily so other providers don't need it
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise LLMError("GEMINI_API_KEY is not set in the environment.")
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=_TIMEOUT_MS))


def _gemini_generate(prompt: str, system: str, role: str, json_mode: bool, temperature: float) -> str:
    from google.genai import types

    model = _GEMINI_MODELS.get(role, _GEMINI_MODELS["default"])
    kwargs: dict[str, Any] = dict(
        system_instruction=system or None,
        temperature=temperature,
        response_mime_type="application/json" if json_mode else None,
    )
    # Disable thinking on flash models to cut per-call latency (pro can't be 0).
    if not _THINKING and "flash" in model:
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    resp = _gemini_client().models.generate_content(
        model=model, contents=prompt, config=types.GenerateContentConfig(**kwargs)
    )
    return (resp.text or "").strip()


# ---------------------------------------------------------------------------
# Nemotron adapter — used specifically for evaluate_criteria (deep judgment)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _nvidia_client():
    from openai import OpenAI
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise LLMError("NVIDIA_API_KEY is not set.")
    return OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)


def nemotron_generate_json(prompt: str, system: str = "") -> Any:
    """Call Nemotron Super (streaming, thinking enabled) and parse the JSON response.

    Nemotron Super is a reasoning model — thinking tokens arrive in
    chunk.choices[0].delta.reasoning_content; the answer follows in .content.
    Falls back to None on any error so callers can degrade to Gemini.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = _nvidia_client().chat.completions.create(
            model=_NVIDIA_MODEL,
            messages=messages,
            temperature=1,
            top_p=0.95,
            max_tokens=2048,
            extra_body={
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": 512,
            },
            stream=False,
        )
        text = (resp.choices[0].message.content or "").strip()
        return _parse_json(text)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"[nemotron] call failed ({exc}), will fall back to Gemini")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def llm_generate(
    prompt: str,
    system: str = "",
    role: str = "default",
    json_mode: bool = False,
    temperature: float = 0.8,
) -> str:
    """Generate text from the configured provider.

    `role` selects the model tier (see the per-provider model maps).
    `json_mode` asks the model to return strict JSON.
    """
    if PROVIDER == "gemini":
        return _gemini_generate(prompt, system, role, json_mode, temperature)
    if PROVIDER == "anthropic":
        raise LLMError(
            "LLM_PROVIDER=anthropic is not wired yet. Set ANTHROPIC_API_KEY and "
            "implement _anthropic_generate to enable it."
        )
    if PROVIDER == "openai":
        raise LLMError(
            "LLM_PROVIDER=openai is not wired yet. Set OPENAI_API_KEY and "
            "implement _openai_generate to enable it."
        )
    raise LLMError(f"Unknown LLM_PROVIDER: {PROVIDER!r}")


def generate_json(
    prompt: str,
    system: str = "",
    role: str = "default",
    temperature: float = 0.7,
    fallback: Any = None,
) -> Any:
    """Generate JSON and parse it, tolerating code fences and stray prose.

    Returns `fallback` (default: empty dict) if parsing fails, so a single
    malformed response never crashes a negotiation turn.
    """
    raw = llm_generate(prompt, system=system, role=role, json_mode=True, temperature=temperature)
    parsed = _parse_json(raw)
    if parsed is None:
        return {} if fallback is None else fallback
    return parsed


def _parse_json(raw: str) -> Any | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Strip ```json ... ``` fences if present.
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    # Last resort: grab the outermost {...} or [...] block.
    match = re.search(r"(\{.*\}|\[.*\])", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None
