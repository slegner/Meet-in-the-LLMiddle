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
    <div className="container">
      <h1>What Makes a Good Negotiator?</h1>
      <p className="subtitle">
        The six principles used to grade your performance after each simulation.
      </p>

      {principles.map((p, i) => (
        <div key={i} className="card" style={{ marginBottom: 16 }}>
          <p style={{ margin: "0 0 6px", fontWeight: 700, fontSize: 15 }}>
            {i + 1}. {p.heading}
          </p>
          <p style={{ margin: 0, lineHeight: 1.7, fontSize: 14 }}>{p.body}</p>
        </div>
      ))}
    </div>
  );
}
