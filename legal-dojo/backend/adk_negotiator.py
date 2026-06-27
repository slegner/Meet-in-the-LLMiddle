"""The AI opponent as a genuine ADK multi-agent team.

Four LlmAgents collaborate over shared session state, in one pipeline per turn:

  Director  -> {directive}   strategy (tactic + instruction), obeying the
                              deterministic concession rules injected as state.
  Adversary -> {cand}        3 candidate replies that follow the directive.
  Predictor -> {sel}         forecasts and picks the best candidate.
  NoteTaker -> {note}        the AI's private read of the opponent (confidence,
                             trust, tells) — "how the negotiator sees the user".

Ethical-usage guardrails: right-sized models (flash / flash-lite), only 3
candidates, lean prompts, and per-turn token accounting returned to the caller
so consumption is visible. Gemini 2.5 also caches repeated prefixes implicitly.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel

# ADK (AI Studio mode) authenticates via GOOGLE_API_KEY — mirror our key in.
load_dotenv(Path(__file__).parent / ".env", override=True)
os.environ.setdefault("GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent  # noqa: E402
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

import concession  # noqa: E402
import store  # noqa: E402

FLASH = os.environ.get("LLM_FLASH_MODEL", "gemini-2.5-flash")
LITE = os.environ.get("LLM_LITE_MODEL", "gemini-2.5-flash-lite")
APP_NAME = "legal_dojo"
N_CANDIDATES = 3


def _cfg(temperature: float):
    """Per-agent generation config. Thinking is disabled to cut latency/cost
    (a key ethical-usage guardrail) unless LLM_THINKING=1."""
    from google.genai import types as t

    kwargs: dict[str, Any] = {"temperature": temperature}
    if os.environ.get("LLM_THINKING", "0") != "1":
        kwargs["thinking_config"] = t.ThinkingConfig(thinking_budget=0)
    return t.GenerateContentConfig(**kwargs)


# ---------------------------------------------------------------------------
# Structured outputs
# ---------------------------------------------------------------------------

class Directive(BaseModel):
    tactic: str
    instruction: str


class Candidates(BaseModel):
    candidates: list[str]


class Selection(BaseModel):
    choice: int
    why: str


# ---------------------------------------------------------------------------
# The agent team (built once)
# ---------------------------------------------------------------------------

director = LlmAgent(
    name="director",
    model=FLASH,
    output_schema=Directive,
    output_key="directive",
    generate_content_config=_cfg(0.7),
    instruction=(
        "You are the DIRECTOR, the private strategist for a tough legal negotiator. "
        "You never speak to the opponent. You represent the {ai_side} side.\n"
        "Your brief:\n{ai_packet}\n"
        "Conversation so far:\n{transcript}\n"
        "Your private notes so far:\n{ai_notes}\n"
        "The opponent just said:\n{student_message}\n"
        "Hard rules you MUST obey this turn: {hard_rules}\n"
        "Decide the single best tactic (such as anchor_high, bluff, fake_concession, "
        "reject, reframe, small_concession, drive_compromise) and give a concrete "
        "instruction for what the negotiator should say. Favour firmness; never fold "
        "just because the opponent sounds confident."
    ),
)

adversary = LlmAgent(
    name="adversary",
    model=FLASH,
    output_schema=Candidates,
    output_key="cand",
    generate_content_config=_cfg(0.95),
    instruction=(
        "You are the ADVERSARY, a sharp opposing legal negotiator speaking directly "
        "to the other side in the first person. You represent the {ai_side} side.\n"
        "Your brief:\n{ai_packet}\n"
        "Conversation so far:\n{transcript}\n"
        "The opponent just said:\n{student_message}\n"
        "Your director's guidance: {directive}\n"
        f"Write {N_CANDIDATES} distinct candidate replies, each 2-4 sentences, all "
        "following the director's guidance but varying in wording and emphasis. "
        "Never reveal your private facts or BATNA outright."
    ),
)

predictor = LlmAgent(
    name="predictor",
    model=LITE,
    output_schema=Selection,
    output_key="sel",
    generate_content_config=_cfg(0.4),
    instruction=(
        "You are the PREDICTOR. You forecast how each candidate reply will land and "
        "pick the best one for YOUR side ({ai_side}).\n"
        "Your brief:\n{ai_packet}\n"
        "Director guidance: {directive}\n"
        "Candidate replies: {cand}\n"
        "Choose the 0-based index of the strongest candidate and explain briefly."
    ),
)

notetaker = LlmAgent(
    name="notetaker",
    model=LITE,
    output_key="note",
    generate_content_config=_cfg(0.85),
    instruction=(
        "You are the NOTE-TAKER voicing the negotiator's private inner monologue "
        "about the opponent as a person — how you feel and what you now believe "
        "about them: confidence, whether you trust them, and any tells they reveal. "
        "First person, 1-2 sentences.\n"
        "You represent the {ai_side} side. Your prior notes:\n{ai_notes}\n"
        "The opponent just said:\n{student_message}\n"
        "Write your private note about the opponent."
    ),
)

# NoteTaker only reads seeded state (notes + the student's message), so it runs
# in PARALLEL with the Director->Adversary->Predictor reply chain — taking it off
# the critical path.
reply_chain = SequentialAgent(name="reply_chain", sub_agents=[director, adversary, predictor])
team = ParallelAgent(name="negotiation_turn", sub_agents=[reply_chain, notetaker])
_runner = InMemoryRunner(agent=team, app_name=APP_NAME)


# ---------------------------------------------------------------------------
# Context rendering (mirrors the non-ADK path)
# ---------------------------------------------------------------------------

def _render_packet(ai: dict[str, Any]) -> str:
    facts = "\n".join(f"  - {f}" for f in ai.get("private_facts", []))
    objs = "\n".join(f"  - {o}" for o in ai.get("objectives", []))
    return (
        f"Role: {ai['role']}\nGoal: {ai['goal']}\nBATNA: {ai['batna']}\n"
        f"Private facts (never reveal directly):\n{facts}\nObjectives:\n{objs}"
    )


def _render_transcript(session: dict[str, Any]) -> str:
    turns = session.get("turns", [])[-12:]
    if not turns:
        return "(no exchanges yet — this is the opening)"
    return "\n".join(
        f"Student: {t['student']}\nYou (AI): {t['adversary']}" for t in turns
    )


def _render_memory(session: dict[str, Any]) -> str:
    notes = session.get("ai_memory", [])
    return "\n".join(f"  - Turn {n['turn']}: {n['note']}" for n in notes) or "(none yet)"


# ---------------------------------------------------------------------------
# Run one turn
# ---------------------------------------------------------------------------

async def _run(state: dict[str, Any], student_message: str) -> tuple[dict[str, Any], int]:
    sid = f"t-{os.urandom(4).hex()}"
    await _runner.session_service.create_session(
        app_name=APP_NAME, user_id="player", session_id=sid, state=state
    )
    msg = types.Content(role="user", parts=[types.Part(text=student_message)])
    tokens = 0
    async for ev in _runner.run_async(user_id="player", session_id=sid, new_message=msg):
        um = getattr(ev, "usage_metadata", None)
        if um and getattr(um, "total_token_count", None):
            tokens += um.total_token_count
    sess = await _runner.session_service.get_session(
        app_name=APP_NAME, user_id="player", session_id=sid
    )
    return dict(sess.state), tokens


def run_turn(case: dict[str, Any], session: dict[str, Any], student_message: str) -> dict[str, Any]:
    """ADK pipeline for one turn. Mutates `session`, returns the new turn dict."""
    ai = store.ai_packet(case, session["side"])
    cstate = concession.ensure(session.setdefault("concession_state", concession.init_state()))
    plan = concession.plan_turn(cstate, student_message)

    seed = {
        "ai_side": ai["side"],
        "ai_packet": _render_packet(ai),
        "transcript": _render_transcript(session),
        "ai_notes": _render_memory(session),
        "hard_rules": plan["directive"],
        "student_message": student_message,
    }
    final_state, tokens = asyncio.run(_run(seed, student_message))

    directive = final_state.get("directive") or {}
    if not isinstance(directive, dict):
        directive = {"tactic": plan["phase"], "instruction": plan["directive"]}
    directive["phase"] = plan["phase"]

    cand_obj = final_state.get("cand") or {}
    candidates = cand_obj.get("candidates") if isinstance(cand_obj, dict) else None
    if not candidates:
        candidates = ["Let's keep talking and see if we can find terms that work."]

    sel = final_state.get("sel") or {}
    choice = sel.get("choice") if isinstance(sel, dict) else 0
    if not isinstance(choice, int) or not (0 <= choice < len(candidates)):
        choice = 0
    chosen = candidates[choice]
    note = (final_state.get("note") or "").strip() or "I'll stay guarded and watch them."

    turn_n = plan["turn_number"]
    session.setdefault("ai_memory", []).append({"turn": turn_n, "note": note})
    concession.record_turn(cstate, plan, demand_summary=chosen)

    turn = {
        "n": turn_n,
        "student": student_message,
        "adversary": chosen,
        "phase": plan["phase"],
        "directive": directive,
        "candidates": candidates,
        "selection": {"choice": choice, "chosen": chosen, "why": sel.get("why", "") if isinstance(sel, dict) else "", "forecasts": []},
        "note": note,
        "tokens": tokens,
    }
    session.setdefault("turns", []).append(turn)
    return turn
