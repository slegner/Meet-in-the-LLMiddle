"use client";

import { useEffect, useState } from "react";
import { getProfile, saveProfile, type Profile } from "@/lib/api";

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

  function updateObs(i: number, value: string) {
    if (!profile) return;
    const obs = [...profile.observations];
    obs[i] = value;
    update("observations", obs);
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

  return (
    <div className="container narrow">
      <h1>Training Profile</h1>
      <p className="subtitle">
        The AI uses this to remember how you negotiate and to target your weak spots. Edit it freely.
      </p>

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
        <textarea
          className="profile-notes"
          value={profile.notes}
          onChange={(e) => update("notes", e.target.value)}
        />
      </div>

      <div className="card">
        <h3>Observed tendencies / weak spots</h3>
        <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
          Auto-collected after each simulation. Edit or delete any you disagree with.
        </p>
        {profile.observations.length === 0 && <p className="muted">None yet — finish a simulation to populate this.</p>}
        {profile.observations.map((o, i) => (
          <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <input className="profile-notes" style={{ minHeight: "auto" }} value={o} onChange={(e) => updateObs(i, e.target.value)} />
            <button className="btn btn-secondary" onClick={() => removeObs(i)}>✕</button>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <button className="btn" onClick={save}>Save profile</button>
        <span className="muted">{status}</span>
      </div>
    </div>
  );
}
