"use client";

import { type CriterionResult, type Report, type WeakSpotAnalysis, reportPdfUrl } from "@/lib/api";

const SCORE_STYLE: Record<CriterionResult["score"], { label: string; color: string; bg: string }> = {
  strong:   { label: "✓ Strong",   color: "#0a2010", bg: "var(--good)" },
  adequate: { label: "~ Adequate", color: "#2a1f05", bg: "var(--accent)" },
  weak:     { label: "✗ Weak",     color: "#2a0a0a", bg: "var(--danger)" },
};

function ScoreBadge({ score }: { score: CriterionResult["score"] }) {
  const s = SCORE_STYLE[score] ?? SCORE_STYLE.adequate;
  return (
    <span style={{
      background: s.bg, color: s.color,
      borderRadius: 5, padding: "2px 9px",
      fontSize: 11, fontWeight: 700, whiteSpace: "nowrap",
    }}>
      {s.label}
    </span>
  );
}

const VERDICT_STYLE: Record<string, { label: string; color: string; bg: string }> = {
  above_batna: { label: "Above BATNA — strong outcome", color: "#0a2010", bg: "var(--good)" },
  at_batna:    { label: "At BATNA — acceptable outcome", color: "#2a1f05", bg: "var(--accent)" },
  below_batna: { label: "Below BATNA — you should have walked away", color: "#2a0a0a", bg: "var(--danger)" },
};

function WeakSpotSection({ spots, analysis }: { spots: string[]; analysis?: WeakSpotAnalysis }) {
  const persistent = new Set(analysis?.persistent ?? []);
  const improved = analysis?.improved ?? [];
  const hasHistory = persistent.size > 0 || improved.length > 0;

  return (
    <div className="eval">
      <h3>Weak Spots to Work On</h3>
      {spots.length === 0 && !hasHistory && <p className="muted">None flagged.</p>}

      {spots.map((w, i) => {
        const isRecurring = persistent.has(w);
        return (
          <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 8 }}>
            <div className="weak" style={{ flex: 1, margin: 0 }}>{w}</div>
            {isRecurring && (
              <span style={{
                background: "var(--danger)",
                color: "#2a0a0a",
                borderRadius: 5,
                padding: "2px 8px",
                fontSize: 11,
                fontWeight: 700,
                whiteSpace: "nowrap",
                alignSelf: "center",
              }}>
                Recurring
              </span>
            )}
          </div>
        );
      })}

      {improved.length > 0 && (
        <div style={{ marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
          <div style={{ fontWeight: 700, fontSize: 13, color: "var(--good)", marginBottom: 6 }}>
            Signs of improvement this session
          </div>
          {improved.map((w, i) => (
            <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 6 }}>
              <span style={{ color: "var(--good)", fontSize: 14, lineHeight: 1 }}>✓</span>
              <span style={{ fontSize: 14, color: "var(--muted)" }}>{w}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

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
        <h3>👁 How Your Opponent Saw You</h3>
        <p style={{ margin: 0 }}>{report.perception.comments}</p>
      </div>
      <div className="eval">
        <h3>⚖️ Legal Review</h3>
        <p style={{ margin: 0 }}>{report.legal.comments}</p>
      </div>
      <div className="eval">
        <h3>🤝 Negotiation Expert</h3>
        <p style={{ margin: 0 }}>{report.negotiation.comments}</p>
      </div>

      {report.criteria && report.criteria.length > 0 && (
        <div className="eval">
          <h3>📋 Negotiator&apos;s Checklist</h3>
          {report.criteria.map((c, i) => (
            <div key={i} style={{
              paddingBottom: 14,
              marginBottom: 14,
              borderBottom: i < report.criteria!.length - 1 ? "1px solid var(--border)" : "none",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                <span style={{ fontWeight: 700, fontSize: 14 }}>{c.short_name}</span>
                <ScoreBadge score={c.score} />
              </div>
              <p style={{ margin: "0 0 5px", fontStyle: "italic", fontSize: 13, color: "var(--muted)" }}>
                {c.quote}
              </p>
              <p style={{ margin: 0, fontSize: 13 }}>{c.feedback}</p>
            </div>
          ))}
        </div>
      )}

      <WeakSpotSection spots={report.weak_spots} analysis={report.weak_spot_analysis} />

      <a className="btn" href={reportPdfUrl(sid)} target="_blank" rel="noreferrer">
        ⬇ Download report (PDF)
      </a>
    </div>
  );
}
