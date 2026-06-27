// Typed client for the Legal Dojo FastAPI backend.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type Side = string;

export interface CaseSummary {
  id: string;
  title: string;
  summary: string;
}

export interface SideInfo {
  role: string;
  goal: string;
  batna: string;
}

export interface CaseDetail {
  id: string;
  title: string;
  summary: string;
  background: string;
  sources?: string[];
  sides: Record<Side, SideInfo>;
}

export interface CaseFile {
  case_id: string;
  title: string;
  background: string;
  side: Side;
  role: string;
  goal: string;
  batna: string;
  objectives: string[];
  documents: { name: string; summary: string }[];
}

export interface StartResponse {
  session_id: string;
  side: Side;
  case_title: string;
}

export interface ChatResponse {
  adversary: string;
  turn_number: number;
  phase: string;
  emotion: "neutral" | "annoyed" | "deal";
}

export interface SessionCard {
  id: string;
  case_id: string;
  case_title: string;
  side: Side;
  created_at: string;
  status: string;
  turns: number;
  summary: string;
}

export interface EvalBlock {
  comments: string;
  weak_spots: string[];
}

export interface DealAssessment {
  verdict: "above_batna" | "at_batna" | "below_batna";
  deal_terms: string;
  comments: string;
}

export interface Report {
  case_title: string;
  side: Side;
  turns: number;
  tokens_used?: number;
  accepted?: boolean;
  deal?: DealAssessment | null;
  summary: string;
  legal: EvalBlock;
  negotiation: EvalBlock;
  perception: EvalBlock;
  weak_spots: string[];
}

export interface Observation {
  text: string;
  sessions_since_last_seen: number;
  added_at: string | null;
}

export interface Profile {
  display_name: string;
  notes: string;
  observations: Observation[];
  timer_idle_secs?: number;
  timer_response_secs?: number;
  updated_at?: string | null;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${method} ${path} failed: ${res.status}`);
  return res.json();
}

export const listCases = () => getJSON<CaseSummary[]>("/cases");
export const getCase = (id: string) => getJSON<CaseDetail>(`/cases/${id}`);
export const generateCase = (query: string, save = true) =>
  send<CaseDetail>("POST", "/cases/generate", { query, save });
export interface Personality {
  id: string;
  label: string;
  description: string;
}

export const listPersonalities = () => getJSON<Personality[]>("/personalities");
export const startSession = (case_id: string, side: Side, personality = "default") =>
  send<StartResponse>("POST", "/sessions", { case_id, side, personality });
export const getCaseFile = (sid: string) =>
  getJSON<CaseFile>(`/sessions/${sid}/casefile`);
export const postChat = (sid: string, message: string) =>
  send<ChatResponse>("POST", `/sessions/${sid}/chat`, { message });
export const endSession = (sid: string, accepted = false) =>
  send<Report>("POST", `/sessions/${sid}/end`, { accepted });
export const nudgeSession = (sid: string) =>
  send<ChatResponse>("POST", `/sessions/${sid}/nudge`);
export const getReport = (sid: string) => getJSON<Report>(`/sessions/${sid}/report`);
export interface TurnRecord {
  n: number;
  student: string;
  adversary: string;
  phase: string;
}
export interface SessionState {
  id: string;
  side: Side;
  case_title: string;
  status: string;
  turns: TurnRecord[];
}
export const getSession = (sid: string) => getJSON<SessionState>(`/sessions/${sid}`);

export const listSessions = () => getJSON<SessionCard[]>("/sessions");
export const deleteSession = (sid: string) => send<{ deleted: boolean }>("DELETE", `/sessions/${sid}`);
export const getProfile = () => getJSON<Profile>("/player-memory");
export const saveProfile = (p: Profile) => send<Profile>("PUT", "/player-memory", p);
// Streaming TTS: point an <audio> element straight at this URL so it plays
// progressively (starts ~1s in) instead of waiting for the whole clip.
export const ttsUrl = (text: string) =>
  `${API_BASE}/tts?text=${encodeURIComponent(text)}`;

export const reportPdfUrl = (sid: string) => `${API_BASE}/sessions/${sid}/report.pdf`;
export const transcriptUrl = (sid: string) => `${API_BASE}/sessions/${sid}/transcript`;
