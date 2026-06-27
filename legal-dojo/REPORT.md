# Meet at the LLMiddle — Technical Project Report

**University of Cambridge · PhD Research 2025–26**
**Domain:** LLM-mediated legal negotiation training

---

## 1. Motivation

Legal negotiation is a core professional skill that is difficult to practise systematically. Real negotiation partners are expensive, role-play partners are inconsistent, and existing simulation tools are either static (scripted decision trees) or too permissive (an LLM that agrees too easily). The goal of this project is a system that:

- Maintains a strategically coherent, adversarial AI opponent across an open-ended negotiation
- Adapts its behaviour based on the quality of the student's argument, not just its content
- Provides structured, criterion-referenced coaching grounded in actual transcript moments
- Persists a student's behavioural profile across sessions to track development over time

---

## 2. System Overview

Meet at the LLMiddle is a full-stack web application. The student selects a two-sided legal dispute, chooses a party to represent, and negotiates in a turn-based text (or voice) interface against a multi-agent AI system. At the end of the session, a coaching pipeline evaluates the student's performance and generates a structured report.

**Stack:** FastAPI (Python 3.11) backend · Next.js App Router (TypeScript) frontend · JSON file state (no database) · Google ADK for the live opponent · Gemini Flash for the evaluator pipeline · Nemotron Super for criteria grading · Perplexity for legal lookups.

---

## 3. AI Opponent Design

### 3.1 Multi-agent pipeline

Each student turn runs a four-agent pipeline:

**Director** — a private strategist that never speaks to the student. It receives the full case brief, the conversation transcript, the AI's running private notes, and a directive from the concession state machine. It selects the best tactic from a tiered list (fact-based tactics preferred: `cite_clause`, `legal_argument`, `factual_counter`; then positional and pressure tactics) and outputs a concrete instruction naming a specific fact or provision. It also assesses which of the 6 Harvard negotiation criteria the student just demonstrated, which feeds the merit concession streak.

**Adversary** — the opponent as a character. It generates 3 candidate replies following the Director's instruction. A hard rule requires every reply to be anchored in at least one specific fact, document, clause, or legal provision — emotional pressure without factual grounding is explicitly prohibited.

**Predictor** — selects the strongest candidate reply by forecasting how it will land.

**NoteTaker** — records the AI's private inner monologue about the student (confidence, trust, tells) — this runs in parallel with the reply chain (off the critical path) and feeds both the Director's next turn and the perception evaluator at session end.

This pipeline runs on Google ADK: a `SequentialAgent` (Director → Adversary → Predictor) inside a `ParallelAgent` with the NoteTaker, sharing state via ADK session variables. Models: Gemini 2.5 Flash for Director and Adversary; Gemini 2.5 Flash-Lite for Predictor and NoteTaker. Thinking is disabled on all agents to control latency.

### 3.2 Concession system

A key design challenge in AI negotiation trainers is preventing the opponent from either capitulating instantly or stonewalling indefinitely. The concession system combines two independent mechanisms:

**Deterministic rules** (`concession.py`) — a state machine whose output is injected into the Director's prompt as `hard_rules`. It enforces: aggressive opening, no demand repeated more than twice, grudging concession when the student makes a strong legal argument (citation heuristic on the raw text), and a drive toward compromise starting from a turn rolled once per session in [6, 12]. This layer is entirely LLM-independent — it fires regardless of what the Director would otherwise choose.

**Merit concessions** — the Director outputs a `criterion_hit` field naming which of the 6 criteria the student clearly demonstrated this turn, if any. A streak tracker in session state monitors consecutive hits on the same criterion: two turns in a row triggers a small merit concession (acknowledged explicitly in `hard_rules` for the next turn); four turns in a row triggers a significant concession on a core objective. The streak decays by one on weak turns and fully resets after a major concession is consumed. This creates a direct, learnable feedback loop: sustained good advocacy earns real movement from the opponent.

### 3.3 Personality system

Four opponent personalities shape the *delivery* of arguments but not their substance. A hard rule in the Adversary prompt ensures that personality affects voice and tone only — it never provides an excuse to dodge factual engagement. The Donald and Boris variants have explicit prohibitions against dismissive hand-waving; they must engage with legal substance colourfully rather than avoid it.

### 3.4 Live legal lookup

When the student cites a statute, article, or named Act mid-turn, `case_search.py` extracts the citation with a regex (`Article/Section/Clause + number`, and `Named Act/Directive + year`) and queries Perplexity for the exact provision text. The result is injected into the AI's packet as `LIVE LOOKUP` for that turn. This means the AI argues from the actual text of the provision the student just invoked, not a hallucinated paraphrase — a significant improvement in the accuracy and credibility of its counter-arguments.

---

## 4. Coaching Pipeline

### 4.1 Evaluator architecture

At session end, five stages run sequentially:

1. **Splitter** — routes the transcript into a legal brief (arguments, clauses, statutes) and a negotiation brief (anchoring, concessions, leverage, BATNA usage).
2. **Legal evaluator** — a senior litigation solicitor persona critiques argument accuracy and use of the documents.
3. **Negotiation evaluator** — a Harvard-method expert assesses tactical performance, naming specific criteria by their short name.
4. **Perception evaluator** — the AI opponent speaks candidly in the second person about how it read the student: confidence, composure, tells, trust. This is built from the NoteTaker's private per-turn notes, giving it a perspective genuinely different from the other evaluators.
5. **Criteria grader** — grades the student against each of the 6 Harvard negotiation principles.

