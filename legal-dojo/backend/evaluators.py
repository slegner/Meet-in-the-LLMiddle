"""End-of-game coaching.

Pipeline:
  1. Splitter agent routes the transcript into a Legal brief and a Negotiation
     brief.
  2. Legal agent  <- legal brief.
  3. Negotiation agent <- negotiation brief.
  4. Perception agent <- the AI opponent's private per-turn notes.
  5. Criteria agent <- same Harvard-method negotiation expert, grading the
     student against the 6 principles from "What Makes a Good Negotiator",
     with verbatim transcript quotes per criterion.
  6. Summary paragraph.

No numeric scoring — each agent returns qualitative comments + weak spots.
"""
from __future__ import annotations

from typing import Any

import llm

# ---------------------------------------------------------------------------
# What Makes a Good Negotiator — the 6 criteria used for structured grading
# ---------------------------------------------------------------------------

_CRITERIA = [
    {
        "short": "Position accuracy",
        "title": "Pushing your position without overstating it",
        "full": (
            "Pushing your position without overstating it: advocating as forcefully "
            "as the facts and law actually support, while resisting the temptation to "
            "inflate claims, damages estimates, or threats beyond what you can credibly "
            "back up. Once the other side catches one exaggeration, they start "
            "discounting everything else you say."
        ),
    },
    {
        "short": "Case preparation",
        "title": "Knowing the facts and law and understanding the strengths and weaknesses of both your position and the other side's",
        "full": (
            "Knowing the facts and law and understanding the strengths and weaknesses "
            "of both your position and the other side's: knowing the documents, timeline, "
            "witness statements, and evidentiary record well enough that you're never "
            "surprised by something the other side raises. If opposing counsel mentions "
            "an email or a clause, you should already know it — not be hearing about it "
            "for the first time across the table."
        ),
    },
    {
        "short": "Interest-based thinking",
        "title": "Distinguishing stated positions from underlying interests",
        "full": (
            "Distinguishing stated positions from underlying interests: looking beyond "
            "what people say they want (positions) to understand why they want it "
            "(interests). By identifying underlying interests, negotiators can uncover "
            "common ground, generate creative alternatives, and reach solutions that "
            "satisfy the core needs of all parties rather than becoming stuck in "
            "positional deadlock."
        ),
    },
    {
        "short": "Concession discipline",
        "title": "Knowing when to make the first offer, how to sequence concessions, and how to avoid giving things away for nothing",
        "full": (
            "Knowing when to make the first offer, how to sequence concessions, and "
            "how to avoid giving things away for nothing: every compromise should be "
            "exchanged for something of equal value. Concessions should be gradual and "
            "strategic, showing flexibility without weakening your position. Never give "
            "something away for free — ask for a concession in return."
        ),
    },
    {
        "short": "Tactical flexibility",
        "title": "Switching between collaborative and competitive tactics depending on the counterpart and stakes",
        "full": (
            "Switching between collaborative (interest-based) and competitive "
            "(positional) tactics depending on the counterpart and stakes: when trust "
            "is important or long-term cooperation matters, focus on shared interests "
            "and value creation. When stakes are high or the counterpart is highly "
            "competitive, shift to a positional style and protect key demands. The "
            "skill lies in reading the situation early and moving fluidly between modes."
        ),
    },
    {
        "short": "Realistic expectations",
        "title": "Keeping expectations realistic and getting authority to move before you're at the table",
        "full": (
            "Keeping expectations realistic and getting authority to move before "
            "you're at the table: ground your targets in data and likely trade-offs "
            "rather than ideal outcomes. Know your walk-away limits, approved "
            "concessions, and decision boundaries in advance — this prevents "
            "'I need to check' moments that weaken your credibility."
        ),
    },
]


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
    criteria_list = "\n".join(f"  {i+1}. {c['short']}" for i, c in enumerate(_CRITERIA))
    return _evaluate(
        "You are a NEGOTIATION EXPERT (Harvard-method). Judge the trainee's "
        "negotiation performance specifically through the lens of these 6 principles:\n"
        f"{criteria_list}\n"
        "Name 2-3 of these principles by their short name in your comments and say "
        "concretely how the student performed on them. Weak spots should each name "
        "the relevant principle.",
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
# 5. Criteria checklist — Harvard-method expert grades against the 6 principles
# ---------------------------------------------------------------------------

def evaluate_criteria(case: dict[str, Any], session: dict[str, Any]) -> list[dict[str, Any]]:
    """Grade the student against the 6 negotiation principles, quoting the transcript."""
    system = (
        "You are a NEGOTIATION EXPERT (Harvard-method) grading a trainee against "
        "6 defined principles of effective negotiation. For each principle, find a "
        "specific moment in the transcript — quote the student's EXACT words with the "
        "turn number — then score it and give two sentences of specific feedback. "
        "Be honest: if the transcript is short or the principle was not tested, say so."
    )

    criteria_block = "\n\n".join(
        f"[{i+1}] {c['short']}\n{c['full']}"
        for i, c in enumerate(_CRITERIA)
    )

    prompt = (
        f"{_player_brief(case, session['side'])}\n\n"
        f"FULL TRANSCRIPT:\n{_full_transcript(session)}\n\n"
        f"THE 6 PRINCIPLES TO GRADE AGAINST:\n{criteria_block}\n\n"
        "For EACH of the 6 principles return one object. "
        "The 'quote' field must contain the student's verbatim words from the "
        "transcript (with turn number), followed by a dash and one sentence of "
        "context. If the principle was not demonstrated, pick the closest relevant "
        "moment or note the absence.\n\n"
        'Return JSON: {"criteria": ['
        '{"short_name": "...", "score": "strong|adequate|weak", '
        '"quote": "Turn N, STUDENT: \'...\' — context sentence", '
        '"feedback": "2 sentences"}, ...6 items]}'
    )

    data = llm.generate_json(prompt, system=system, role="evaluator", temperature=0.5)
    items = (data.get("criteria") if isinstance(data, dict) else None) or []

    # Normalise and fill gaps so the frontend always gets exactly 6 items
    result = []
    for i, c in enumerate(_CRITERIA):
        raw = items[i] if i < len(items) else {}
        score = str(raw.get("score", "adequate"))
        if score not in ("strong", "adequate", "weak"):
            score = "adequate"
        result.append({
            "short_name": c["title"],
            "score": score,
            "quote": str(raw.get("quote", "")).strip() or "Not clearly demonstrated in this session.",
            "feedback": str(raw.get("feedback", "")).strip() or "Play more turns to generate specific feedback.",
        })
    return result


# ---------------------------------------------------------------------------
# 6. Deal assessment (only when the student accepted a deal)
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
# Weak-spot persistence analysis
# ---------------------------------------------------------------------------

def analyse_weak_spots(current_spots: list[str], profile: dict[str, Any]) -> dict[str, Any]:
    """Classify current session weak spots against the historical player profile.

    Returns:
        persistent: spots that appeared before (recurring issues)
        new:        spots seen for the first time this session
        improved:   historical spots NOT triggered this session (possible progress)
    """
    observations = profile.get("observations", [])
    if not observations and not current_spots:
        return {"persistent": [], "new": [], "improved": []}
    if not observations:
        return {"persistent": [], "new": current_spots, "improved": []}
    if not current_spots:
        return {"persistent": [], "new": [], "improved": [o["text"] for o in observations]}

    obs_texts = [o["text"] for o in observations]
    system = "You are an analyst comparing negotiation coaching reports across sessions."
    prompt = (
        "HISTORICAL weak spots (from previous sessions, may be paraphrased differently):\n"
        + "\n".join(f"  [{i}] {t}" for i, t in enumerate(obs_texts))
        + "\n\nCURRENT session weak spots:\n"
        + "\n".join(f"  - {s}" for s in current_spots)
        + "\n\nFor each CURRENT spot, decide if it describes the same underlying weakness "
        "as one of the historical spots (even if worded differently). "
        "Then list which historical spots were NOT matched by any current spot "
        "(possible signs of improvement). "
        'Return JSON: {"persistent": [{"text": "...", "history_index": <int>}], '
        '"new": ["..."], "improved_indices": [<int>]}'
    )
    data = llm.generate_json(prompt, system=system, role="evaluator", temperature=0.2, fallback={})
    if not isinstance(data, dict):
        return {"persistent": [], "new": current_spots, "improved": []}

    persistent = []
    for p in data.get("persistent") or []:
        text = str(p.get("text", "")).strip()
        if text:
            persistent.append(text)

    new = [str(s).strip() for s in (data.get("new") or []) if str(s).strip()]

    improved = []
    for idx in data.get("improved_indices") or []:
        if isinstance(idx, int) and 0 <= idx < len(obs_texts):
            improved.append(obs_texts[idx])

    return {"persistent": persistent, "new": new, "improved": improved}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def compose_report(case: dict[str, Any], session: dict[str, Any],
                   accepted: bool = False) -> dict[str, Any]:
    import player_memory as _pm
    profile = _pm.load_profile()

    briefs = split_material(case, session)
    legal = evaluate_legal(case, session, briefs["legal"])
    negotiation = evaluate_negotiation(case, session, briefs["negotiation"])
    perception = evaluate_perception(case, session)
    criteria = evaluate_criteria(case, session)
    deal = evaluate_deal(case, session) if accepted else None

    all_weak = legal["weak_spots"] + negotiation["weak_spots"] + perception["weak_spots"]
    weak_spot_analysis = analyse_weak_spots(all_weak, profile)
    summary = _summarize(case, session, legal, negotiation, perception, deal, weak_spot_analysis)

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
        "criteria": criteria,
        "weak_spots": all_weak,
        "weak_spot_analysis": weak_spot_analysis,
    }


