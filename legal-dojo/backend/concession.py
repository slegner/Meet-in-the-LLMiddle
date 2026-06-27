"""Deterministic concession rules for the AI opponent.

These run independently of the LLM and inject hard constraints into the
Director's prompt, so the opponent's escalation/de-escalation is predictable
and game-like regardless of model whim:

  * Start highly aggressive.
  * If the user makes a strong, logical legal argument, concede slightly on the
    AI's next turn.
  * Never repeat the exact same demand more than twice.
  * From a per-session random turn (6-12), drive toward a middle-ground
    compromise.
"""
from __future__ import annotations

import os
import random
import re
from typing import Any

# Signals that the student has made a substantive, citable legal argument
# (as opposed to mere assertion). Extends the leverage heuristic from v1.
_STRONG_ARGUMENT_SIGNALS = (
    "market standard",
    "market rate",
    "comparable",
    "clause 7",
    "clause 12",
    "loss-adjuster",
    "loss adjuster",
    "repairing covenant",
    "covenant",
    "statute",
    "section ",
    "precedent",
    "case law",
    "relief from forfeiture",
    "breach",
    "abatement",
    "obliged",
    "obligation",
    "entitled",
    "the report",
)


# The turn from which the opponent starts driving toward compromise is rolled
# once per session, so the player can't predict exactly when it softens.
COMPROMISE_MIN = int(os.environ.get("COMPROMISE_MIN", "6"))
COMPROMISE_MAX = int(os.environ.get("COMPROMISE_MAX", "12"))


def init_state() -> dict[str, Any]:
    return {
        "turn": 0,
        "recent_demands": [],   # normalized demand signatures, newest last
        "phase_history": [],    # phase used each AI turn
        "compromise_turn": random.randint(COMPROMISE_MIN, COMPROMISE_MAX),
    }


def ensure(state: dict[str, Any]) -> dict[str, Any]:
    """Backfill any missing keys (e.g. for sessions created before this field)."""
    state.setdefault("turn", 0)
    state.setdefault("recent_demands", [])
    state.setdefault("phase_history", [])
    state.setdefault("compromise_turn", random.randint(COMPROMISE_MIN, COMPROMISE_MAX))
    return state


def detect_strong_argument(message: str) -> bool:
    text = (message or "").lower()
    hits = sum(1 for s in _STRONG_ARGUMENT_SIGNALS if s in text)
    # A single clear citation, or two softer signals, counts as "strong".
    has_citation = bool(re.search(r"clause\s*\d+|section\s*\d+", text))
    return has_citation or hits >= 2


def _normalize_demand(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()[:160]


def plan_turn(state: dict[str, Any], student_message: str) -> dict[str, Any]:
    """Decide the phase + constraints for the AI's upcoming reply.

    Returns a dict with a `phase`, booleans, and a `directive` string that is
    appended verbatim to the Director's prompt.
    """
    turn_number = state.get("turn", 0) + 1
    strong = detect_strong_argument(student_message)
    recent = state.get("recent_demands", [])
    repeated = len(recent) >= 2 and recent[-1] == recent[-2]
    compromise_turn = state.get("compromise_turn", COMPROMISE_MIN)

    if turn_number >= compromise_turn:
        phase = "compromise"
    elif strong:
        phase = "concede"
    elif turn_number <= 2:
        phase = "aggressive"
    else:
        phase = "firm"

    parts = [f"This is the opponent's turn {turn_number}."]
    if phase == "aggressive":
        parts.append("Open from a HIGH, aggressive position. Do not give ground yet; make the student work.")
    elif phase == "firm":
        parts.append("Hold a firm position. You may probe, doubt, bluff, or use a fake concession, but do not make a real concession this turn.")
    elif phase == "concede":
        parts.append("The student just made a strong, logical legal argument. You MUST concede SLIGHTLY this turn — give a small, real movement toward them while protecting your headline goal.")
    elif phase == "compromise":
        parts.append("It is turn 6 or later. Begin actively driving toward a realistic middle-ground compromise that both sides could accept.")

    if repeated:
        parts.append("You have already made the same core demand twice — you MUST change or move it now; do not repeat it again.")
    elif recent:
        parts.append("Avoid repeating the exact same demand you already used; vary your framing or position.")

    return {
        "turn_number": turn_number,
        "phase": phase,
        "must_concede": phase in ("concede", "compromise"),
        "strong_argument": strong,
        "force_move": repeated,
        "directive": " ".join(parts),
    }


def record_turn(state: dict[str, Any], plan: dict[str, Any], demand_summary: str) -> None:
    """Update state after the AI reply is chosen."""
    state["turn"] = plan["turn_number"]
    sig = _normalize_demand(demand_summary)
    if sig:
        state.setdefault("recent_demands", []).append(sig)
        state["recent_demands"] = state["recent_demands"][-4:]
    state.setdefault("phase_history", []).append(plan["phase"])
