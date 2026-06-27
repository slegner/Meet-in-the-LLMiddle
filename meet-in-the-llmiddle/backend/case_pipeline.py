"""Case generation pipeline: Search → Parse → Build Sides → Assemble → Sanitise Names.

Usage:
    from case_pipeline import generate_case
    case = generate_case("employment tribunal unfair dismissal UK")
    # Returns a dict matching the case JSON schema ready to save.
"""
from __future__ import annotations

import json as _json
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

    data = llm.generate_json(prompt, system=system, role="case_parser", temperature=0.3)
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

    data = llm.generate_json(prompt, system=system, role="case_parser", temperature=0.5)
    _require(data, slug1, slug2, label="Side Builder")
    return data


# ---------------------------------------------------------------------------
# Stage 3 — Assembler (pure code)
# ---------------------------------------------------------------------------

def assemble_case(
    parsed: dict[str, Any],
    sides: dict[str, Any],
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """Merge parser + side builder output into the case JSON schema."""
    title   = parsed.get("title", "Untitled Case")
    case_id = _slugify(title)
    return {
        "id":               case_id,
        "title":            title,
        "summary":          parsed.get("summary", ""),
        "background":       parsed.get("background", ""),
        "relevant_law":     parsed.get("relevant_law", []),
        "legal_context":    "",   # populated by enrich_legal_context if Perplexity is available
        "shared_documents": parsed.get("shared_documents", []),
        "sources":          sources or [],
        "sides":            sides,
    }


# ---------------------------------------------------------------------------
# Stage 4 — Name Sanitiser Agent
# ---------------------------------------------------------------------------


def sanitise_names(case: dict[str, Any], theme: str = "") -> dict[str, Any]:
    """Scan the assembled case for real human names and replace with fictional ones.

    Args:
        case:  The assembled case dict (post-assemble_case).
        theme: Optional flavour hint so replacements fit the setting,
               e.g. "solar system / planet names" for a space parody.

    Returns:
        The case dict with all real person names swapped out.
    """
    case_text = _json.dumps(case, ensure_ascii=False)

    theme_hint = (
        f"\nFictional name THEME: {theme}. "
        "All replacement names must feel at home in this setting."
        if theme else ""
    )

    system = (
        "You are a PRIVACY EDITOR for a legal training simulation. "
        "Find every real human person's name in the supplied case JSON and "
        "replace it with a clearly fictional alternative. "
        "Do NOT change: party role labels (e.g. 'the employer', 'the tenant'), "
        "organisation names, place names, or the names of legal instruments, "
        "statutes, or court cases. "
        "ONLY replace individual people's personal names "
        "(first name + surname, or a standalone surname that refers to a named person)."
    )

    prompt = (
        f"CASE JSON:\n{case_text}\n\n"
        f"Identify every real human person's name in this text.{theme_hint}\n\n"
        "Return a JSON object mapping each real name string to its fictional replacement. "
        "If no real names are found return an empty object {}.\n\n"
        "Rules:\n"
        "- Include BOTH the full 'First Last' form AND the bare 'Last' form "
        "  if the surname appears alone anywhere in the text.\n"
        "- One person → one consistent fictional identity throughout.\n"
        "- Fictional names must sound like plausible names but be clearly invented.\n"
        "- Do NOT flag slugs, role labels, party names, or organisations.\n\n"
        'Example output: {"John Smith": "Orion Vega", "Smith": "Vega"}'
    )

    replacements = llm.generate_json(
        prompt, system=system, role="case_parser", temperature=0.3, fallback={}
    )

    if not replacements or not isinstance(replacements, dict):
        return case

    # Apply longest-match-first so "John Smith" is caught before "Smith"
    case_str = _json.dumps(case, ensure_ascii=False)
    for real, fictional in sorted(replacements.items(), key=lambda x: -len(x[0])):
        if real and fictional and isinstance(real, str) and isinstance(fictional, str):
            case_str = case_str.replace(real, fictional)

    try:
        return _json.loads(case_str)
    except Exception:
        return case  # if JSON breaks for any reason, return the unsanitised version


# ---------------------------------------------------------------------------
# Stage 5 — Legal Context Enrichment (Perplexity)
# ---------------------------------------------------------------------------

def enrich_legal_context(case: dict[str, Any]) -> dict[str, Any]:
    """Use Perplexity to fetch real legal content for the laws cited in the case.

    Stores the result in case["legal_context"] and appends any new source URLs.
    Silently skips if PERPLEXITY_API_KEY is not set or if the call fails —
    the case is fully playable without this enrichment.
    """
    relevant_law = case.get("relevant_law", [])
    if not relevant_law:
        return case

    try:
        law_list = ", ".join(relevant_law[:6])
        query = (
            f"Legal research for a negotiation case: '{case.get('title', '')}'. "
            f"Explain the following legal provisions in detail — what they say, "
            f"the key obligations and procedures they impose, and how they have "
            f"been interpreted or applied in practice: {law_list}"
        )
        result = search_perplexity(query, max_chars=5000)
        case["legal_context"] = result["text"]
    except Exception:
        pass  # non-fatal — case still fully usable without enrichment

    return case


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_case(query: str) -> dict[str, Any]:
    """Full pipeline: search → parse → build sides → assemble → sanitise names.

    Args:
        query: Natural language description of the kind of case to find
               (e.g. 'employment tribunal unfair dismissal UK').

    Returns:
        Case dict matching the existing case JSON schema, ready to save.
    """
    result  = search_perplexity(query)
    raw     = result["text"]
    sources = result.get("citations", [])
    parsed  = parse_case(raw)
    sides   = build_sides(parsed)
    case    = assemble_case(parsed, sides, sources=sources)
    case    = sanitise_names(case)
    return enrich_legal_context(case)


def generate_case_from_text(raw_text: str) -> dict[str, Any]:
    """Pipeline starting from existing text (no search step)."""
    parsed = parse_case(raw_text)
    sides  = build_sides(parsed)
    case   = assemble_case(parsed, sides)
    case   = sanitise_names(case)
    return enrich_legal_context(case)


def generate_parody_case(
    raw_text: str,
    substitutions: dict[str, str],
) -> dict[str, Any]:
    """Generate a playable case from real source text with fictional substitutions.

    The legal/negotiation structure is preserved faithfully; only names, places,
    and entities are replaced according to the substitution map.  A Name Sanitiser
    pass runs afterwards to catch any real person names the parser missed.

    Args:
        raw_text: Full text of the real case or document.
        substitutions: Mapping of real → fictional names,
                       e.g. {"UK": "Pluto", "EU": "The Solar System"}.
    """
    sub_instruction = ""
    theme = ""
    if substitutions:
        lines = "\n".join(f"  {k} → {v}" for k, v in substitutions.items())
        sub_instruction = (
            "\n\nFICTIONAL SUBSTITUTIONS — apply ALL of the following throughout "
            "your entire output. Use ONLY the fictional names; never use the real ones.\n"
            f"{lines}\n"
            "Keep every legal argument, negotiation pressure point, BATNA, and "
            "strategic dynamic faithful to the real case — only the names change."
        )
        # Derive a theme hint from the substitution values for the name sanitiser
        theme = ", ".join(substitutions.values())

    parsed = parse_case(raw_text + sub_instruction)
    sides  = build_sides(parsed)
    case   = assemble_case(parsed, sides)
    case   = sanitise_names(case, theme=theme)
    return enrich_legal_context(case)
