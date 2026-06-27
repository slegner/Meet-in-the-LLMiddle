"use client";

import { type Report, reportPdfUrl } from "@/lib/api";

const VERDICT_STYLE: Record<string, { label: string; color: string; bg: string }> = {
  above_batna: { label: "Above BATNA — strong outcome", color: "#0a2010", bg: "var(--good)" },
  at_batna:    { label: "At BATNA — acceptable outcome", color: "#2a1f05", bg: "var(--accent)" },
  below_batna: { label: "Below BATNA — you should have walked away", color: "#2a0a0a", bg: "var(--danger)" },
};

export default function ReportView({ sid, report }: { sid: string; report: Report }) {
  const verdict = report.deal ? VERDICT_STYLE[report.deal.verdict] ?? VERDICT_STYLE.at_batna : null;

  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        {report.case_title} · played as {report.side} · {report.turns} turns
        {report.tokens_used ? ` · ~${report.tokens_used.toLocaleString()} Gemini tokens used` : ""}
      </p>

      {/* Deal assessment — shown only when the player accepted a deal */}
      {report.accepted && report.deal && verdict && (
        <div style={{
          border: `2px solid ${verdict.bg}`,
          borderRadius: 10,
          padding: "14px 16px",
          marginBottom: 16,
          background: `color-mix(in srgb, ${verdict.bg} 12%, transparent)`,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <span style={{
              background: verdict.bg,
              color: verdict.color,
              borderRadius: 6,
              padding: "3px 12px",
              fontWeight: 700,
              fontSize: 13,
            }}>
              🤝 {verdict.label}
            </span>
          </div>
          <p style={{ margin: "0 0 6px", fontWeight: 600 }}>{report.deal.deal_terms}</p>
          <p style={{ margin: 0, color: "var(--muted)", fontSize: 14 }}>{report.deal.comments}</p>
        </div>
      )}

      <div className="eval">
        <h3>Summary</h3>
        <p style={{ margin: 0 }}>{report.summary}</p>
      </div>

      <div className="eval">
        <h3>⚖️ Legal Review</h3>
        <p style={{ margin: 0 }}>{report.legal.comments}</p>
      </div>
      <div className="eval">
        <h3>🤝 Negotiation Expert</h3>
        <p style={{ margin: 0 }}>{report.negotiation.comments}</p>
      </div>
      <div className="eval">
        <h3>👁 How Your Opponent Saw You</h3>
        <p style={{ margin: 0 }}>{report.perception.comments}</p>
      </div>

      <div className="eval">
        <h3>Weak Spots to Work On</h3>
        {report.weak_spots.length === 0 && <p className="muted">None flagged.</p>}
        {report.weak_spots.map((w, i) => (
          <div className="weak" key={i}>{w}</div>
        ))}
      </div>

      <a className="btn" href={reportPdfUrl(sid)} target="_blank" rel="noreferrer">
        ⬇ Download report (PDF)
      </a>
    </div>
  );
}
