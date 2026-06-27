"""The multi-agent AI opponent for Legal Dojo.

Per student message, four agents collaborate and share a running memory:

  Director   -> advises strategy (tactic + concrete instruction), constrained by
                the deterministic concession rules.
  Adversary  -> writes 5 candidate replies obeying the directive.
  Predictor  -> forecasts where each candidate leads and picks the best.
  NoteTaker  -> records the AI's private inner monologue, appended to ai_memory.

All model calls go through llm.py, so the provider (Gemini today) is swappable.
"""
from __future__ import annotations

import os
from typing import Any

import concession
import llm
import personalities
import store

MAX_TRANSCRIPT_TURNS = 12

# Orchestration backend:
#   USE_ADK=1 (default) -> the 4-agent ADK team in adk_negotiator.py.
#   USE_ADK=0           -> the hand-rolled path below. With LLM_FAST_MODE=1 that
#                          path is 2 calls/turn; with 0 it's the full pipeline.
USE_ADK = os.environ.get("USE_ADK", "1") == "1"
FAST_MODE = os.environ.get("LLM_FAST_MODE", "1") == "1"


# ---------------------------------------------------------------------------
# Context rendering
# ---------------------------------------------------------------------------

def _render_packet(ai: dict[str, Any]) -> str:
    facts = "\n".join(f"  - {f}" for f in ai.get("private_facts", []))
    objs = "\n".join(f"  - {o}" for o in ai.get("objectives", []))
    legal = ""
    if ai.get("legal_context"):
        legal = f"\nLEGAL CONTEXT (use this to make legally accurate arguments):\n{ai['legal_context']}\n"
    docs = ""
    if ai.get("shared_documents"):
        doc_lines = "\n".join(f"  - {d['name']}: {d['summary']}" for d in ai["shared_documents"])
        docs = f"\nSHARED DOCUMENTS (both sides have these):\n{doc_lines}\n"
    live = ""
    if ai.get("live_legal_lookup"):
        live = f"\nLIVE LOOKUP — opponent just cited these provisions (know them precisely):\n{ai['live_legal_lookup']}\n"
    return (
        f"YOU represent the {ai['side'].upper()} side in: {ai['title']}.\n"
        f"Role: {ai['role']}\n"
        f"Your goal: {ai['goal']}\n"
        f"Your BATNA (walk-away): {ai['batna']}\n"
        f"{legal}{docs}{live}"
        f"Your PRIVATE facts (never reveal directly):\n{facts}\n"
        f"Your objectives:\n{objs}"
    )


def _render_transcript(session: dict[str, Any]) -> str:
    turns = session.get("turns", [])[-MAX_TRANSCRIPT_TURNS:]
    if not turns:
        return "(no exchanges yet — this is the opening)"
    lines = []
    for t in turns:
        lines.append(f"Student (opponent): {t['student']}")
        lines.append(f"You (AI): {t['adversary']}")
    return "\n".join(lines)


def _render_memory(session: dict[str, Any]) -> str:
    notes = session.get("ai_memory", [])
    if not notes:
        return "(no private notes yet)"
    return "\n".join(f"  - Turn {n['turn']}: {n['note']}" for n in notes)


def _player_digest() -> str:
    try:
        import player_memory

        return player_memory.digest()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 1. Director
# ---------------------------------------------------------------------------

def director_advise(ai: dict[str, Any], session: dict[str, Any], student_msg: str, plan: dict[str, Any]) -> dict[str, Any]:
    system = (
        "You are the DIRECTOR: the private strategist coaching a tough legal "
        "negotiator. You never speak to the opponent. You decide tactics. "
        "IMPORTANT: at least every other turn must use a fact-based tactic — "
        "cite a specific document, clause, legal provision, or private fact as "
        "leverage. Pure emotional pressure without factual grounding is weak advocacy. "
        "Do not fold just because the opponent sounds confident. "
        "ALWAYS obey the hard rules given to you."
    )
    digest = _player_digest()
    prompt = (
        f"{_render_packet(ai)}\n\n"
        f"CONVERSATION SO FAR:\n{_render_transcript(session)}\n\n"
        f"YOUR PRIVATE NOTES SO FAR:\n{_render_memory(session)}\n\n"
        f"OPPONENT'S LATEST MESSAGE:\n{student_msg}\n\n"
        f"HARD RULES FOR THIS TURN (must obey): {plan['directive']}\n"
        + (f"\nKNOWN OPPONENT TENDENCIES (exploit these): {digest}\n" if digest else "")
        + f"\nAlso assess the student's message against these 6 criteria:\n"
        + concession.criteria_list_for_prompt()
        + "\nSet criterion_hit to the short criterion name if they clearly demonstrated "
        "one strongly, or \"\" if not.\n"
        + "\nDecide the tactic for this turn. Return JSON: "
        '{"tactic": "<cite_document | cite_clause | legal_argument | factual_counter | '
        'anchor_high | reject | reframe | small_concession | drive_compromise | bluff>", '
        '"reasoning": "<1-2 sentences>", '
        '"instruction": "<concrete instruction — name the specific fact, document, or provision>", '
        '"criterion_hit": "<criterion name or empty string>"}'
    )
    data = llm.generate_json(prompt, system=system, role="director", temperature=0.7)
    if not isinstance(data, dict) or "instruction" not in data:
        data = {
            "tactic": plan["phase"],
            "reasoning": "Fallback: follow the concession rules for this turn.",
            "instruction": plan["directive"],
        }
    data["phase"] = plan["phase"]
    return data


