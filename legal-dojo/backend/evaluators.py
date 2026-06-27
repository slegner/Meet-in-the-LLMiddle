"""End-of-game coaching.

Pipeline:
  1. Splitter agent routes the transcript into a Legal brief and a Negotiation
     brief.
  2. Legal agent  <- legal brief.
  3. Negotiation agent <- negotiation brief.
  4. Perception agent <- the AI opponent's private per-turn notes. This is NOT
     "your client" — it is *how the opponent perceived you* (confidence, tells,
     trust), e.g. "this person didn't seem sure of their position".
  5. Summary paragraph.

No numeric scoring — each agent returns qualitative comments + weak spots.
"""
from __future__ import annotations

from typing import Any

import llm


def _full_transcript(session: dict[str, Any]) -> str:
    """Student turns + AI replies (no private notes — used by the splitter)."""
    lines = []
    for t in session.get("turns", []):
        lines.append(f"Turn {t['n']}")
        lines.append(f"  STUDENT: {t['student']}")
        lines.append(f"  OPPONENT: {t['adversary']}")
    return "\n".join(lines) if lines else "(no turns were played)"


def _ai_notes_text(session: dict[str, Any]) -> str:
    notes = session.get("ai_memory", [])
    if not notes:
        return "(the opponent recorded no private notes)"
    return "\n".join(f"  Turn {n['turn']}: {n['note']}" for n in notes)


def _player_brief(case: dict[str, Any], side: str) -> str:
    s = case["sides"][side]
    return f"The STUDENT played the {side.upper()} side. Goal: {s['goal']} BATNA: {s['batna']}"


# ---------------------------------------------------------------------------
# 1. Splitter — route the transcript into focused briefs
# ---------------------------------------------------------------------------

def split_material(case: dict[str, Any], session: dict[str, Any]) -> dict[str, str]:
    system = (
        "You are a ROUTING ANALYST. You read a legal negotiation transcript and "
        "separate the student's performance into two focused briefs: one about "
        "LEGAL substance (arguments, clauses, statutes, documents, accuracy) and "
        "one about NEGOTIATION TACTICS (anchoring, concessions, leverage, BATNA, "
        "composure, information control). Quote concrete moments."
    )
    prompt = (
        f"{_player_brief(case, session['side'])}\n\n"
        f"TRANSCRIPT:\n{_full_transcript(session)}\n\n"
        "Return JSON: {\"legal\": \"<brief of the legally-relevant moments>\", "
        "\"negotiation\": \"<brief of the tactical moments>\"}"
    )
    data = llm.generate_json(prompt, system=system, role="evaluator", temperature=0.4)
    if not isinstance(data, dict):
        data = {}
    return {
        "legal": str(data.get("legal", "")).strip() or _full_transcript(session),
        "negotiation": str(data.get("negotiation", "")).strip() or _full_transcript(session),
    }


# ---------------------------------------------------------------------------
# 2-4. The three evaluators
# ---------------------------------------------------------------------------

def _evaluate(persona_system: str, header: str, material: str) -> dict[str, Any]:
    prompt = (
        f"{header}\n\nMATERIAL TO ASSESS:\n{material}\n\n"
        "Assess ONLY the student's performance, specifically and constructively, "
        "referencing concrete moments. Return JSON: "
        '{"comments": "<2-4 sentences>", "weak_spots": ["<short>", "<short>"]}'
    )
    data = llm.generate_json(prompt, system=persona_system, role="evaluator", temperature=0.6)
    if not isinstance(data, dict):
        data = {}
    return {
        "comments": str(data.get("comments", "")).strip() or "No specific feedback generated.",
        "weak_spots": [str(w) for w in data.get("weak_spots", []) if str(w).strip()],
    }


def evaluate_legal(case, session, legal_brief):
    return _evaluate(
        "You are a senior LITIGATION SOLICITOR reviewing a trainee. Judge the "
        "strength and accuracy of their legal arguments and use of the clauses "
        "and documents.",
        _player_brief(case, session["side"]),
        legal_brief,
    )


def evaluate_negotiation(case, session, negotiation_brief):
    return _evaluate(
        "You are a NEGOTIATION EXPERT (Harvard-method). Judge the trainee's "
        "anchoring, concession discipline, use of leverage and BATNA, information "
        "control, and composure against pressure tactics.",
        _player_brief(case, session["side"]),
        negotiation_brief,
    )


