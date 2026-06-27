"use client";

import { useEffect, useState } from "react";

type Principle = { heading: string; body: string };

function parseMd(raw: string): Principle[] {
  const principles: Principle[] = [];
  const chunks = raw.split(/\n\n+/).map((c) => c.trim()).filter(Boolean);
  for (let i = 0; i < chunks.length; i++) {
    if (chunks[i].startsWith("# ")) {
      const heading = chunks[i].replace(/^#\s+/, "").replace(/\.$/, "");
      const body = chunks[i + 1] && !chunks[i + 1].startsWith("#") ? chunks[i + 1] : "";
      if (body) i++;
      principles.push({ heading, body });
    }
  }
  return principles;
}

export default function GuidePage() {
  const [principles, setPrinciples] = useState<Principle[]>([]);

  useEffect(() => {
    fetch("/what_makes_a_good_negotiator.md")
      .then((r) => r.text())
      .then((text) => setPrinciples(parseMd(text)));
  }, []);

  return (
    <div className="container narrow" style={{ maxWidth: 760 }}>
      <h1>What Makes a Good Negotiator?</h1>
      <p className="subtitle">
        The six principles used to grade your performance after each simulation.
      </p>

      {principles.map((p, i) => (
        <div key={i} className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <span style={{
              background: "var(--accent)",
              color: "#1a1200",
              borderRadius: 5,
              padding: "2px 9px",
              fontWeight: 700,
              fontSize: 12,
              flexShrink: 0,
            }}>
              {i + 1}
            </span>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>{p.heading}</h2>
          </div>
          <p style={{ margin: 0, lineHeight: 1.7, color: "var(--muted)", fontSize: 14 }}>{p.body}</p>
        </div>
      ))}
    </div>
  );
}
