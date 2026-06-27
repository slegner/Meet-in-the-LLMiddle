"""Case generation pipeline: Search → Parse → Build Sides → Assemble.

Usage:
    from case_pipeline import generate_case
    case = generate_case("employment tribunal unfair dismissal UK")
    # Returns a dict matching the case JSON schema ready to save.
"""
from __future__ import annotations

import re
from typing import Any

import llm
from case_search import search_perplexity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:60]


def _require(data: Any, *keys: str, label: str = "agent") -> None:
    if not isinstance(data, dict):
        raise ValueError(f"{label} returned non-dict: {str(data)[:200]}")
    for k in keys:
        if k not in data:
            raise ValueError(f"{label} response missing key '{k}': {str(data)[:300]}")


# ---------------------------------------------------------------------------
# Stage 1 — Case Parser Agent
# ---------------------------------------------------------------------------

def parse_case(raw_text: str) -> dict[str, Any]:
    """Extract structured case data from raw prose (search result or pasted text)."""
    system = (
        "You are a LEGAL CASE ANALYST who transforms real dispute descriptions into "
        "structured negotiation data for a training simulator. "
        "Extract information precisely; where something isn't stated, make a reasonable "
        "inference from context rather than leaving the field empty. "
        "Always identify exactly two distinct parties."
    )
    prompt = (
        f"RAW CASE TEXT:\n{raw_text}\n\n"
        "Extract the following JSON. "
        "Each party's 'slug' must be a short, lowercase, underscore-separated word "
        "(e.g. 'employer', 'employee', 'buyer', 'seller', 'tenant', 'landlord', "
        "'claimant', 'defendant').\n\n"
        'Return JSON with exactly this shape:\n'
        '{\n'
        '  "title": "Descriptive case title",\n'
        '  "summary": "One punchy sentence describing the core dispute",\n'
        '  "background": "2-3 paragraphs of factual background (narrative, not bullets)",\n'
        '  "parties": [\n'
        '    {"name": "Full party name", "role_description": "Who they are", "slug": "short_slug"},\n'
        '    {"name": "Full party name", "role_description": "Who they are", "slug": "short_slug"}\n'
        '  ],\n'
        '  "dispute": "What is the core thing being contested",\n'
        '  "legal_issues": ["Issue 1", "Issue 2"],\n'
        '  "interests": {\n'
        '    "<slug1>": ["primary interest", "secondary interest"],\n'
        '    "<slug2>": ["primary interest", "secondary interest"]\n'
        '  },\n'
        '  "batna": {\n'
        '    "<slug1>": "Best alternative if talks break down",\n'
        '    "<slug2>": "Best alternative if talks break down"\n'
        '  },\n'
        '  "watna": {\n'
        '    "<slug1>": "Worst-case outcome if talks break down",\n'
        '    "<slug2>": "Worst-case outcome if talks break down"\n'
        '  },\n'
        '  "hidden_info": {\n'
        '    "<slug1>": ["Fact only this party knows"],\n'
        '    "<slug2>": ["Fact only this party knows"]\n'
        '  },\n'
        '  "possible_concessions": {\n'
        '    "<slug1>": ["Could offer X in exchange for Y"],\n'
        '    "<slug2>": ["Could offer X in exchange for Y"]\n'
        '  },\n'
        '  "relevant_law": ["Statute 1", "Case 2"],\n'
        '  "shared_documents": [\n'
        '    {"name": "Document name", "summary": "What it says and why it matters"}\n'
        '  ]\n'
        '}'
    )

    data = llm.generate_json(prompt, system=system, role="evaluator", temperature=0.3)
    _require(data, "title", "parties", "background", label="Case Parser")

    parties = data.get("parties", [])
    if len(parties) < 2:
        raise ValueError(
            f"Case Parser could not identify two parties. Got: {parties}"
        )
    # Ensure slugs are clean
    for p in parties:
        p["slug"] = _slugify(p.get("slug") or p.get("name", "party"))
    return data


# ---------------------------------------------------------------------------
# Stage 2 — Side Builder Agent
# ---------------------------------------------------------------------------

