"use client";

import { type Report, reportPdfUrl } from "@/lib/api";

export default function ReportView({ sid, report }: { sid: string; report: Report }) {
  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        {report.case_title} · played as {report.side} · {report.turns} turns
        {report.tokens_used ? ` · ~${report.tokens_used.toLocaleString()} Gemini tokens used` : ""}
      </p>

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
