"""JSON-file persistence: cases, and multi-session negotiation state.

No database. Cases live in data/cases/*.json. Each negotiation is a single
JSON file under data/sessions/<id>.json. There is no longer a single fixed
session — every "Begin Negotiation" creates a fresh, timestamped session, so
past simulations remain available as history.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import concession

DATA_DIR = Path(__file__).parent / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
CASES_DIR = DATA_DIR / "cases"

# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

def list_cases() -> list[dict[str, Any]]:
    cases = []
    for path in sorted(CASES_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            c = json.load(f)
        cases.append({"id": c["id"], "title": c["title"], "summary": c.get("summary", "")})
    return cases


def load_case(case_id: str) -> dict[str, Any]:
    path = CASES_DIR / f"{case_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Unknown case: {case_id}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_case(case: dict[str, Any], overwrite: bool = False) -> None:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    path = CASES_DIR / f"{case['id']}.json"
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"Case '{case['id']}' already exists. Pass overwrite=True to replace it."
        )
    path.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")


def opposite_side(case: dict[str, Any], side: str) -> str:
    others = [s for s in case["sides"] if s != side]
    if not others:
        raise ValueError(f"No opposing side found for '{side}' in case '{case['id']}'")
    return others[0]


def player_packet(case: dict[str, Any], side: str) -> dict[str, Any]:
    """The case file the player sees: their side + shared background/documents."""
    s = case["sides"][side]
    return {
        "case_id": case["id"],
        "title": case["title"],
        "background": case["background"],
        "side": side,
        "role": s["role"],
        "goal": s["goal"],
        "batna": s["batna"],
        "objectives": s["objectives"],
        "documents": case.get("shared_documents", []),
    }


def ai_packet(case: dict[str, Any], player_side: str) -> dict[str, Any]:
    """The opponent's private packet (the side the player did NOT pick)."""
    side = opposite_side(case, player_side)
    s = case["sides"][side]
    return {
        "title": case["title"],
        "background": case["background"],
        "legal_context": case.get("legal_context", ""),
        "shared_documents": case.get("shared_documents", []),
        "side": side,
        "role": s["role"],
        "goal": s["goal"],
        "batna": s["batna"],
        "private_facts": s.get("private_facts", []),
        "objectives": s["objectives"],
    }


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def _session_path(sid: str) -> Path:
    return SESSIONS_DIR / f"{sid}.json"


def new_session_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{secrets.token_hex(2)}"


def create_session(case_id: str, side: str, personality: str = "default") -> dict[str, Any]:
    case = load_case(case_id)
    if side not in case["sides"]:
        raise ValueError(
            f"Invalid side '{side}'. Available sides: {list(case['sides'].keys())}"
        )
    session = {
        "id": new_session_id(),
        "case_id": case_id,
        "case_title": case["title"],
        "side": side,
        "personality": personality,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "summary": "",
        "ai_memory": [],
        "concession_state": concession.init_state(),
        "turns": [],
        "report": None,
    }
    save_session(session)
    return session


def delete_session(sid: str) -> bool:
    path = _session_path(sid)
    if path.exists():
        path.unlink()
        return True
    return False


def prune_empty_sessions() -> int:
    """Delete 0-turn, never-finished session drafts. Returns count removed."""
    removed = 0
    for path in SESSIONS_DIR.glob("*.json"):
        try:
            with path.open(encoding="utf-8") as f:
                s = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if len(s.get("turns", [])) == 0 and s.get("status") != "ended":
            path.unlink()
            removed += 1
    return removed


def load_session(sid: str) -> dict[str, Any]:
    path = _session_path(sid)
    if not path.exists():
        raise FileNotFoundError(f"Unknown session: {sid}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_session(session: dict[str, Any]) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    with _session_path(session["id"]).open("w", encoding="utf-8") as f:
        json.dump(session, f, indent=2, ensure_ascii=False)


def list_sessions() -> list[dict[str, Any]]:
    """History cards: only ENDED simulations. In-progress games are not history
    — they're resumed via their session id, not listed here.
    """
    out = []
    for path in SESSIONS_DIR.glob("*.json"):
        try:
            with path.open(encoding="utf-8") as f:
                s = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if s.get("status") != "ended":
            continue
        out.append(
            {
                "id": s["id"],
                "case_id": s.get("case_id"),
                "case_title": s.get("case_title", ""),
                "side": s.get("side"),
                "created_at": s.get("created_at"),
                "status": s.get("status", "active"),
                "turns": len(s.get("turns", [])),
                "summary": s.get("summary", ""),
            }
        )
    out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return out
