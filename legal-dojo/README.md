# Legal Dojo

A gamified legal-negotiation trainer. Pick a side of a dispute, negotiate
against a strategic **multi-agent AI opponent** in an Ace-Attorney-style scene,
then get qualitative coaching and an exportable transcript. A persistent,
user-editable memory of your behaviour carries across sessions.

## Two halves — they start differently

> ⚠️ `npm run dev` is a **frontend-only** command. The `backend/` folder is a
> Python app with **no `package.json`**, so `npm` cannot run there — it uses
> **uvicorn**.

### Backend — FastAPI on **Python 3.11**, port 8000

```bash
cd legal-dojo/backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --reload --port 8000
```

The backend calls a real LLM. The provider is chosen by `LLM_PROVIDER`
(default `gemini`, using the `GEMINI_API_KEY` already in your environment).
Switching to another provider later is a one-line env change — see `llm.py`.

> Note: `gemini-2.5-pro` has no free-tier quota on the current key, so every
> agent role uses `gemini-2.5-flash`. Override with `LLM_FLASH_MODEL` /
> `LLM_PRO_MODEL` env vars when a paid tier is available.

### Frontend — Next.js, port 3000

```bash
cd legal-dojo/frontend
npm install
npm run dev -- --port 3000
```

Open <http://localhost:3000>. **Run it on port 3000** — the backend's CORS
allow-list is `localhost:3000`, so a browser on 3001 would be blocked.

## The flow

1. **New Simulation** (`/`) — pick a case, choose your side (tenant or
   landlord); you see that side's goal + BATNA.
2. **Negotiate** (`/play`) — the scene: you (left) vs the AI (right), an
   Ace-Attorney dialogue box with a directional pointer and expandable history.
   **Case File** and **Previous Simulations** open as non-destructive overlays;
   only **End** finalizes the report.
3. **Report** — summary + comments from three evaluator agents (Legal,
   Negotiation-expert, Client), weak spots, and a downloadable transcript that
   interleaves the AI's per-turn private notes.
4. **Training Profile** (`/profile`) — view/edit the cross-session memory of
   your tendencies.

## The AI opponent (`backend/agents.py`)

Per student message, four agents collaborate over a shared running memory:

| Agent      | Role                                                               |
| ---------- | ----------------------------------------------------------------- |
| Director   | Advises strategy (bluff, fake concession, reject, reframe…).       |
| Adversary  | Writes 5 candidate replies obeying the directive.                  |
| Predictor  | Forecasts where each candidate leads and picks the best.           |
| NoteTaker  | Records the AI's private inner monologue, appended to `ai_memory`. |

`concession.py` enforces deterministic behaviour rules independent of the LLM:
start aggressive → concede slightly after a strong legal argument → never repeat
a demand more than twice → drive toward compromise from turn 6.

`evaluators.py` produces the end-of-game coaching; `player_memory.py` persists
the editable cross-session profile.

## State

JSON files only, no database. Cases in `backend/data/cases/`, one session file
per simulation in `backend/data/sessions/`, the player profile in
`backend/data/player_profile.json`.