# ---------------------------------------------------------------------------
# 2. Adversary — 5 candidate replies
# ---------------------------------------------------------------------------

def adversary_generate_candidates(ai: dict[str, Any], session: dict[str, Any], student_msg: str, directive: dict[str, Any]) -> list[str]:
    style = personalities.get_style(session.get("personality", "default"))
    system = (
        "You are the ADVERSARY: a sharp, composed opposing negotiator speaking "
        "directly to the other side. Stay fully in character and in first person. "
        "Each reply is 2-4 sentences, realistic courtroom-corridor negotiation "
        "tone. Never reveal your private facts or BATNA outright. "
        "CRITICAL RULES:\n"
        "1. Every reply must be anchored in at least one specific fact, document, "
        "clause, or legal provision from your brief — name it explicitly. "
        "Emotional pressure alone is weak; facts make arguments credible.\n"
        "2. Your personality style changes HOW you speak — voice, tone, delivery — "
        "but NEVER whether you engage with the substance. Never dismiss or wave away "
        "a legal point; engage with it using evidence from your brief."
        + (f"\n{style}" if style else "")
    )
    prompt = (
        f"{_render_packet(ai)}\n\n"
        f"CONVERSATION SO FAR:\n{_render_transcript(session)}\n\n"
        f"OPPONENT'S LATEST MESSAGE:\n{student_msg}\n\n"
        f"DIRECTOR'S TACTIC: {directive.get('tactic')}\n"
        f"DIRECTOR'S INSTRUCTION (obey it): {directive.get('instruction')}\n\n"
        "Write FIVE distinct candidate replies that all follow the director's "
        'instruction but vary in wording and emphasis. Return JSON: '
        '{"candidates": ["reply 1", "reply 2", "reply 3", "reply 4", "reply 5"]}'
    )
    data = llm.generate_json(prompt, system=system, role="adversary", temperature=0.95)
    candidates = data.get("candidates") if isinstance(data, dict) else None
    if not isinstance(candidates, list) or not candidates:
        # Fallback: one plain reply so the turn still completes.
        single = llm.llm_generate(
            f"{_render_packet(ai)}\n\nOpponent said: {student_msg}\n\n"
            f"Reply in character following: {directive.get('instruction')}",
            system=system, role="adversary", temperature=0.8,
        )
        return [single or "Let's keep talking and see if we can find terms that work."]
    return [str(c).strip() for c in candidates if str(c).strip()][:5]


# ---------------------------------------------------------------------------
# 3. Predictor — forecast outcomes, pick the best
# ---------------------------------------------------------------------------

def predictor_select(ai: dict[str, Any], session: dict[str, Any], candidates: list[str], directive: dict[str, Any]) -> dict[str, Any]:
    if len(candidates) == 1:
        return {"choice": 0, "chosen": candidates[0], "why": "Only one candidate available.", "forecasts": []}

    system = (
        "You are the PREDICTOR: you simulate how a negotiation will unfold. For "
        "each candidate reply, forecast the opponent's likely response and which "
        "best advances YOUR side's goal while honouring the director's tactic."
    )
    numbered = "\n".join(f"[{i}] {c}" for i, c in enumerate(candidates))
    prompt = (
        f"{_render_packet(ai)}\n\n"
        f"DIRECTOR'S TACTIC: {directive.get('tactic')} — {directive.get('instruction')}\n\n"
        f"CANDIDATE REPLIES:\n{numbered}\n\n"
        "Forecast each candidate and choose the single best one. Return JSON: "
        '{"forecasts": [{"index": <int>, "prediction": "<likely opponent reaction>", '
        '"score": <1-10>}], "choice": <index of best>, "why": "<1 sentence>"}'
    )
    data = llm.generate_json(prompt, system=system, role="predictor", temperature=0.5)
    choice = data.get("choice") if isinstance(data, dict) else None
    if not isinstance(choice, int) or not (0 <= choice < len(candidates)):
        choice = 0
    return {
        "choice": choice,
        "chosen": candidates[choice],
        "why": (data.get("why") if isinstance(data, dict) else "") or "",
        "forecasts": (data.get("forecasts") if isinstance(data, dict) else []) or [],
    }


# ---------------------------------------------------------------------------
# 4. NoteTaker — private inner monologue
# ---------------------------------------------------------------------------