def evaluate_perception(case, session):
    """How the AI opponent perceived the student — built from its private notes."""
    return _evaluate(
        "You ARE the opposing negotiator, debriefing privately on how you read "
        "the other side as a person across the negotiation: their confidence, "
        "composure, tells, whether you trusted them, and what they accidentally "
        "revealed. Speak in the second person to the student ('you came across "
        "as…'). Be candid and specific.",
        f"{_player_brief(case, session['side'])}\nThese are YOUR (the opponent's) private notes, turn by turn:",
        _ai_notes_text(session),
    )


# ---------------------------------------------------------------------------
# 5. Deal assessment (only when the student accepted a deal)
# ---------------------------------------------------------------------------

def evaluate_deal(case: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    """Compare the accepted deal to the student's BATNA and stated goal."""
    side = session["side"]
    s = case["sides"][side]
    system = (
        "You are a DEAL ASSESSMENT EXPERT. The student has just accepted a negotiated "
        "deal. Read the transcript and identify the final agreed terms, then judge "
        "whether the outcome is above, at, or below the student's BATNA."
    )
    prompt = (
        f"Case: {case['title']}\n"
        f"Student's side: {side.upper()}\n"
        f"Student's goal: {s['goal']}\n"
        f"Student's BATNA: {s['batna']}\n\n"
        f"TRANSCRIPT:\n{_full_transcript(session)}\n\n"
        "Based on the final exchanges, identify the key terms that were agreed and "
        "assess the outcome. Return JSON:\n"
        '{"verdict": "above_batna|at_batna|below_batna", '
        '"deal_terms": "<1-2 sentences summarising what was agreed>", '
        '"comments": "<2-3 sentences: how the deal compares to the BATNA and goal, '
        'and what the student could have pushed for>"}'
    )
    data = llm.generate_json(prompt, system=system, role="evaluator", temperature=0.4)
    if not isinstance(data, dict):
        data = {}
    verdict = str(data.get("verdict", "at_batna"))
    if verdict not in ("above_batna", "at_batna", "below_batna"):
        verdict = "at_batna"
    return {
        "verdict": verdict,
        "deal_terms": str(data.get("deal_terms", "Terms not clearly identified.")).strip(),
        "comments": str(data.get("comments", "")).strip() or "No deal assessment generated.",
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def compose_report(case: dict[str, Any], session: dict[str, Any],
                   accepted: bool = False) -> dict[str, Any]:
    briefs = split_material(case, session)
    legal = evaluate_legal(case, session, briefs["legal"])
    negotiation = evaluate_negotiation(case, session, briefs["negotiation"])
    perception = evaluate_perception(case, session)
    deal = evaluate_deal(case, session) if accepted else None

    all_weak = legal["weak_spots"] + negotiation["weak_spots"] + perception["weak_spots"]
    summary = _summarize(case, session, legal, negotiation, perception, deal)

    return {
        "case_title": case["title"],
        "side": session["side"],
        "turns": len(session.get("turns", [])),
        "tokens_used": sum(t.get("tokens", 0) for t in session.get("turns", [])),
        "accepted": accepted,
        "deal": deal,
        "summary": summary,
        "legal": legal,
        "negotiation": negotiation,
        "perception": perception,
        "weak_spots": all_weak,
    }


def _summarize(case, session, legal, negotiation, perception, deal=None) -> str:
    deal_line = ""
    if deal:
        deal_line = f"The student accepted a deal ({deal['verdict'].replace('_', ' ')}): {deal['deal_terms']}\n"
    prompt = (
        f"Case: {case['title']}. The student played {session['side']}.\n"
        f"{deal_line}"
        f"Legal feedback: {legal['comments']}\n"
        f"Negotiation feedback: {negotiation['comments']}\n"
        f"How the opponent perceived them: {perception['comments']}\n\n"
        "Write a single warm, candid coaching paragraph (3-4 sentences) "
        "summarising how the student did and the one thing to work on next."
    )
    out = llm.llm_generate(prompt, role="evaluator", temperature=0.6)
    return (out or "").strip() or "The negotiation has concluded."


def short_summary(report: dict[str, Any]) -> str:
    text = report.get("summary", "").strip().split(". ")
    return (text[0][:140] + ("…" if len(text[0]) > 140 else "")) if text and text[0] else "Negotiation complete."
