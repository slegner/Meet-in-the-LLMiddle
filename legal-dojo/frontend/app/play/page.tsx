"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { postChat, endSession, nudgeSession, getSession, getCaseFile, getProfile, ttsUrl, transcribeAudio, type Report, type CaseFile } from "@/lib/api";

const ACTIVE_KEY = "legaldojo_activeSid";
import HistoryOverlay from "../components/HistoryOverlay";
import ReportView from "../components/ReportView";
import Overlay from "../components/Overlay";

interface Msg { role: "player" | "ai"; text: string }

function CaseFilePanel({ cf }: { cf: CaseFile }) {
  return (
    <div style={{
      flex: 1,
      minHeight: 0,
      overflowY: "auto",
      background: "#f4ecd2",
      color: "#2c2412",
      border: "1px solid #cbb783",
      borderRadius: 8,
      padding: "20px 20px",
      fontFamily: "Georgia, 'Times New Roman', serif",
      fontSize: 15,
      lineHeight: 1.65,
    }}>
      <div style={{ fontWeight: 800, fontSize: 20, marginBottom: 3, color: "#3a2c10" }}>{cf.title}</div>
      <div style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.6px", color: "#8a6a1e", marginBottom: 10 }}>
        Counsel for {cf.side}
      </div>
      <hr style={{ border: "none", borderTop: "1px solid #cbb783", margin: "6px 0 10px" }} />

      {[
        ["Background", cf.background],
        ["Your Role", cf.role],
        ["Goal", cf.goal],
        ["BATNA", cf.batna],
      ].map(([label, text]) => (
        <div key={label} style={{ marginBottom: 10 }}>
          <div style={{ fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: "0.5px", color: "#5a4020", marginBottom: 4 }}>{label}</div>
          <p style={{ margin: 0 }}>{text}</p>
        </div>
      ))}

      <div style={{ marginBottom: 10 }}>
        <div style={{ fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: "0.5px", color: "#5a4020", marginBottom: 3 }}>Objectives</div>
        <ul style={{ margin: 0, paddingLeft: 14 }}>
          {cf.objectives.map((o, i) => <li key={i} style={{ marginBottom: 3 }}>{o}</li>)}
        </ul>
      </div>

      {cf.documents.length > 0 && (
        <div>
          <div style={{ fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: "0.5px", color: "#5a4020", marginBottom: 8 }}>Documents</div>
          {cf.documents.map((d, i) => (
            <div key={i} style={{ borderLeft: "2px solid #a9842c", paddingLeft: 10, marginBottom: 10 }}>
              <div style={{ fontWeight: 700, fontSize: 14 }}>{d.name}</div>
              <div style={{ fontSize: 13, color: "#6a5a33" }}>{d.summary}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Scene() {
  const sid = useSearchParams().get("sid") ?? "";
  const router = useRouter();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [turns, setTurns] = useState(0);
  const [phase, setPhase] = useState<string>("");
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [caseFileOpen, setCaseFileOpen] = useState(true);
  const [caseFile, setCaseFile] = useState<CaseFile | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [ending, setEnding] = useState(false);
  const [ended, setEnded] = useState(false);

  const [emotion, setEmotion] = useState<"neutral" | "annoyed" | "deal">("neutral");

  // ── Timer ──────────────────────────────────────────────────────────────────
  // Defaults; overwritten from profile on mount
  const idleSecsRef = useRef(30);
  const responseSecsRef = useRef(120);
  const [timerOn, setTimerOn] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  // Refs so timer callbacks read current values without stale closures
  const timerOnRef = useRef(false);
  const sendingRef = useRef(false);
  const endedRef = useRef(false);
  const isTypingRef = useRef(false);

  useEffect(() => { timerOnRef.current = timerOn; }, [timerOn]);
  useEffect(() => { sendingRef.current = sending; }, [sending]);
  useEffect(() => { endedRef.current = ended; }, [ended]);

  // Countdown tick — one setTimeout per second so cleanup is automatic
  useEffect(() => {
    if (!timerOn || countdown === null) return;
    if (countdown <= 0) {
      setCountdown(null);
      if (!sendingRef.current && !endedRef.current) fireNudge();
      return;
    }
    const id = setTimeout(() => setCountdown((c) => (c !== null ? c - 1 : null)), 1000);
    return () => clearTimeout(id);
  }, [countdown, timerOn]); // eslint-disable-line react-hooks/exhaustive-deps

  function startIdleTimer() {
    if (!timerOnRef.current) return;
    isTypingRef.current = false;
    setCountdown(idleSecsRef.current);
  }

  function onInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    // If the user edits during the voice auto-send window, they take over manually.
    pendingVoiceTextRef.current = null;
    setVoicePending(false);
    // First keystroke switches from idle timer to (longer) response timer
    if (timerOnRef.current && !isTypingRef.current && e.target.value.trim()) {
      isTypingRef.current = true;
      setCountdown(responseSecsRef.current);
    }
  }

  async function fireNudge() {
    if (sendingRef.current || endedRef.current) return;
    setSending(true);
    try {
      const res = await nudgeSession(sid);
      setMessages((m) => [...m, { role: "ai", text: res.adversary }]);
      setTurns(res.turn_number);
      setPhase(res.phase);
      setEmotion(res.emotion ?? "neutral");
      speak(res.adversary);
      startIdleTimer();
    } catch { /* silent — don't disrupt the session */ } finally {
      setSending(false);
    }
  }
  // ──────────────────────────────────────────────────────────────────────────

  const [voiceOn, setVoiceOn] = useState(true);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const [voiceMode, setVoiceMode] = useState(false);
  const voiceModeRef = useRef(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const silenceRafRef = useRef<number | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  // Holds the transcribed text while the 1-second "show before send" window is open.
  // Cleared if the user edits the textarea (they take over manually).
  const pendingVoiceTextRef = useRef<string | null>(null);
  const [voicePending, setVoicePending] = useState(false);

  function speak(text: string) {
    if (!voiceOn || !text) return;
    try {
      if (!audioRef.current) audioRef.current = new Audio();
      audioRef.current.src = ttsUrl(text);
      audioRef.current.onended = () => {
        if (voiceModeRef.current && !endedRef.current) startListening().catch(() => {});
      };
      audioRef.current.play().catch(() => {});
    } catch { /* TTS is best-effort */ }
  }

  const histRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (expanded) histRef.current?.scrollTo({ top: histRef.current.scrollHeight });
  }, [messages, expanded]);

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

    getCaseFile(sid).then(setCaseFile).catch(() => {});
    getProfile().then((p) => {
      if (p.timer_idle_secs) idleSecsRef.current = p.timer_idle_secs;
      if (p.timer_response_secs) responseSecsRef.current = p.timer_response_secs;
    }).catch(() => {});
  }, [sid]);

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

  function stopSpeaking() {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
  }

  function stopSilenceDetection() {
    if (silenceRafRef.current !== null) { cancelAnimationFrame(silenceRafRef.current); silenceRafRef.current = null; }
    if (audioCtxRef.current) { audioCtxRef.current.close().catch(() => {}); audioCtxRef.current = null; }
  }

  async function startListening() {
    if (sendingRef.current || endedRef.current) return;
    let stream: MediaStream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
    catch { return; }

    const mr = new MediaRecorder(stream);
    chunksRef.current = [];
    mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
    mr.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      stopSilenceDetection();
      setRecording(false);
      if (!voiceModeRef.current) return;
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      setTranscribing(true);
      try {
        const text = await transcribeAudio(blob);
        if (text) {
          // Show the transcript in the textarea so the user can read (and edit) it.
          // Auto-send after 1 s unless the user modifies the field (which clears pendingVoiceTextRef).
          setInput(text);
          pendingVoiceTextRef.current = text;
          setVoicePending(true);
          await new Promise<void>((r) => setTimeout(r, 1000));
          setVoicePending(false);
          if (pendingVoiceTextRef.current === text && voiceModeRef.current) {
            pendingVoiceTextRef.current = null;
            await sendMessage(text);
          }
        }
      } catch {}
      setTranscribing(false);
    };

    try {
      const audioCtx = new AudioContext();
      audioCtxRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      let speechDetected = false;
      let silenceStart: number | null = null;
      const startTime = Date.now();
      function tick() {
        if (!voiceModeRef.current) { mr.stop(); return; }
        analyser.getByteTimeDomainData(data);
        const rms = Math.sqrt(data.reduce((s, v) => s + (v - 128) ** 2, 0) / data.length);
        if (rms > 8) { speechDetected = true; silenceStart = null; }
        else if (speechDetected && Date.now() - startTime > 500) {
          if (silenceStart === null) silenceStart = Date.now();
          else if (Date.now() - silenceStart > 1500) { mr.stop(); return; }
        }
        silenceRafRef.current = requestAnimationFrame(tick);
      }
      silenceRafRef.current = requestAnimationFrame(tick);
    } catch { /* Web Audio unavailable — recording runs until voice mode exits */ }

    mr.start();
    mediaRecorderRef.current = mr;
    setRecording(true);
  }

  async function enterVoiceMode() {
    if (audioRef.current && !audioRef.current.paused) {
      audioRef.current.onended = null;
      stopSpeaking();
      setEmotion("annoyed");
    }
    setVoiceMode(true);
    voiceModeRef.current = true;
    await startListening().catch(() => { setVoiceMode(false); voiceModeRef.current = false; });
  }

  function exitVoiceMode() {
    setVoiceMode(false);
    voiceModeRef.current = false;
    stopSilenceDetection();
    if (audioRef.current) audioRef.current.onended = null;
    mediaRecorderRef.current?.stop();
    stopSpeaking();
  }

  async function sendMessage(text: string) {
    if (!text || sending || ended) return;
    stopSpeaking();
    if (audioRef.current) audioRef.current.onended = null;
    setError(null);
    setInput("");
    setCountdown(null);           // pause timer while AI is replying
    isTypingRef.current = false;
    setMessages((m) => [...m, { role: "player", text }]);
    setSending(true);
    try {
      const res = await postChat(sid, text);
      setMessages((m) => [...m, { role: "ai", text: res.adversary }]);
      setTurns(res.turn_number);
      setPhase(res.phase);
      setEmotion(res.emotion ?? "neutral");
      speak(res.adversary);
      startIdleTimer();           // restart 2-min idle clock after AI speaks
    } catch {
      setMessages((m) => m.slice(0, -1));
      setInput(text);
      setError("The opponent didn't respond (likely the Gemini API is rate-limited). Your message was kept — press Send to retry.");
    } finally {
      setSending(false);
    }
  }

  async function send() {
    const text = input.trim();
    if (!text) return;
    await sendMessage(text);
  }

  async function end(accepted = false) {
    setEnding(true);
    try {
      setReport(await endSession(sid, accepted));
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

  const last = messages[messages.length - 1];
  const speaker: "player" | "ai" = sending ? "ai" : last?.role ?? "player";
  const lineText = sending
    ? THINKING[Math.min(thinkIdx, THINKING.length - 1)]
    : last?.text ?? "Opposing counsel is waiting. Make your opening move.";
  const speakerName = speaker === "player" ? "You" : "Opposing Counsel";

  return (
    <div style={{ padding: "24px 12px 80px", width: "100%", boxSizing: "border-box" }}>

      {/* ── Button bar ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
        <button
          className="btn btn-secondary"
          style={{ borderColor: caseFileOpen ? "var(--accent)" : undefined }}
          onClick={() => setCaseFileOpen((v) => !v)}
        >
          📁 {caseFileOpen ? "Close File" : "Case File"}
        </button>
        <button
          className="btn"
          style={{ background: "var(--good)", color: "#0a2010" }}
          onClick={() => end(true)}
          disabled={ending || ended || turns < 1}
          title="Accept the deal on the table and receive your coaching report"
        >
          {ending ? "Scoring…" : "🤝 Accept Deal"}
        </button>
        <button className="btn btn-danger" onClick={() => end(false)} disabled={ending || ended}>
          {ending ? "Scoring…" : ended ? "Ended" : "⏹ End"}
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => setVoiceOn((v) => {
            if (v) {
              exitVoiceMode();
              if (audioRef.current) audioRef.current.pause();
            }
            return !v;
          })}
        >
          {voiceOn ? "🔊 Voice on" : "🔇 Voice off"}
        </button>
        <button
          className="btn btn-secondary"
          style={{ borderColor: timerOn ? "var(--accent)" : undefined }}
          onClick={() => {
            const next = !timerOn;
            setTimerOn(next);
            timerOnRef.current = next;
            if (next) { isTypingRef.current = false; setCountdown(idleSecsRef.current); }
            else setCountdown(null);
          }}
          title="2 min idle / 5 min response — AI presses on if you go silent"
        >
          ⏱ Timer {timerOn ? "on" : "off"}
        </button>
        {timerOn && countdown !== null && (
          <div style={{
            fontFamily: "monospace",
            fontWeight: 700,
            fontSize: 14,
            minWidth: 46,
            color: countdown < 30 ? "var(--danger)" : countdown < 60 ? "var(--accent)" : "var(--muted)",
          }}>
            {Math.floor(countdown / 60)}:{String(countdown % 60).padStart(2, "0")}
          </div>
        )}
        <div className="turn-counter" style={{ margin: "0 4px" }}>
          Turn {turns}{phase && <span className="phase-pill">{phase}</span>}
        </div>
        <div style={{ flex: 1 }} />
        <button className="btn btn-secondary" onClick={() => setShowHistory(true)}>
          🏆 Previous Simulations
        </button>
      </div>

      {/* ── Case file + stage ── */}
      <div style={{ display: "flex", gap: 16, alignItems: "stretch", justifyContent: "center" }}>

        {/* Case file column — outer clips so content doesn't squish */}
        <div style={{
          width: caseFileOpen ? 700 : 0,
          flexShrink: 0,
          overflow: "hidden",
          transition: "width 0.3s ease",
          display: "flex",
        }}>
          <div style={{ width: 700, flexShrink: 0, display: "flex", flexDirection: "column" }}>
            {caseFile
              ? <CaseFilePanel cf={caseFile} />
              : <div className="muted" style={{ fontSize: 13, paddingTop: 8 }}>Loading…</div>}
          </div>
        </div>

        {/* Stage — max-width keeps it centred when case file is closed */}
        <div style={{ flex: "1 1 auto", minWidth: 0, maxWidth: 1200 }}>
          <div className="stage-wrap">
            <div className="stage">
              <img src="/Human.png" alt="You" className={`char human ${speaker === "player" ? "active" : "dim"}`} />
              <img
                src={emotion === "annoyed" ? "/AI_annoyed.png" : emotion === "deal" ? "/AI_deal.png" : "/AI.png"}
                alt="AI opponent"
                className={`char robot ${speaker === "ai" ? "active" : "dim"}`}
              />

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
                      onChange={onInputChange}
                      onKeyDown={onKeyDown}
                      placeholder={transcribing ? "Transcribing…" : "Type your argument… (Enter to send)"}
                      disabled={sending}
                      style={voicePending ? { borderColor: "var(--accent)", boxShadow: "0 0 0 2px rgba(198,160,79,0.25)" } : undefined}
                    />
                    <button
                      className={`btn ${voiceMode ? "" : "btn-secondary"}`}
                      onClick={voiceMode ? exitVoiceMode : enterVoiceMode}
                      disabled={transcribing}
                      title={voiceMode ? "Exit voice mode" : "Enter voice mode"}
                      style={voiceMode ? { background: recording ? "#c0392b" : "#8b0000", color: "#fff", borderColor: recording ? "#c0392b" : "#8b0000" } : undefined}
                    >
                      {transcribing ? "…" : voiceMode ? (recording ? "🎙 Listening…" : "🔴 Voice") : "🎤"}
                    </button>
                    <button className="btn" onClick={send} disabled={sending || !input.trim()}>Send</button>
                  </div>
                )}
              </div>
            </div>
            {error && <p className="weak" style={{ marginTop: 10 }}>{error}</p>}
          </div>
        </div>
      </div>

      {showHistory && <HistoryOverlay onClose={() => setShowHistory(false)} />}
      {ended && report && (
        <Overlay title="Coaching Report" onClose={() => router.push("/")} wide>
          <ReportView sid={sid} report={report} />
          <div style={{ marginTop: 18 }}>
            <button className="btn" onClick={() => router.push("/")}>
              ← Back to Case Files (start a new case)
            </button>
          </div>
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
