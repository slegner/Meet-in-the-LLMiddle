# LLMiddle

A gamified legal-negotiation trainer. Pick a side of a real or parody legal dispute, negotiate against a multi-agent AI opponent, and receive a structured coaching report graded against Harvard negotiation principles.

Built as part of PhD research at the University of Cambridge (2025–26) on LLM-mediated legal negotiation training.

---

## Quick start

```bash
cd legal-dojo
./start.sh        # kills stale servers, starts backend (:8000) + frontend (:3000)
# Ctrl+C to stop both
```

Open http://localhost:3000.

---

## Setup

### 1. API keys

You need three API keys. Create `legal-dojo/backend/.env` (this file is gitignored — never commit it):

```
GEMINI_API_KEY=...       # Google AI Studio — free tier works, billed key recommended
PERPLEXITY_API_KEY=...   # Perplexity — used for live legal lookups and case generation
NVIDIA_API_KEY=...       # NVIDIA build.nvidia.com — used for end-of-session criteria grading
```

Where to get each key:
- **Gemini** — https://aistudio.google.com/apikey
- **Perplexity** — https://www.perplexity.ai/settings/api
- **NVIDIA** — https://build.nvidia.com (sign in → get API key)

### 2. Backend (Python 3.11)

```bash
cd legal-dojo/backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 3. Frontend (Node 18+)

```bash
cd legal-dojo/frontend
npm install
```

---

## Running

```bash
cd legal-dojo
./start.sh
```

Or separately:

```bash
# Terminal 1 — backend
cd legal-dojo/backend
.venv/bin/uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd legal-dojo/frontend
npm run dev -- --port 3000
```

> **Port 3000 is required for the frontend.** The backend CORS allow-list is hardcoded to `localhost:3000`.

---

## How it works

### Flow

1. **Pick a case and side** (`/`) — read the case file, choose which party to represent, and select an AI opponent personality.
2. **Negotiate** (`/play`) — turn-based chat. Type or speak your argument; the AI responds with a strategically chosen reply.
3. **End the session** — the coaching report is generated. Download it as PDF or markdown.
4. **Training Profile** (`/profile`) — view your persistent cross-session weak-spot record.

### AI opponent

Each student message triggers a four-agent pipeline:

| Agent | Role |
|-------|------|
| **Director** | Chooses the best tactic (cite a clause, bluff, fake concession, drive compromise…) and assesses which of the 6 criteria the student just demonstrated |
| **Adversary** | Writes 3 candidate replies obeying the Director's instruction |
| **Predictor** | Picks the strongest candidate |
| **NoteTaker** | Records the AI's private read of the opponent — runs in parallel, off the critical path |

The default path uses **Google ADK** (a `SequentialAgent` reply chain in a `ParallelAgent` with NoteTaker). A hand-rolled fallback path (`USE_ADK=0`) makes the same calls via direct `llm.py` calls.

### Concession system

Two layers of concession logic run independently of the LLM:

**Deterministic rules** — start aggressive, never repeat the same demand twice, grudgingly concede when the student makes a strong legal argument (citation heuristic), then drive toward compromise from a randomly-rolled turn (6–12, decided at session start).

**Merit concessions** — the Director scores each student turn against the 6 negotiation criteria. Hit the same criterion strongly 2 turns in a row → small concession. Hit it 4 turns in a row → significant concession on a core objective. The streak decays on weak turns and fully resets after each major concession.

### Live legal lookup

When the student cites a statute, article, or named Act (e.g. "Article 50 TEU", "Employment Rights Act 1996"), the system detects the citation with a regex, queries Perplexity for the exact provision text, and injects the result into the Director's prompt for that turn — so the AI argues from the actual legal text, not a hallucination.

### End-of-session grading

The coaching report runs a 5-stage pipeline:

| Stage | What it does |
|-------|--------------|
| **Splitter** | Routes the transcript into a legal brief and a negotiation brief |
| **Legal evaluator** | Senior litigation solicitor — critiques argument accuracy and use of clauses |
| **Negotiation evaluator** | Harvard-method expert — judges tactical performance against the 6 criteria |
| **Perception evaluator** | The AI opponent speaking privately — how it read the student as a person |
| **Criteria grader** | **Nemotron Super** (120B reasoning model) scores each of the 6 principles with a verbatim quote, a verdict (strong / adequate / weak), and two sentences of feedback |

Nemotron uses streaming with thinking enabled (`reasoning_budget=1024`) — it deliberates before scoring, making the criteria judgments more calibrated than a standard LLM call. Falls back to Gemini Flash if the NVIDIA key is unavailable.

---

## The 6 Negotiation Criteria

The coaching report and the merit concession system both use these Harvard-method principles:

| # | Criterion | What it tests |
|---|-----------|---------------|
| 1 | **Position accuracy** | Advocating as forcefully as the facts support — no overstatement |
| 2 | **Case preparation** | Knowing documents, clauses, and timeline so nothing surprises you |
| 3 | **Interest-based thinking** | Looking past stated positions to the underlying interests |
| 4 | **Concession discipline** | Sequencing concessions strategically — never giving something for nothing |
| 5 | **Tactical flexibility** | Switching between collaborative and competitive modes as the situation demands |
| 6 | **Realistic expectations** | Grounding targets in data; knowing walk-away limits before sitting down |

---

## Cases

Cases live in `backend/data/cases/` as two-sided JSON files. Each side has a `role`, `goal`, `batna`, `objectives`, and `private_facts` (known only to that side's AI).

**Included cases:**

| Case | Description |
|------|-------------|
| **Riverside Lofts** | Landlord–tenant dispute over dilapidations and repair obligations |
| **Pluto's Pluxit Negotiations** | Parody: Article 50 extension talks with Pluto replacing the UK |
| **The Great Flatmate Break-Up Agreement** | Parody: flatmate departure as Brexit at household scale |

New parody cases can be generated via the `/cases/generate-parody` endpoint — paste a source document, provide a substitution map (real name → fictional name), and a full playable case is built and saved automatically.

---

## Opponent Personalities

| Personality | Style |
|-------------|-------|
| **Classic Counsel** | Measured, precise, fact-grounded |
| **The Donald** | Brash, hyperbolic, deal-obsessed — engages with facts through bluster |
| **The Boris** | Theatrical, classical-allusion-heavy, never dodges substance |
| **Randomise** | Drawn at random — you won't know who until they speak |

---

## Environment variables (all optional except API keys)

Set these in `backend/.env`:

| Variable | Default | What it does |
|----------|---------|--------------|
| `GEMINI_API_KEY` | — | **Required.** Google Gemini key |
| `PERPLEXITY_API_KEY` | — | **Required.** Perplexity key for legal lookups |
| `NVIDIA_API_KEY` | — | **Required for Nemotron.** Criteria grader falls back to Gemini without it |
| `USE_ADK` | `1` | `0` to use the hand-rolled fallback opponent instead of Google ADK |
| `LLM_FAST_MODE` | `0` | `1` to collapse the opponent to 2 LLM calls/turn |
| `LLM_THINKING` | `0` | `1` to enable Gemini thinking tokens on flash models |
| `LLM_FLASH_MODEL` | `gemini-2.5-flash` | Gemini model for Director/Adversary/NoteTaker |
| `LLM_PRO_MODEL` | `gemini-2.5-flash` | Gemini model for Predictor/evaluators |
| `NVIDIA_NEMOTRON_MODEL` | `nvidia/nemotron-3-super-120b-a12b` | Nemotron model for criteria grading |
| `COMPROMISE_MIN` | `6` | Earliest turn the AI starts driving toward compromise |
| `COMPROMISE_MAX` | `12` | Latest turn the AI starts driving toward compromise |

---

## Project structure

```
legal-dojo/
  backend/
    main.py              API endpoints (FastAPI)
    adk_negotiator.py    Live AI opponent — Google ADK agent team
    agents.py            Hand-rolled fallback opponent
    concession.py        Deterministic concession state machine + merit streak
    evaluators.py        End-of-session coaching pipeline
    llm.py               Provider seam (Gemini + Nemotron)
    personalities.py     Opponent personality styles
    player_memory.py     Persistent cross-session weak-spot profile (LLM dedup)
    case_search.py       Perplexity legal lookup (case generation + live turn)
    store.py             JSON session/case I/O
    report_pdf.py        PDF coaching report renderer
    data/cases/          Case JSON files
    data/sessions/       Session state (gitignored)
    data/player_profile.json  Cross-session training profile
  frontend/
    app/
      page.tsx           Case picker + side selector
      play/page.tsx      Live negotiation scene
      guide/page.tsx     How-to-negotiate guide
      profile/page.tsx   Training profile editor
      components/
        ReportView.tsx   Coaching report renderer
        GuideButton.tsx  Floating guide button
    lib/api.ts           Typed API client
  start.sh               One-command launcher
  stop.sh                Kill all servers
```
