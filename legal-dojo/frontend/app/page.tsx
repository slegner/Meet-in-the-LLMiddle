"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  listCases,
  listPersonalities,
  getCase,
  generateCase,
  startSession,
  getSession,
  type CaseSummary,
  type CaseDetail,
  type Side,
  type Personality,
} from "@/lib/api";

const ACTIVE_KEY = "legaldojo_activeSid";

export default function StartPage() {
  const router = useRouter();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [side, setSide] = useState<Side | null>(null);
  const [personality, setPersonality] = useState("default");
  const [personalityList, setPersonalityList] = useState<Personality[]>([]);
  const [starting, setStarting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [genQuery, setGenQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [resume, setResume] = useState<{ sid: string; turns: number; side: Side } | null>(null);

  useEffect(() => {
    listCases()
      .then((cs) => {
        setCases(cs);
        if (cs[0]) return getCase(cs[0].id).then(setDetail);
      })
      .catch(() => setError("Could not reach the backend on :8000. Is it running?"));
    listPersonalities().then(setPersonalityList).catch(() => {});
  }, []);

  // Offer to resume an unfinished game if one is remembered.
  useEffect(() => {
    const sid = localStorage.getItem(ACTIVE_KEY);
    if (!sid) return;
    getSession(sid)
      .then((s) => {
        if (s.status === "ended") localStorage.removeItem(ACTIVE_KEY);
        else setResume({ sid, turns: s.turns.length, side: s.side });
      })
      .catch(() => localStorage.removeItem(ACTIVE_KEY));
  }, []);

  async function begin() {
    if (!detail || !side) return;
    setStarting(true);
    try {
      const res = await startSession(detail.id, side, personality);
      router.push(`/play?sid=${res.session_id}`);
    } catch {
      setError("Could not start the simulation.");
      setStarting(false);
    }
  }

  async function generate() {
    if (!genQuery.trim()) return;
    setGenerating(true);
    setError(null);
    try {
      const newCase = await generateCase(genQuery.trim());
      setCases((cs) => [...cs, { id: newCase.id, title: newCase.title, summary: newCase.summary }]);
      setDetail(newCase);
      setSide(null);
      setGenQuery("");
    } catch (e) {
      setError(`Case generation failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setGenerating(false);
    }
  }

  if (error) return <div className="container narrow"><p className="muted">{error}</p></div>;
  if (!detail) return <div className="container narrow"><p className="muted">Loading cases…</p></div>;

  const sides = Object.keys(detail.sides) as Side[];

  return (
    <div className="container" style={{ maxWidth: 1280 }}>
      {resume && (
        <section className="card" style={{ borderColor: "var(--accent)" }}>
          <div className="row-between">
            <div>
              <b>You have a negotiation in progress</b>
              <div className="muted" style={{ fontSize: 13 }}>
                as {resume.side} · {resume.turns} turns played
              </div>
            </div>
            <button className="btn" onClick={() => router.push(`/play?sid=${resume.sid}`)}>
              Resume →
            </button>
          </div>
        </section>
      )}

      <h1>New Simulation</h1>
      <p className="subtitle">Read the case file, choose your side, and negotiate against the AI.</p>

      <div style={{ display: "flex", gap: 10, marginBottom: 20, alignItems: "stretch" }}>
        <select
          style={{
            flex: "0 0 auto",
            padding: "8px 12px",
            borderRadius: 8,
            border: "1px solid var(--border)",
            background: "var(--panel)",
            color: "var(--fg)",
            fontSize: 14,
          }}
          value={detail.id}
          onChange={(e) => {
            const found = cases.find((c) => c.id === e.target.value);
            if (found) { getCase(found.id).then(setDetail); setSide(null); }
          }}
        >
          {cases.map((c) => (
            <option key={c.id} value={c.id}>{c.title}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder='Generate new case… e.g. "employment tribunal unfair dismissal UK"'
          value={genQuery}
          onChange={(e) => setGenQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && generate()}
          disabled={generating}
          style={{
            flex: 1,
            padding: "8px 12px",
            borderRadius: 8,
            border: "1px solid var(--border)",
            background: "var(--panel)",
            color: "var(--fg)",
            fontSize: 14,
          }}
        />
        <button
          className="btn"
          onClick={generate}
          disabled={generating || !genQuery.trim()}
          style={{ whiteSpace: "nowrap" }}
        >
          {generating ? "Generating…" : "Generate"}
        </button>
      </div>

      <section className="paper">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0 }}>{detail.title}</h2>
          <span className="stamp">Case File</span>
        </div>
        <hr />
        <p style={{ fontStyle: "italic" }}>{detail.summary}</p>
        <p>{detail.background}</p>
      </section>

      <h3 style={{ marginTop: 24 }}>Choose your side</h3>
      <div className="side-grid">
        {sides.map((s) => (
          <div
            key={s}
            className={`side-card ${side === s ? "selected" : ""}`}
            onClick={() => setSide(s)}
          >
            <div className="side-name">{s}</div>
            <div className="kv"><b>Role:</b> {detail.sides[s].role}</div>
            <div className="kv"><b>Goal:</b> {detail.sides[s].goal}</div>
            <div className="kv"><b>BATNA:</b> {detail.sides[s].batna}</div>
          </div>
        ))}
      </div>

      {personalityList.length > 1 && (
        <>
          <h3 style={{ marginTop: 24 }}>Opponent personality</h3>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {personalityList.map((p) => (
              <div
                key={p.id}
                onClick={() => setPersonality(p.id)}
                style={{
                  cursor: "pointer",
                  padding: "10px 16px",
                  borderRadius: 10,
                  border: `2px solid ${personality === p.id ? "var(--accent)" : "var(--border)"}`,
                  background: personality === p.id ? "rgba(198,160,79,0.12)" : "var(--panel)",
                  minWidth: 140,
                  transition: "border-color 0.15s",
                }}
              >
                <div style={{ fontWeight: 700, marginBottom: 3 }}>{p.label}</div>
                <div className="muted" style={{ fontSize: 12 }}>{p.description}</div>
              </div>
            ))}
          </div>
        </>
      )}

      <div style={{ marginTop: 22 }}>
        <button className="btn" onClick={begin} disabled={!side || starting}>
          {starting ? "Starting…" : side ? `Begin as ${side} →` : "Select a side to begin"}
        </button>
      </div>
    </div>
  );
}
