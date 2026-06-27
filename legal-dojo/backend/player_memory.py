"""Persistent, user-editable memory of the player's negotiating behaviour.

Carries across sessions so the Director can exploit known tendencies and so
future training can target weak spots. Stored as a single JSON file the user
can edit by hand or through the in-app Training Profile page.
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
    "updated_at": None,
}

MAX_OBSERVATIONS = 30


def load_profile() -> dict[str, Any]:
    if not PROFILE_FILE.exists():
        return dict(_DEFAULT)
    try:
        with PROFILE_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT)
    # Backfill any missing keys.
    return {**_DEFAULT, **data}


def save_profile(profile: dict[str, Any]) -> dict[str, Any]:
    clean = {
        "display_name": str(profile.get("display_name", "Trainee"))[:80],
        "notes": str(profile.get("notes", "")),
        "observations": [str(o) for o in profile.get("observations", []) if str(o).strip()][:MAX_OBSERVATIONS],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PROFILE_FILE.open("w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    return clean


def update_from_session(session: dict[str, Any], report: dict[str, Any]) -> None:
    """Fold a finished session's weak spots into the persistent profile."""
    profile = load_profile()
    existing = set(profile.get("observations", []))
    case = session.get("case_title", "a case")
    for w in report.get("weak_spots", []):
        entry = f"{w}"
        if entry not in existing:
            profile.setdefault("observations", []).append(entry)
            existing.add(entry)
    # Keep newest observations if we overflow.
    profile["observations"] = profile["observations"][-MAX_OBSERVATIONS:]
    save_profile(profile)


def digest(limit: int = 6) -> str:
    """A compact tendencies string for the Director prompt."""
    profile = load_profile()
    obs = profile.get("observations", [])[-limit:]
    notes = profile.get("notes", "").strip()
    parts = []
    if obs:
        parts.append("Recurring weak spots: " + "; ".join(obs))
    if notes and notes != _DEFAULT["notes"]:
        parts.append(f"Self-noted: {notes[:200]}")
    return " | ".join(parts)
