"""Render a finished session into a downloadable PDF (and a Markdown fallback).

Uses fpdf2 with the built-in core fonts, so text is sanitised to Latin-1 (the
em-dashes / curly quotes in our content are mapped to ASCII).
"""
from __future__ import annotations

from typing import Any

from fpdf import FPDF

_SUBS = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", "•": "-",
    "→": "->", "\xa3": "GBP ",
}


def _clean(text: str) -> str:
    s = str(text or "")
    for k, v in _SUBS.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


class _PDF(FPDF):
    def _write(self, text: str, h: float):
        # Always render at the left margin across the full effective page width,
        # and break overlong unbroken tokens (wrapmode="CHAR") so layout never
        # runs out of horizontal space.
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, h, _clean(text), new_x="LMARGIN", new_y="NEXT", wrapmode="CHAR")

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(150)
        self.set_x(self.l_margin)
        self.cell(self.epw, 6, "LEGAL DOJO - Coaching Report", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def h1(self, text: str):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(20)
        self._write(text, 8)
        self.ln(2)

    def h2(self, text: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(180, 130, 20)
        self._write(text, 7)
        self.set_text_color(20)

    def body(self, text: str):
        self.set_font("Helvetica", "", 10.5)
        self.set_text_color(30)
        self._write(text, 5.5)
        self.ln(1)

    def meta(self, text: str):
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(120)
        self._write(text, 5)
        self.set_text_color(30)


def build_report_pdf(case: dict[str, Any], session: dict[str, Any]) -> bytes:
    report = session.get("report") or {}
    notes = {n["turn"]: n["note"] for n in session.get("ai_memory", [])}

    pdf = _PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.h1(case["title"])
    pdf.meta(
        f"You played: {session.get('side')}  |  "
        f"Turns: {len(session.get('turns', []))}  |  "
        f"Date: {session.get('created_at', '')[:19]}"
    )
    pdf.ln(2)

    if report:
        pdf.h2("Summary")
        pdf.body(report.get("summary", ""))

        for key, title in (
            ("legal", "Legal Review"),
            ("negotiation", "Negotiation Expert"),
            ("perception", "How Your Opponent Saw You"),
        ):
            block = report.get(key, {})
            pdf.h2(title)
            pdf.body(block.get("comments", ""))
            for w in block.get("weak_spots", []):
                pdf.body(f"  - {w}")

    # Transcript with the AI's private notes.
    pdf.add_page()
    pdf.h2("Transcript (with the opponent's private notes)")
    for t in session.get("turns", []):
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(30)
        pdf._write(f"Turn {t['n']}", 5.5)
        pdf.body(f"You: {t['student']}")
        pdf.body(f"Opponent: {t['adversary']}")
        if t["n"] in notes:
            pdf.meta(f"AI private note: {notes[t['n']]}")
        pdf.ln(1)

    out = pdf.output()
    return bytes(out)


def build_transcript_md(case: dict[str, Any], session: dict[str, Any]) -> str:
    notes = {n["turn"]: n["note"] for n in session.get("ai_memory", [])}
    lines = [
        f"# Legal Dojo - {case['title']}",
        f"You played: {session.get('side')} | Turns: {len(session.get('turns', []))}",
        "",
    ]
    for t in session.get("turns", []):
        lines += [f"## Turn {t['n']}", f"**You:** {t['student']}", f"**Opponent:** {t['adversary']}"]
        if t["n"] in notes:
            lines.append(f"> _AI note:_ {notes[t['n']]}")
        lines.append("")
    return "\n".join(lines)
