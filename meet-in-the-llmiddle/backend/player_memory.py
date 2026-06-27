"""Persistent, user-editable memory of the player's negotiating behaviour.

Carries across sessions so the Director can exploit known tendencies and so
future training can target weak spots. Stored as a single JSON file the user
can edit by hand or through the in-app Training Profile page.

Each observation is a dict: {text, sessions_since_last_seen, added_at}.
An observation is evicted once it hasn't re-appeared in EVICT_AFTER consecutive
completed sessions, which signals the player has fixed that tendency.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

PROFILE_FILE = Path(__file__).parent / "data" / "player_profile.json"

_DEFAULT: dict[str, Any] = {
    "display_name": "Trainee",
    "notes": "Editable notes about your negotiation style and goals. Add anything you want the trainer to remember.",
    "observations": [],
    "timer_idle_secs": 30,
    "timer_response_secs": 120,
    "updated_at": None,
}

MAX_OBSERVATIONS = 12
EVICT_AFTER = 2  # sessions without the weak spot re-appearing → auto-remove


def _coerce_obs(raw: list) -> list[dict]:
    """Migrate old string observations to the current dict format."""
    result = []
    for o in raw:
        if isinstance(o, str) and o.strip():
            result.append({"text": o.strip(), "sessions_since_last_seen": 0, "added_at": None})
        elif isinstance(o, dict) and str(o.get("text", "")).strip():
            result.append({
                "text": str(o["text"]).strip(),
                "sessions_since_last_seen": int(o.get("sessions_since_last_seen", 0)),
                "added_at": o.get("added_at"),
            })
    return result


def load_profile() -> dict[str, Any]:
    if not PROFILE_FILE.exists():
        return dict(_DEFAULT)
    try:
        with PROFILE_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT)
    merged = {**_DEFAULT, **data}
    merged["observations"] = _coerce_obs(merged.get("observations", []))
    return merged


def save_profile(profile: dict[str, Any]) -> dict[str, Any]:
    obs = _coerce_obs(profile.get("observations", []))[-MAX_OBSERVATIONS:]
    def _clamp_secs(val: Any, default: int) -> int:
        try:
            return max(30, min(1800, int(val)))
        except (TypeError, ValueError):
            return default

    clean = {
        "display_name": str(profile.get("display_name", "Trainee"))[:80],
        "notes": str(profile.get("notes", "")),
        "observations": obs,
        "timer_idle_secs": _clamp_secs(profile.get("timer_idle_secs"), 120),
        "timer_response_secs": _clamp_secs(profile.get("timer_response_secs"), 300),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PROFILE_FILE.open("w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    return clean


def _fuzzy_match(a: str, b: str) -> bool:
    """True if either string is a substring of the other (case-insensitive)."""
    a, b = a.lower().strip(), b.lower().strip()
    return a in b or b in a


def _llm_match_spots(new_spots: list[str], existing: list[dict]) -> tuple[dict[int, str], list[str]]:
    """Use the LLM to find which new weak spots are semantically the same as existing ones.

    Returns:
        matched: {existing_index: new_spot_text}  — existing obs that this session confirmed
        unmatched: [new_spot_text]                 — genuinely new issues
    """
    if not new_spots or not existing:
        return {}, new_spots

    try:
        import llm as _llm
        existing_lines = "\n".join(f"  [{i}] {o['text']}" for i, o in enumerate(existing))
        new_lines = "\n".join(f"  - {s}" for s in new_spots)
        prompt = (
            "EXISTING tracked weak spots:\n" + existing_lines +
            "\n\nNEW weak spots from latest session:\n" + new_lines +
            "\n\nFor each new spot, decide if it describes the same underlying weakness "
            "as one of the existing spots (even if worded differently). "
            'Return JSON: {"matches": [{"new": "exact new text", "existing_index": <int or null>}]}'
        )
        data = _llm.generate_json(
            prompt,
            system="You are a deduplication assistant for a legal coaching system.",
            role="evaluator",
            temperature=0.1,
            fallback={},
        )
        matched: dict[int, str] = {}
        unmatched: list[str] = []
        for m in (data.get("matches") if isinstance(data, dict) else []) or []:
            text = str(m.get("new", "")).strip()
            idx = m.get("existing_index")
            if text and isinstance(idx, int) and 0 <= idx < len(existing):
                matched[idx] = text
            elif text:
                unmatched.append(text)
        return matched, unmatched
    except Exception:
        # Fallback: original substring matching
        matched = {}
        unmatched = []
        for spot in new_spots:
            found = False
            for i, obs in enumerate(existing):
                if _fuzzy_match(obs["text"], spot):
                    matched[i] = spot
                    found = True
                    break
            if not found:
                unmatched.append(spot)
        return matched, unmatched


def update_from_session(session: dict[str, Any], report: dict[str, Any]) -> None:
    """Fold a finished session's weak spots into the persistent profile.

    Uses LLM-based semantic deduplication so the same underlying issue never
    accumulates as multiple differently-worded entries. Matched observations are
    refreshed (text updated to the clearer phrasing); unmatched new spots are
    appended. Observations unseen for EVICT_AFTER consecutive sessions are dropped.
    """
    profile = load_profile()
    observations = _coerce_obs(profile.get("observations", []))
    now = datetime.now(timezone.utc).isoformat()

    new_spots = [str(w).strip() for w in report.get("weak_spots", []) if str(w).strip()]

    # LLM matches new spots to existing observations
    matched, unmatched = _llm_match_spots(new_spots, observations)

    # Update matched observations: reset counter, refresh text if clearer
    for idx, new_text in matched.items():
        obs = observations[idx]
        obs["sessions_since_last_seen"] = 0
        # Take the longer/more descriptive phrasing
        if len(new_text) > len(obs["text"]):
            obs["text"] = new_text

    # Age unmatched existing observations
    for i, obs in enumerate(observations):
        if i not in matched:
            obs["sessions_since_last_seen"] = obs.get("sessions_since_last_seen", 0) + 1

    # Drop stale observations
    observations = [o for o in observations if o["sessions_since_last_seen"] < EVICT_AFTER]

    # Append genuinely new weak spots (not a duplicate of anything remaining)
    existing_texts = {o["text"].lower() for o in observations}
    for spot in unmatched:
        if spot.lower() not in existing_texts:
            observations.append({"text": spot, "sessions_since_last_seen": 0, "added_at": now})

    observations = observations[-MAX_OBSERVATIONS:]
    profile["observations"] = observations
    save_profile(profile)


def digest(limit: int = 6) -> str:
    """A compact tendencies string for the Director prompt."""
    profile = load_profile()
    obs = _coerce_obs(profile.get("observations", []))[-limit:]
    texts = [o["text"] for o in obs]
    notes = profile.get("notes", "").strip()
    parts = []
    if texts:
        parts.append("Recurring weak spots: " + "; ".join(texts))
    if notes and notes != _DEFAULT["notes"]:
        parts.append(f"Self-noted: {notes[:200]}")
    return " | ".join(parts)
