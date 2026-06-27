"use client";

import { useEffect, useState } from "react";
import { listSessions, getReport, deleteSession, type SessionCard, type Report } from "@/lib/api";
import Overlay from "./Overlay";
import ReportView from "./ReportView";

export default function HistoryOverlay({ onClose }: { onClose: () => void }) {
  const [cards, setCards] = useState<SessionCard[] | null>(null);
  const [openSid, setOpenSid] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSessions().then(setCards).catch(() => setError("Could not load history."));
  }, []);

  async function open(card: SessionCard) {
    if (card.status !== "ended") return;
    setOpenSid(card.id);
    setReport(null);
    try {
      setReport(await getReport(card.id));
    } catch {
      setError("Could not load that report.");
    }
  }

  async function remove(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    setCards((cs) => (cs ? cs.filter((c) => c.id !== id) : cs));
    try {
      await deleteSession(id);
    } catch {
      setError("Could not delete that simulation.");
    }
  }

  if (openSid && report) {
    return (
      <Overlay title="Past Simulation" onClose={onClose} wide>
        <button className="btn btn-secondary" style={{ marginBottom: 12 }} onClick={() => { setOpenSid(null); setReport(null); }}>
          ← Back to list
        </button>
        <ReportView sid={openSid} report={report} />
      </Overlay>
    );
  }

  return (
    <Overlay title="Previous Simulations" onClose={onClose} wide>
      <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
        Your current negotiation stays open underneath — browsing here won't end it.
      </p>
      {error && <p className="muted">{error}</p>}
      {!cards && !error && <p className="muted">Loading…</p>}
      {cards && cards.length === 0 && <p className="muted">No simulations yet.</p>}
      {cards?.map((c) => (
        <div
          key={c.id}
          className="hist-card"
          onClick={() => open(c)}
          style={{ cursor: c.status === "ended" ? "pointer" : "default" }}
        >
          <div>
            <div><b>{c.case_title}</b> <span className="tag" style={{ textTransform: "capitalize" }}>{c.side}</span></div>
            <div className="hc-meta">
              {new Date(c.created_at).toLocaleString()} · {c.turns} turns ·{" "}
              {c.status === "ended" ? "completed" : "in progress"}
            </div>
            {c.summary && <div style={{ fontSize: 13, marginTop: 4 }}>{c.summary}</div>}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {c.status === "ended" && <span className="muted">View →</span>}
            <button className="close-x" title="Delete" onClick={(e) => remove(e, c.id)}>×</button>
          </div>
        </div>
      ))}
    </Overlay>
  );
}
