"use client";

import { useEffect, useState } from "react";
import { getCaseFile, type CaseFile } from "@/lib/api";
import Overlay from "./Overlay";

export default function CaseFileOverlay({ sid, onClose }: { sid: string; onClose: () => void }) {
  const [cf, setCf] = useState<CaseFile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCaseFile(sid).then(setCf).catch(() => setError("Could not load the case file."));
  }, [sid]);

  return (
    <Overlay title="Case File" onClose={onClose}>
      {error && <p className="muted">{error}</p>}
      {!cf && !error && <p className="muted">Loading…</p>}
      {cf && (
        <>
          <p className="tag" style={{ textTransform: "capitalize" }}>You: {cf.side}</p>
          <div className="card"><h3>Background</h3><p style={{ margin: 0, fontSize: 14 }}>{cf.background}</p></div>
          <div className="card"><h3>Your Role</h3><p style={{ margin: 0, fontSize: 14 }}>{cf.role}</p></div>
          <div className="card"><h3>Your Goal</h3><p style={{ margin: 0, fontSize: 14 }}>{cf.goal}</p></div>
          <div className="card"><h3>Your BATNA</h3><p style={{ margin: 0, fontSize: 14 }}>{cf.batna}</p></div>
          <div className="card">
            <h3>Objectives</h3>
            <ul className="objectives">{cf.objectives.map((o, i) => <li key={i}>{o}</li>)}</ul>
          </div>
          <div className="card">
            <h3>Documents</h3>
            {cf.documents.map((d, i) => (
              <div className="doc" key={i}>
                <div className="doc-name">{d.name}</div>
                <div className="doc-summary">{d.summary}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </Overlay>
  );
}
