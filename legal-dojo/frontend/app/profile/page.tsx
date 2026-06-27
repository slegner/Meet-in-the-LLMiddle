"use client";

import { useEffect, useState } from "react";
import { getProfile, saveProfile, type Observation, type Profile } from "@/lib/api";

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

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProfile().then(setProfile).catch(() => setError("Could not load your profile."));
  }, []);

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
      <h1>Training Profile</h1>
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

          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <button className="btn" onClick={save}>Save profile</button>
            <span className="muted">{status}</span>
          </div>
        </div>

        {/* Right column: weak spots */}
        <div className="card" style={{ borderColor: "rgba(239,111,111,0.35)" }}>
          <h3 style={{ color: "var(--danger)", marginBottom: 4 }}>Identified weak spots</h3>
          <p className="muted" style={{ fontSize: 13, marginTop: 0, marginBottom: 16 }}>
            Auto-collected from your coaching reports. Spots that stop appearing in your sessions
            are removed automatically after {EVICT_AFTER} sessions — or dismiss one yourself if
            you disagree.
          </p>

          {profile.observations.length === 0 && (
            <p className="muted" style={{ fontStyle: "italic" }}>
              None yet — finish a simulation to populate this.
            </p>
          )}

          {/* Active weak spots (seen in most recent session) */}
          {fresh.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.5px", textTransform: "uppercase", color: "var(--muted)", marginBottom: 8 }}>
                Still present
              </div>
              {fresh.map((obs, i) => {
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
                    <button
                      onClick={() => removeObs(realIdx)}
                      title="Dismiss this observation"
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--muted)",
                        fontSize: 16,
                        cursor: "pointer",
                        padding: "0 2px",
                        lineHeight: 1,
                        flexShrink: 0,
                      }}
                    >×</button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Fading observations (not seen recently) */}
          {fading.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.5px", textTransform: "uppercase", color: "var(--muted)", marginBottom: 8 }}>
                Improving — not seen recently
              </div>
              {fading.map((obs) => {
                const realIdx = profile.observations.indexOf(obs);
                return (
                  <div key={realIdx} style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    background: "var(--panel)",
                    border: "1px solid var(--border)",
                    borderLeft: "3px solid var(--muted)",
                    borderRadius: 8,
                    padding: "9px 12px",
                    marginBottom: 8,
                    opacity: 0.7,
                  }}>
                    <span style={{ flex: 1, fontSize: 14 }}>{obs.text}</span>
                    <StaleBadge obs={obs} />
                    <button
                      onClick={() => removeObs(realIdx)}
                      title="Dismiss this observation"
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--muted)",
                        fontSize: 16,
                        cursor: "pointer",
                        padding: "0 2px",
                        lineHeight: 1,
                        flexShrink: 0,
                      }}
                    >×</button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
