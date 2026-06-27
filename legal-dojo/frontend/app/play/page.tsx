"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { postChat, endSession, getSession, ttsUrl, type Report } from "@/lib/api";

const ACTIVE_KEY = "legaldojo_activeSid";
import CaseFileOverlay from "../components/CaseFileOverlay";
import HistoryOverlay from "../components/HistoryOverlay";
import ReportView from "../components/ReportView";
import Overlay from "../components/Overlay";

interface Msg { role: "player" | "ai"; text: string }

function Scene() {
  const sid = useSearchParams().get("sid") ?? "";
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [turns, setTurns] = useState(0);
  const [phase, setPhase] = useState<string>("");
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [showCaseFile, setShowCaseFile] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [ending, setEnding] = useState(false);
  const [ended, setEnded] = useState(false);

  const [voiceOn, setVoiceOn] = useState(true);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  function speak(text: string) {
    if (!voiceOn || !text) return;
    try {
      if (!audioRef.current) audioRef.current = new Audio();
      audioRef.current.src = ttsUrl(text); // streams + plays progressively
      audioRef.current.play().catch(() => {}); // ignore autoplay blocks
    } catch {
      /* TTS is best-effort; text still works */
    }
  }

  const histRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (expanded) histRef.current?.scrollTo({ top: histRef.current.scrollHeight });
  }, [messages, expanded]);

  // Resume: rebuild the conversation from the saved session and remember this
  // as the active game so we can return to the current stage later.
  useEffect(() => {
    if (!sid) return;
    getSession(sid)
      .then((s) => {
        const msgs: Msg[] = [];
        for (const t of s.turns) {
          msgs.push({ role: "player", text: t.student });
          msgs.push({ role: "ai", text: t.adversary });
        }
        setMessages(msgs);
        setTurns(s.turns.length);
        if (s.turns.length) setPhase(s.turns[s.turns.length - 1].phase);
        if (s.status === "ended") {
          setEnded(true);
          localStorage.removeItem(ACTIVE_KEY);
        } else {
          localStorage.setItem(ACTIVE_KEY, sid);
        }
      })
      .catch(() => {});
  }, [sid]);

  // While the 4-agent team runs (~6-7s), cycle a themed status so the wait
  // reads as "the opponent is strategising" rather than "stuck".
  const THINKING = [
    "Opposing counsel is strategising…",
    "weighing several lines of attack…",
    "predicting where each could lead…",
    "deciding their move…",
  ];
  const [thinkIdx, setThinkIdx] = useState(0);
  useEffect(() => {
    if (!sending) return;
    setThinkIdx(0);
    const id = setInterval(() => setThinkIdx((i) => i + 1), 1700);
    return () => clearInterval(id);
  }, [sending]);

  async function send() {
    const text = input.trim();
    if (!text || sending || ended) return;
    setError(null);
    setInput("");
    setMessages((m) => [...m, { role: "player", text }]);
    setSending(true);
    try {
      const res = await postChat(sid, text);
      setMessages((m) => [...m, { role: "ai", text: res.adversary }]);
      setTurns(res.turn_number);
      setPhase(res.phase);
      speak(res.adversary);
    } catch {
      // Roll back the optimistic bubble and give the text back so the turn
      // isn't lost — the user can just press Send again.
      setMessages((m) => m.slice(0, -1));
      setInput(text);
      setError("The opponent didn't respond (likely the Gemini API is rate-limited). Your message was kept — press Send to retry.");
    } finally {
      setSending(false);
    }
  }

  async function end() {
    setEnding(true);
    try {
      setReport(await endSession(sid));
      setEnded(true);
      localStorage.removeItem(ACTIVE_KEY);
    } catch {
      setError("Could not generate the report.");
    } finally {
      setEnding(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }

  // Current dialogue line + who is speaking.
  const last = messages[messages.length - 1];
  const speaker: "player" | "ai" = sending ? "ai" : last?.role ?? "player";
  const lineText = sending
    ? THINKING[Math.min(thinkIdx, THINKING.length - 1)]
    : last?.text ?? "Opposing counsel is waiting. Make your opening move.";
  const speakerName = speaker === "player" ? "You" : "Opposing Counsel";

  return (
    <div className="container wide">
      <div className="dojo">
        {/* Left controls (outside the stage) */}
        <div className="side-rail">
          <button className="btn btn-secondary btn-block" onClick={() => setShowCaseFile(true)}>📁 Case File</button>
          <button className="btn btn-danger btn-block" onClick={end} disabled={ending || ended}>
            {ending ? "Scoring…" : ended ? "Ended" : "⏹ End"}
          </button>
          <button
            className="btn btn-secondary btn-block"
            onClick={() => {
              setVoiceOn((v) => {
                if (v && audioRef.current) audioRef.current.pause();
                return !v;
              });
            }}
            title="Toggle the opponent's voice"
          >
            {voiceOn ? "🔊 Voice on" : "🔇 Voice off"}
          </button>
          <div className="turn-counter">Turn {turns}{phase && <span className="phase-pill">{phase}</span>}</div>
        </div>

        {/* The game stage */}
        <div className="stage-wrap">
          <div className="stage">
            <img src="/Human.png" alt="You" className={`char human ${speaker === "player" ? "active" : "dim"}`} />
            <img src="/AI.png" alt="AI opponent" className={`char robot ${speaker === "ai" ? "active" : "dim"}`} />

            <div className="dialogue">
              <div className={`pointer ${speaker === "player" ? "left" : "right"}`} />
              <div className="speaker">
                <span>{speakerName}</span>
                <button className="expand-btn" onClick={() => setExpanded((e) => !e)}>
                  {expanded ? "▲ hide history" : "▼ show history"}
                </button>
              </div>

              {!expanded && <div className="line">{lineText}</div>}

              {expanded && (
                <div className="history-scroll" ref={histRef}>
                  {messages.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No messages yet.</div>}
                  {messages.map((m, i) => (
                    <div className={`h-line ${m.role}`} key={i}>
                      <span className="who">{m.role === "player" ? "You" : "Opposing Counsel"}</span>
                      {m.text}
                    </div>
                  ))}
                </div>
              )}

              {!ended && (
                <div className="composer">
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={onKeyDown}
                    placeholder="Type your argument… (Enter to send)"
                    disabled={sending}
                  />
                  <button className="btn" onClick={send} disabled={sending || !input.trim()}>Send</button>
                </div>
              )}
            </div>
          </div>
          {error && <p className="weak" style={{ marginTop: 10 }}>{error}</p>}
        </div>

        {/* Right controls (outside the stage) */}
        <div className="side-rail right">
          <button className="btn btn-secondary btn-block" onClick={() => setShowHistory(true)}>🏆 Previous Simulations</button>
        </div>
      </div>

      {showCaseFile && <CaseFileOverlay sid={sid} onClose={() => setShowCaseFile(false)} />}
      {showHistory && <HistoryOverlay onClose={() => setShowHistory(false)} />}
      {ended && report && (
        <Overlay title="Coaching Report" onClose={() => setEnded(false)}>
          <ReportView sid={sid} report={report} />
        </Overlay>
      )}
    </div>
  );
}

export default function PlayPage() {
  return (
    <Suspense fallback={<div className="container"><p className="muted">Loading…</p></div>}>
      <Scene />
    </Suspense>
  );
}