def build_sides(parsed: dict[str, Any]) -> dict[str, Any]:
    """Build two fully playable sides from the parsed case structure."""
    parties = parsed["parties"]
    p1, p2 = parties[0], parties[1]
    slug1, slug2 = p1["slug"], p2["slug"]

    interests  = parsed.get("interests", {})
    batna      = parsed.get("batna", {})
    watna      = parsed.get("watna", {})
    hidden     = parsed.get("hidden_info", {})
    concessions = parsed.get("possible_concessions", {})

    system = (
        "You are a NEGOTIATION GAME DESIGNER creating a legal training simulation. "
        "Build rich, asymmetric roles: each side must have genuine leverage AND "
        "real vulnerabilities. Make the private facts and tactics concrete and "
        "specific — vague generalities make for bad gameplay."
    )
    prompt = (
        f"Case: {parsed['title']}\n"
        f"Background: {parsed.get('background', '')}\n"
        f"Dispute: {parsed.get('dispute', '')}\n"
        f"Legal issues: {', '.join(parsed.get('legal_issues', []))}\n"
        f"Relevant law: {', '.join(parsed.get('relevant_law', []))}\n\n"
        f"Party 1 — {p1['name']} (slug: {slug1}):\n"
        f"  Role: {p1['role_description']}\n"
        f"  Interests: {interests.get(slug1, [])}\n"
        f"  BATNA: {batna.get(slug1, '')}\n"
        f"  WATNA: {watna.get(slug1, '')}\n"
        f"  Hidden info they hold: {hidden.get(slug1, [])}\n"
        f"  Concessions they could make: {concessions.get(slug1, [])}\n\n"
        f"Party 2 — {p2['name']} (slug: {slug2}):\n"
        f"  Role: {p2['role_description']}\n"
        f"  Interests: {interests.get(slug2, [])}\n"
        f"  BATNA: {batna.get(slug2, '')}\n"
        f"  WATNA: {watna.get(slug2, '')}\n"
        f"  Hidden info they hold: {hidden.get(slug2, [])}\n"
        f"  Concessions they could make: {concessions.get(slug2, [])}\n\n"
        "Design two playable simulation roles. For EACH side produce:\n"
        "  role        — A second-person paragraph ('You are counsel for…') giving\n"
        "                context, the client's personality, and negotiation style hints.\n"
        "  goal        — Primary win condition (1 sentence, specific and measurable).\n"
        "  batna       — What this side does if talks fail entirely.\n"
        "  objectives  — 3-5 ordered priorities (list of strings).\n"
        "  private_facts — 3-6 items this side knows that the other doesn't.\n"
        f"                For the {slug2} side (the AI adversary) ALSO include:\n"
        "                  • 'Tactic: <bluff or pressure move they may use>'\n"
        "                  • 'Red line: <demand they will never accept>'\n"
        "                  • 'Style: <emotional register and escalation pattern>'\n\n"
        f"Return JSON with exactly the two slugs as keys:\n"
        f'{{\n'
        f'  "{slug1}": {{\n'
        f'    "role": "...", "goal": "...", "batna": "...",\n'
        f'    "objectives": ["..."], "private_facts": ["..."]\n'
        f'  }},\n'
        f'  "{slug2}": {{\n'
        f'    "role": "...", "goal": "...", "batna": "...",\n'
        f'    "objectives": ["..."], "private_facts": ["..."]\n'
        f'  }}\n'
        f'}}'
    )

    data = llm.generate_json(prompt, system=system, role="evaluator", temperature=0.5)
    _require(data, slug1, slug2, label="Side Builder")
    return data


# ---------------------------------------------------------------------------
# Stage 3 — Assembler (pure code)
# ---------------------------------------------------------------------------

def assemble_case(parsed: dict[str, Any], sides: dict[str, Any]) -> dict[str, Any]:
    """Merge parser + side builder output into the case JSON schema."""
    title   = parsed.get("title", "Untitled Case")
    case_id = _slugify(title)
    return {
        "id":               case_id,
        "title":            title,
        "summary":          parsed.get("summary", ""),
        "background":       parsed.get("background", ""),
        "shared_documents": parsed.get("shared_documents", []),
        "sides":            sides,
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_case(query: str) -> dict[str, Any]:
    """Full pipeline: search → parse → build sides → assemble.

    Args:
        query: Natural language description of the kind of case to find
               (e.g. 'employment tribunal unfair dismissal UK').

    Returns:
        Case dict matching the existing case JSON schema, ready to save.
    """
    raw    = search_perplexity(query)
    parsed = parse_case(raw)
    sides  = build_sides(parsed)
    return assemble_case(parsed, sides)


def generate_case_from_text(raw_text: str) -> dict[str, Any]:
    """Pipeline starting from existing text (no search step).

    Useful when you already have a case description or document.
    """
    parsed = parse_case(raw_text)
    sides  = build_sides(parsed)
    return assemble_case(parsed, sides)
