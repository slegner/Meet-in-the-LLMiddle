"use client";

import { useEffect, useState } from "react";

type Principle = { heading: string; body: string };

function parseMd(raw: string): Principle[] {
  const principles: Principle[] = [];
  const blocks = raw.split(/\n\n+/).map((b) => b.trim()).filter(Boolean);
  for (const block of blocks) {
    if (!block.startsWith("# ")) continue;
    const lines = block.split("\n");
    const heading = lines[0].replace(/^#\s+/, "").replace(/\.$/, "").trim();
    const title = heading.charAt(0).toUpperCase() + heading.slice(1);
    const body = lines.slice(1).join(" ").trim();
    principles.push({ heading: title, body });
  }
  return principles;
}

export default function GuideButton() {
  const [open, setOpen] = useState(false);
  const [principles, setPrinciples] = useState<Principle[]>([]);

  useEffect(() => {
    fetch("/what_makes_a_good_negotiator.md")
      .then((r) => r.text())
      .then((text) => setPrinciples(parseMd(text)))
      .catch(() => {});
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") setOpen(false); }
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen(true)}
        title="Negotiator's Guide"
        style={{
          position: "fixed",
          bottom: 24,
          right: 24,
          zIndex: 900,
          width: 44,
          height: 44,
          borderRadius: "50%",
          background: "var(--accent)",
          color: "#1a1200",
          border: "none",
          fontSize: 20,
          fontWeight: 700,
          cursor: "pointer",
          boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          lineHeight: 1,
        }}
      >
        ?
      </button>

      {/* Overlay */}
      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: 16,
              width: "100%",
              maxWidth: 960,
              maxHeight: "85vh",
              overflowY: "auto",
              padding: "28px 32px",
              position: "relative",
            }}
          >
            <button
              onClick={() => setOpen(false)}
              style={{
                position: "absolute",
                top: 16,
                right: 18,
                background: "none",
                border: "none",
                color: "var(--muted)",
                fontSize: 22,
                cursor: "pointer",
                lineHeight: 1,
              }}
            >
              ✕
            </button>

            <h2 style={{ margin: "0 0 4px", fontSize: 26, fontWeight: 700 }}>
              What Makes a Good Negotiator?
            </h2>
            <p style={{ margin: "0 0 24px", color: "var(--muted)", fontSize: 13 }}>
              The six principles used to grade your performance after each simulation.
            </p>

            {principles.map((p, i) => (
              <div
                key={i}
                style={{
                  borderTop: i === 0 ? "none" : "1px solid var(--border)",
                  paddingTop: i === 0 ? 0 : 20,
                  marginTop: i === 0 ? 0 : 20,
                }}
              >
                <p style={{ margin: "0 0 10px", fontWeight: 700, fontSize: 19 }}>
                  {i + 1}. {p.heading}
                </p>
                <p style={{ margin: 0, fontSize: 16, lineHeight: 1.85, color: "var(--muted)" }}>
                  {p.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