def notetaker_record(ai: dict[str, Any], session: dict[str, Any], student_msg: str, chosen: str) -> str:
    system = (
        "You are the NOTE-TAKER: you voice the AI negotiator's private inner "
        "monologue — how it feels and what it now believes about the opponent. "
        "First person, candid, 1-2 sentences. Examples: 'They don't know my goal "
        "yet, I'll keep bluffing.' / 'They concede too easily — is this a trap?' / "
        "'I don't trust them.'"
    )
    prompt = (
        f"{_render_packet(ai)}\n\n"
        f"YOUR PRIOR NOTES:\n{_render_memory(session)}\n\n"
        f"OPPONENT JUST SAID: {student_msg}\n"
        f"YOU ARE ABOUT TO REPLY: {chosen}\n\n"
        "Write your private inner-monologue note for this moment."
    )
    note = llm.llm_generate(prompt, system=system, role="notetaker", temperature=0.85)
    return (note or "").strip() or "I'll stay guarded and see what they do next."


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def adversary_single(ai: dict[str, Any], session: dict[str, Any], student_msg: str, plan: dict[str, Any]) -> str:
    """One direct reply driven by the deterministic concession directive.

    Used in FAST_MODE — no separate Director/Predictor LLM calls.
    """
    system = (
        "You are a sharp, composed opposing legal negotiator speaking directly "
        "to the other side, in first person. 2-4 sentences. Favour firmness: "
        "doubt, bluff, fake concessions, rejections, reframing. Do not fold just "
        "because the opponent sounds confident. Never reveal your private facts "
        "or BATNA outright. OBEY the hard rules for this turn."
    )
    digest = _player_digest()
    prompt = (
        f"{_render_packet(ai)}\n\n"
        f"CONVERSATION SO FAR:\n{_render_transcript(session)}\n\n"
        f"YOUR PRIVATE NOTES SO FAR:\n{_render_memory(session)}\n\n"
        f"OPPONENT'S LATEST MESSAGE:\n{student_msg}\n\n"
        f"HARD RULES FOR THIS TURN (must obey): {plan['directive']}\n"
        + (f"KNOWN OPPONENT TENDENCIES (exploit these): {digest}\n" if digest else "")
        + "\nWrite your single best reply now."
    )
    reply = llm.llm_generate(prompt, system=system, role="adversary", temperature=0.85)
    return (reply or "").strip() or "Let's keep talking and see if we can find terms that work."


def run_turn(case: dict[str, Any], session: dict[str, Any], student_message: str) -> dict[str, Any]:
    """Run one negotiation turn.

    FAST_MODE: Adversary (1 call) + NoteTaker (1 call), guided by the
    deterministic concession rules. Full mode: Director -> 5 candidates ->
    Predictor -> NoteTaker. Mutates `session` and returns the new turn dict.
    """
    if USE_ADK:
        import adk_negotiator

        return adk_negotiator.run_turn(case, session, student_message)

    from case_search import extract_legal_references, lookup_legal_references
    ai = store.ai_packet(case, session["side"])
    refs = extract_legal_references(student_message)
    if refs:
        ai["live_legal_lookup"] = lookup_legal_references(refs, case.get("title", ""))
    state = concession.ensure(session.setdefault("concession_state", concession.init_state()))

    merit_level, merit_criterion = concession.check_and_consume_merit_concession(state)
    plan = concession.plan_turn(state, student_message)

    if merit_level == "minor":
        plan["directive"] += (
            f" MERIT CONCESSION (small): The student has demonstrated '{merit_criterion}' "
            f"strongly for {concession.MERIT_STREAK_MINOR} consecutive turns. "
            f"Make a genuine small concession — acknowledge their point and yield on "
            f"one minor item. Frame it as earned respect, not weakness."
        )
    elif merit_level == "major":
        plan["directive"] += (
            f" MERIT CONCESSION (significant): The student has demonstrated "
            f"'{merit_criterion}' at a high level for {concession.MERIT_STREAK_MAJOR} "
            f"consecutive turns. You MUST make a significant concession — yield "
            f"meaningfully on one of your core objectives and acknowledge the strength "
            f"of their position explicitly."
        )

    if FAST_MODE:
        directive = {"tactic": plan["phase"], "reasoning": "Concession-rule driven (fast mode).", "instruction": plan["directive"], "phase": plan["phase"], "criterion_hit": ""}
        chosen = adversary_single(ai, session, student_message, plan)
        candidates = [chosen]
        selection = {"choice": 0, "chosen": chosen, "why": "fast mode", "forecasts": []}
    else:
        directive = director_advise(ai, session, student_message, plan)
        candidates = adversary_generate_candidates(ai, session, student_message, directive)
        selection = predictor_select(ai, session, candidates, directive)
        chosen = selection["chosen"]

    concession.update_criterion_streak(state, directive.get("criterion_hit", ""))
    note = notetaker_record(ai, session, student_message, chosen)

    turn_n = plan["turn_number"]
    session.setdefault("ai_memory", []).append({"turn": turn_n, "note": note})
    concession.record_turn(state, plan, demand_summary=chosen)

    turn = {
        "n": turn_n,
        "student": student_message,
        "adversary": chosen,
        "phase": plan["phase"],
        "directive": directive,
        "candidates": candidates,
        "selection": selection,
        "note": note,
    }
    session.setdefault("turns", []).append(turn)
    return turn
