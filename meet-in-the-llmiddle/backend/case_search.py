"""Search clients for sourcing real legal dispute cases.

Currently: Perplexity API (web-search-augmented LLM).
Planned: EU Cellar API (SPARQL + document fetch).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
PERPLEXITY_MODEL   = os.environ.get("PERPLEXITY_MODEL", "sonar-pro")
_PERPLEXITY_URL    = "https://api.perplexity.ai/chat/completions"


class CaseSearchError(RuntimeError):
    pass


def search_perplexity(query: str, max_chars: int = 8000) -> dict:
    """Ask Perplexity for a detailed factual account of a real legal dispute.

    Returns {"text": str, "citations": list[str]} where citations are the
    source URLs Perplexity used. Raises CaseSearchError on failure.
    """
    if not PERPLEXITY_API_KEY:
        raise CaseSearchError(
            "PERPLEXITY_API_KEY is not set in backend/.env — "
            "add it to enable case generation."
        )

    prompt = (
        f"Find and describe a real legal dispute or negotiation case involving: {query}.\n\n"
        "Provide a detailed, factual account that includes:\n"
        "1. The parties involved (names, roles, organisational context)\n"
        "2. The background and key facts of the dispute\n"
        "3. What each party wants and why — their interests and priorities\n"
        "4. The legal issues at stake and any relevant statutes, regulations, or case law\n"
        "5. Each party's best alternative if negotiations fail (BATNA)\n"
        "6. Any key documents, contracts, or evidence in the case\n"
        "7. Information that one side holds privately that the other doesn't know\n"
        "8. Possible concessions each side could make\n\n"
        "Cite real cases, rulings, or news reports where possible. "
        "Be specific and factual — this will be used to build a legal negotiation training scenario."
    )

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                _PERPLEXITY_URL,
                headers={
                    "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": PERPLEXITY_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 2000,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        raise CaseSearchError(f"Perplexity API returned {e.response.status_code}: {e.response.text[:300]}") from e
    except httpx.RequestError as e:
        raise CaseSearchError(f"Perplexity request failed: {e}") from e

    text = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])
    if citations:
        text += "\n\nSOURCES:\n" + "\n".join(f"- {c}" for c in citations[:8])

    return {"text": text[:max_chars], "citations": citations[:8]}


# ---------------------------------------------------------------------------
# Per-turn legal reference lookup
# ---------------------------------------------------------------------------

# Matches: "Article 50", "Article 50(3)", "Article 4.3 TEU", "Section 13(1)(b)",
#          "Schedule 2", "Clause 5", and named Acts/Directives/Treaties with a year.
_ARTICLE_RE = re.compile(
    r'\b(?:Article|Art\.?|Section|Sec\.?|Clause|Schedule|Para(?:graph)?)\s+'
    r'[\d]+(?:[.(][\d\w]+[).)]?)*'
    r'(?:\s+(?:TEU|TFEU|ECHR|of\s+the\s+[\w\s]{3,40}))?',
    re.IGNORECASE,
)
_ACT_RE = re.compile(
    r'\b(?:[A-Z][a-z]+\s+){1,6}(?:\([A-Za-z\s]+\)\s+)?(?:Act|Directive|Regulation|Treaty|Convention)\s+\d{4}\b'
)


def extract_legal_references(text: str) -> list[str]:
    """Return unique legal references found in `text`, capped at 5."""
    found: list[str] = []
    seen: set[str] = set()
    for m in _ARTICLE_RE.findall(text) + _ACT_RE.findall(text):
        key = m.strip().lower()
        if key and key not in seen:
            seen.add(key)
            found.append(m.strip())
    return found[:5]


def lookup_legal_references(refs: list[str], case_title: str = "") -> str:
    """Query Perplexity for the cited legal provisions. Returns "" on failure or no key."""
    if not refs or not PERPLEXITY_API_KEY:
        return ""
    ref_list = "; ".join(refs)
    context = f" in the context of '{case_title}'" if case_title else ""
    query = (
        f"Explain the following legal provisions{context}: {ref_list}. "
        "For each, state precisely what it says, what obligations or rights it creates, "
        "and any key interpretations. Be concise and accurate."
    )
    try:
        result = search_perplexity(query, max_chars=2000)
        return result["text"]
    except Exception:
        return ""
