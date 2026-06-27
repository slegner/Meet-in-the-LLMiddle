"use client";

import { useEffect, useState } from "react";
import { getProfile, saveProfile, listSessions, getReport, type Observation, type Profile, type SessionCard, type Report } from "@/lib/api";

const EVICT_AFTER = 3;

function staleness(obs: Observation): "fresh" | "fading" | "stale" {
  const n = obs.sessions_since_last_seen ?? 0;
  if (n === 0) return "fresh";
  if (n === EVICT_AFTER - 1) return "stale";
  return "fading";
}

function StaleBadge({ obs }: { obs: Observation }) {
  const n = obs.sessions_since_last_seen ?? 0;
  if (n === 0) return null;
  const remaining = EVICT_AFTER - n;
  return (
    <span style={{
      fontSize: 11,
      fontWeight: 600,
      color: n === EVICT_AFTER - 1 ? "var(--muted)" : "var(--muted)",
      background: "var(--panel-2)",
      borderRadius: 6,
      padding: "1px 7px",
      whiteSpace: "nowrap",
      flexShrink: 0,
    }}>
      {remaining === 1 ? "auto-removing next session" : `${remaining} sessions left`}
    </span>
  );
}

const VERDICT_LABEL: Record<string, { label: string; color: string }> = {
  above_batna: { label: "Above BATNA", color: "var(--good)" },
  at_batna:    { label: "At BATNA",    color: "var(--accent)" },
  below_batna: { label: "Below BATNA", color: "var(--danger)" },
};

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionCard[] | null>(null);
  const [openReport, setOpenReport] = useState<{ sid: string; report: Report } | null>(null);
  const [fadingOpen, setFadingOpen] = useState(false);

  useEffect(() => {
    getProfile().then(setProfile).catch(() => setError("Could not load your profile."));
    listSessions().then(setSessions).catch(() => {});
  }, []);

  async function viewReport(sid: string) {
    if (openReport?.sid === sid) { setOpenReport(null); return; }
    try {
      const report = await getReport(sid);
      setOpenReport({ sid, report });
    } catch { /* silent */ }
  }

  function update<K extends keyof Profile>(key: K, value: Profile[K]) {
    setProfile((p) => (p ? { ...p, [key]: value } : p));
    setStatus("");
  }

  function removeObs(i: number) {
    if (!profile) return;
    update("observations", profile.observations.filter((_, j) => j !== i));
  }

  async function save() {
    if (!profile) return;
    setStatus("Saving…");
    try {
      const saved = await saveProfile(profile);
      setProfile(saved);
      setStatus("Saved ✓");
    } catch {
      setStatus("");
      setError("Could not save.");
    }
  }

  if (error) return <div className="container narrow"><p className="muted">{error}</p></div>;
  if (!profile) return <div className="container narrow"><p className="muted">Loading…</p></div>;

  const fresh = profile.observations.filter((o) => o.sessions_since_last_seen === 0);
  const fading = profile.observations.filter((o) => o.sessions_since_last_seen > 0);

  return (
    <div className="container" style={{ maxWidth: 1280 }}>
      <h1>Training Data</h1>
      <p className="subtitle">
        The AI uses this to remember how you negotiate and to target your weak spots.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignItems: "start" }}>

        {/* Left column: name + notes */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card">
            <h3>Display name</h3>
            <input
              className="profile-notes"
              style={{ minHeight: "auto" }}
              value={profile.display_name}
              onChange={(e) => update("display_name", e.target.value)}
            />
          </div>

          <div className="card">
            <h3>Your notes</h3>
            <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
              Anything you want the trainer to remember about your style and goals.
            </p>
            <textarea
              className="profile-notes"
              value={profile.notes}
              onChange={(e) => update("notes", e.target.value)}
            />
          </div>

          <div className="card">
            <h3>Pressure timer</h3>
            <p className="muted" style={{ fontSize: 13, marginTop: 0, marginBottom: 14 }}>
              When the timer is on during a session, AI presses if you go silent.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <label style={{ fontSize: 13 }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Idle timeout</div>
                <div className="muted" style={{ fontSize: 11, marginBottom: 6 }}>No typing after AI speaks</div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input
                    type="number"
                    min={10} max={600} step={5}
                    value={profile.timer_idle_secs ?? 120}
                    onChange={(e) => update("timer_idle_secs", Math.max(10, parseInt(e.target.value) || 120))}
                    style={{ width: 70, padding: "4px 6px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--panel)", color: "var(--text)" }}
                  />
                  <span className="muted">sec</span>
                </div>
              </label>
              <label style={{ fontSize: 13 }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Response timeout</div>
                <div className="muted" style={{ fontSize: 11, marginBottom: 6 }}>Started typing but haven't sent</div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input
                    type="number"
                    min={1} max={30} step={0.5}
                    value={((profile.timer_response_secs ?? 300) / 60).toFixed(1).replace(/\.0$/, "")}
                    onChange={(e) => update("timer_response_secs", Math.round(Math.max(1, parseFloat(e.target.value) || 5) * 60))}
                    style={{ width: 70, padding: "4px 6px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--panel)", color: "var(--text)" }}
                  />
                  <span className="muted">min</span>
                </div>
              </label>
            </div>
          </div>

          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <button className="btn" onClick={save}>Save</button>
            <span className="muted">{status}</span>
          </div>
        </div>

        {/* Right column: weak spots */}
        <div className="card" style={{ borderColor: "rgba(239,111,111,0.35)" }}>
          <h3 style={{ color: "var(--danger)", marginBottom: 4 }}>Weak spots from last session</h3>
          <p className="muted" style={{ fontSize: 13, marginTop: 0, marginBottom: 16 }}>
            Auto-collected from your most recent coaching report. Dismiss any you disagree with —
            spots that stop appearing are removed automatically after {EVICT_AFTER} sessions.
          </p>

          {profile.observations.length === 0 && (
            <p className="muted" style={{ fontStyle: "italic" }}>
              None yet — finish a simulation to populate this.
            </p>
          )}

          {fresh.length === 0 && profile.observations.length > 0 && (
            <p className="muted" style={{ fontStyle: "italic", fontSize: 13 }}>
              No new weak spots from your last session — looking good!
            </p>
          )}

          {fresh.map((obs) => {
            const realIdx = profile.observations.indexOf(obs);
            return (
              <div key={realIdx} style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                background: "rgba(239,111,111,0.10)",
                border: "1px solid rgba(239,111,111,0.28)",
                borderLeft: "3px solid var(--danger)",
                borderRadius: 8,
                padding: "9px 12px",
                marginBottom: 8,
              }}>
                <span style={{ flex: 1, fontSize: 14 }}>{obs.text}</span>
                <button onClick={() => removeObs(realIdx)} title="Dismiss"
                  style={{ background: "none", border: "none", color: "var(--muted)", fontSize: 16, cursor: "pointer", padding: "0 2px", lineHeight: 1, flexShrink: 0 }}>×</button>
              </div>
            );
          })}

          {/* Improving section — collapsed by default */}
          {fading.length > 0 && (
            <div style={{ marginTop: fresh.length > 0 ? 12 : 0 }}>
              <button
                onClick={() => setFadingOpen((v) => !v)}
                style={{ background: "none", border: "none", color: "var(--muted)", fontSize: 12, cursor: "pointer", padding: 0, display: "flex", alignItems: "center", gap: 6 }}
              >
                {fadingOpen ? "▲" : "▶"} {fading.length} improving — not seen recently
              </button>
              {fadingOpen && (
                <div style={{ marginTop: 8 }}>
                  {fading.map((obs) => {
                    const realIdx = profile.observations.indexOf(obs);
                    return (
                      <div key={realIdx} style={{
                        display: "flex", alignItems: "center", gap: 10,
                        background: "var(--panel)", border: "1px solid var(--border)",
                        borderLeft: "3px solid var(--muted)", borderRadius: 8,
                        padding: "9px 12px", marginBottom: 8, opacity: 0.7,
                      }}>
                        <span style={{ flex: 1, fontSize: 14 }}>{obs.text}</span>
                        <StaleBadge obs={obs} />
                        <button onClick={() => removeObs(realIdx)} title="Dismiss"
                          style={{ background: "none", border: "none", color: "var(--muted)", fontSize: 16, cursor: "pointer", padding: "0 2px", lineHeight: 1, flexShrink: 0 }}>×</button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Past cases ── */}
      <div style={{ marginTop: 28 }}>
        <h2 style={{ marginBottom: 12 }}>Past Cases</h2>
        {!sessions && <p className="muted">Loading…</p>}
        {sessions && sessions.length === 0 && <p className="muted">No completed simulations yet.</p>}
        {sessions && sessions.map((s) => {
          const isOpen = openReport?.sid === s.id;
          const deal = isOpen && openReport?.report.deal ? openReport.report.deal : null;
          const verdictStyle = deal ? VERDICT_LABEL[deal.verdict] : null;
          return (
            <div key={s.id} className="card" style={{ marginBottom: 12 }}>
              <div
                style={{ display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer" }}
                onClick={() => viewReport(s.id)}
              >
                <div>
                  <div style={{ fontWeight: 700 }}>{s.case_title} <span className="tag" style={{ textTransform: "capitalize", marginLeft: 6 }}>{s.side}</span>
                    {verdictStyle && (
                      <span style={{ marginLeft: 8, fontSize: 12, fontWeight: 700, color: verdictStyle.color }}>
                        🤝 {verdictStyle.label}
                      </span>
                    )}
                  </div>
                  <div className="muted" style={{ fontSize: 13 }}>
                    {new Date(s.created_at).toLocaleString()} · {s.turns} turns
                  </div>
                  {s.summary && <div style={{ fontSize: 13, marginTop: 4 }}>{s.summary}</div>}
                </div>
                <span className="muted">{isOpen ? "▲ hide" : "▼ report"}</span>
              </div>

              {isOpen && openReport && (
                <div style={{ marginTop: 14, borderTop: "1px solid var(--border)", paddingTop: 14 }}>
                  {openReport.report.accepted && deal && verdictStyle && (
                    <div style={{ border: `2px solid ${verdictStyle.color}`, borderRadius: 8, padding: "10px 14px", marginBottom: 12 }}>
                      <div style={{ fontWeight: 700, color: verdictStyle.color, marginBottom: 4 }}>🤝 {verdictStyle.label}</div>
                      <div style={{ fontSize: 14, marginBottom: 4 }}>{deal.deal_terms}</div>
                      <div style={{ fontSize: 13, color: "var(--muted)" }}>{deal.comments}</div>
                    </div>
                  )}
                  <p style={{ fontSize: 14, margin: "0 0 8px" }}>{openReport.report.summary}</p>
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>
                    <b style={{ color: "var(--text)" }}>Legal:</b> {openReport.report.legal.comments}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 6 }}>
                    <b style={{ color: "var(--text)" }}>Negotiation:</b> {openReport.report.negotiation.comments}
                  </div>
                  {openReport.report.weak_spots.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      {openReport.report.weak_spots.map((w, i) => (
                        <div className="weak" key={i}>{w}</div>
                      ))}
                    </div>
                  )}
                  <a className="btn btn-secondary" href={`http://localhost:8000/sessions/${s.id}/report.pdf`} target="_blank" rel="noreferrer" style={{ display: "inline-block", marginTop: 10, fontSize: 13 }}>
                    ⬇ PDF
                  </a>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