def _summarize(case, session, legal, negotiation, perception, deal=None, wsa=None) -> str:
    deal_line = ""
    if deal:
        deal_line = f"The student accepted a deal ({deal['verdict'].replace('_', ' ')}): {deal['deal_terms']}\n"
    persistent_line = ""
    if wsa and wsa.get("persistent"):
        spots = "; ".join(wsa["persistent"])
        persistent_line = f"Recurring issues (appeared in previous sessions too): {spots}\n"
    improved_line = ""
    if wsa and wsa.get("improved"):
        spots = "; ".join(wsa["improved"])
        improved_line = f"Possible signs of improvement (not triggered this session): {spots}\n"
    prompt = (
        f"Case: {case['title']}. The student played {session['side']}.\n"
        f"{deal_line}"
        f"Legal feedback: {legal['comments']}\n"
        f"Negotiation feedback: {negotiation['comments']}\n"
        f"How the opponent perceived them: {perception['comments']}\n"
        f"{persistent_line}{improved_line}\n"
        "Write a single warm, candid coaching paragraph (3-4 sentences). "
        "If there are recurring issues, call them out directly — these need priority attention. "
        "If something improved compared to previous sessions, acknowledge it. "
        "End with the single most important thing to work on next."
    )
    out = llm.llm_generate(prompt, role="evaluator", temperature=0.6)
    return (out or "").strip() or "The negotiation has concluded."


def short_summary(report: dict[str, Any]) -> str:
    text = report.get("summary", "").strip().split(". ")
    return (text[0][:140] + ("…" if len(text[0]) > 140 else "")) if text and text[0] else "Negotiation complete."
