"use client";

import { useEffect, useState } from "react";

type Principle = { heading: string; body: string };

function parseMd(raw: string): Principle[] {
  const principles: Principle[] = [];
  // Split on blank lines; each block is either a heading+body or standalone text
  const blocks = raw.split(/\n\n+/).map((b) => b.trim()).filter(Boolean);
  for (const block of blocks) {
    if (!block.startsWith("# ")) continue;
    const lines = block.split("\n");
    const heading = lines[0].replace(/^#\s+/, "").replace(/\.$/, "").trim();
    // Capitalise first letter (some headings start lowercase in the file)
    const title = heading.charAt(0).toUpperCase() + heading.slice(1);
    const body = lines.slice(1).join(" ").trim();
    principles.push({ heading: title, body });
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
          <p style={{ margin: "0 0 14px", fontWeight: 700, fontSize: 19, lineHeight: 1.3 }}>
            {i + 1}. {p.heading}
          </p>
          <p style={{ margin: 0, lineHeight: 1.8, fontSize: 14, color: "var(--muted)" }}>
            {p.body}
          </p>
        </div>
      ))}
    </div>
  );
}