### 4.2 Nemotron Super as criteria grader

The criteria grader is the most consequential single evaluation in the pipeline — it produces the score on each principle that feeds both the report and the merit concession tracker. For this stage, `nvidia/nemotron-3-super-120b-a12b` (Nemotron Super) is used instead of Gemini Flash.

Nemotron Super is a 120B-parameter mixture-of-experts model fine-tuned for reward modeling and preference alignment. Unlike a standard instruction-tuned model, it has been trained to make calibrated quality judgments — to distinguish "strong" from "adequate" from "weak" in a principled way. This makes it better suited to criterion-referenced assessment than a model trained primarily for fluent generation.

The call uses streaming with thinking enabled (`reasoning_budget=1024`). The model deliberates privately before producing its answer; the thinking tokens are consumed during streaming but discarded — only the final scored criteria JSON is used. Falls back to Gemini Flash automatically if the NVIDIA key is unavailable.

### 4.3 Weak-spot persistence

After each session, the evaluators' weak spots are compared against the student's historical profile using an LLM-based semantic deduplication step. New observations that are semantically equivalent to existing ones (even if phrased differently) update the existing record rather than creating a new one. The coaching report shows a "Recurring" badge on weak spots that appeared in previous sessions, and a "Signs of improvement" section for historical spots not triggered this session. The Director is given a digest of the student's known weaknesses at the start of each turn and instructed to exploit them.

---

## 5. The 6 Negotiation Criteria

The system is organised around six principles drawn from the Harvard Negotiation Project and related literature:

| # | Criterion | Core question |
|---|-----------|---------------|
| 1 | **Position accuracy** | Did they advocate as forcefully as the facts actually support, without overstating? |
| 2 | **Case preparation** | Did they know the documents and law well enough to never be surprised? |
| 3 | **Interest-based thinking** | Did they look past stated positions to underlying interests? |
| 4 | **Concession discipline** | Did they sequence concessions strategically, never giving something for nothing? |
| 5 | **Tactical flexibility** | Did they switch appropriately between collaborative and competitive modes? |
| 6 | **Realistic expectations** | Were their targets grounded in data, with walk-away limits decided in advance? |

These criteria appear in three places in the system: the coaching report (scored with evidence), the merit concession tracker (real-time assessment per turn), and the guide page (explained for student reference before they negotiate).

---

## 6. Case Design

### 6.1 Structure

Each case is a two-sided JSON file. Both sides share a case background, legal context, and named documents. Each side additionally has a private role description, goal, BATNA, objectives list, and private facts — information known only to their AI. The AI is always assigned the side the student did *not* choose.

The legal context is enriched at case-generation time using Perplexity, which provides real legal background relevant to the scenario. For parody cases (fictional scenarios based on real events), source URLs are suppressed — the legal context is real but the scenario is not.

### 6.2 Parody case generator

A `/cases/generate-parody` endpoint takes a source document (e.g. the text of the Withdrawal Agreement) and a substitution map (e.g. `{"UK": "Pluto", "EU": "The Solar System"}`), and runs a three-stage pipeline: a case parser extracts the negotiation structure, a side builder constructs two asymmetric playable roles, and a name sanitiser replaces any real human names that leaked through. The result is saved as a playable case.

---

## 7. Design Decisions and Trade-offs

**Why ADK rather than a single prompt?** Separating Director (strategy), Adversary (generation), and Predictor (selection) into distinct agents with structured outputs makes each stage inspectable and debuggable. The Director's `criterion_hit` field, the Adversary's candidate list, and the Predictor's `why` field are all logged per turn. A monolithic prompt produces a black box.

**Why deterministic concessions rather than letting the LLM decide?** LLMs are inconsistent across sessions — a model that stonewalls in one conversation may capitulate in another for no pedagogically meaningful reason. The deterministic layer makes the opponent's general trajectory predictable and game-like, while the LLM still controls the specific wording and framing of each turn.

**Why Nemotron for criteria grading only?** The criteria grader is a judgment task (calibrated assessment against defined standards) rather than a generation task (producing plausible text). Nemotron's reward-modeling fine-tuning makes it better suited to judgment; using it for the full pipeline would be expensive and slow. The live opponent uses Gemini Flash for low latency.

**Why no database?** The current user base is a single researcher. JSON files are sufficient, introspectable, and trivially portable. Adding a database would be the right move before multi-user deployment.

---

## 8. Limitations and Future Work

- **Single-user only** — no authentication, no multi-user support; all sessions share one player profile.
- **English only** — all prompts and case content are in English.
- **Parody case quality** — the generator produces cases from any source document, but the resulting legal context can be verbose. A quality-filtering step would help.
- **Voice input latency** — transcription via faster-whisper runs on-device and is fast, but the full round-trip (transcription → LLM → response) is 4–8 seconds on flash without thinking.
- **Nemotron latency** — even with `reasoning_budget=1024`, Nemotron grading adds ~10–20 seconds to the report generation time. Acceptable at session end; would not be appropriate mid-negotiation.
- **Criterion assessment accuracy** — the Director's `criterion_hit` assessment is a single flash-model call with no verification. A more robust approach would run a dedicated evaluator per turn, but the latency cost is prohibitive.
