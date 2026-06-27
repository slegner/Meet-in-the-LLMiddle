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
    <Overlay title="Case File" onClose={onClose} wide>
      {error && <p className="muted">{error}</p>}
      {!cf && !error && <p className="muted">Loading…</p>}
      {cf && (
        <div className="paper">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ margin: 0 }}>{cf.title}</h2>
            <span className="stamp">Counsel for {cf.side}</span>
          </div>
          <hr />
          <h3>Background</h3>
          <p>{cf.background}</p>
          <h3>Your Role</h3>
          <p>{cf.role}</p>
          <h3>Your Goal</h3>
          <p>{cf.goal}</p>
          <h3>Your BATNA</h3>
          <p>{cf.batna}</p>
          <h3>Objectives</h3>
          <ul className="objectives">{cf.objectives.map((o, i) => <li key={i}>{o}</li>)}</ul>
          <h3>Documents</h3>
          {cf.documents.map((d, i) => (
            <div className="doc" key={i} style={{ margin: "12px 0" }}>
              <div className="doc-name" style={{ fontWeight: 700 }}>{d.name}</div>
              <div className="doc-summary">{d.summary}</div>
            </div>
          ))}
        </div>
      )}
    </Overlay>
  );
}
