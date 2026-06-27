# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Legal Dojo — a gamified legal-negotiation trainer. A student picks a side of a dispute and negotiates against a strategic, Gemini-backed AI opponent in an Ace-Attorney-style scene, then receives a qualitative coaching report. FastAPI backend + Next.js frontend, state in JSON files (no database).

## Commands

```bash
# Run everything (kills stale servers, starts both, streams logs, Ctrl+C stops both)
./start.sh                      # from legal-dojo/
./stop.sh                       # kill all servers

# Backend only (FastAPI, port 8000) — Python 3.11, uses backend/.venv
cd backend && .venv/bin/uvicorn main:app --reload --port 8000

# Frontend only (Next.js, port 3000)
cd frontend && npm run dev -- --port 3000
npm run build                   # type-check + production build (the only "test")
npx tsc --noEmit                # type-check alone
```

There is **no automated test suite**. Verification is end-to-end: hit the API with `curl` (`POST /sessions` then `/sessions/{id}/chat`, `/end`, `/report.pdf`) or play through the UI.

### Hard requirements / gotchas
- **Run the frontend on port 3000.** The backend CORS allow-list is `localhost:3000` only (`backend/main.py`); 3001 gets blocked.
- **`start.sh` targets macOS bash 3.2** — do not use `wait -n` or other bash 4+ features.
- **Backend changes need a restart** to load (uvicorn `--reload` only watches Python files; ADK agents are built at import). After editing prompts/agents, restart.
- **Gemini key** lives in `backend/.env` as `GEMINI_API_KEY` (gitignored; loaded via python-dotenv with `override=True`). The free tier caps flash at ~20 requests/day — a billed key is required for real use. `gemini-2.5-pro` has no free-tier quota.
- The startup log line *"Both GOOGLE_API_KEY and GEMINI_API_KEY are set"* is benign: `adk_negotiator.py` mirrors the one key into `GOOGLE_API_KEY` (ADK auth) while `llm.py` reads `GEMINI_API_KEY`.

## Architecture

### Two LLM code paths (this is the key thing to understand)
1. **`adk_negotiator.py` — the live opponent (default, `USE_ADK=1`).** A Google ADK agent team runs per turn: a `SequentialAgent` reply chain **Director → Adversary (3 candidates) → Predictor (picks best)**, wrapped in a `ParallelAgent` with the **NoteTaker** (which only reads seeded state, so it runs off the critical path). Agents collaborate via **shared ADK session state**, seeded each turn with the rendered case packet, transcript, memory, and the concession directive; outputs are read back from state. Models: flash for Director/Adversary, flash-lite for Predictor/NoteTaker, thinking disabled. See `docs/adk_architecture.png`.
2. **`agents.py` — hand-rolled fallback (`USE_ADK=0`).** Same Director/Adversary/Predictor/NoteTaker roles via direct `llm.py` calls. `LLM_FAST_MODE=1` collapses it to 2 calls/turn. `agents.run_turn` dispatches to the ADK path when `USE_ADK` is set.

Both paths produce the **same turn dict shape** (`student`, `adversary`, `phase`, `directive`, `candidates`, `selection`, `note`, `tokens`) appended to the session, so the API/frontend never change.

### `llm.py` — provider seam
All non-ADK model calls go through `llm_generate()` / `generate_json()`, dispatched by `LLM_PROVIDER` (default `gemini`). This is the single point to swap providers; Anthropic/OpenAI branches are stubbed. Per-role model map; thinking disabled on flash.

### `concession.py` — deterministic behaviour (LLM-independent)
A state machine injected into the Director's prompt every turn: start aggressive → **concede slightly** when the student makes a strong legal argument (keyword/citation heuristic) → never repeat a demand >2× → **drive compromise** from a turn rolled once per session in `[COMPROMISE_MIN, COMPROMISE_MAX]` (default 6–12, stored in `concession_state.compromise_turn`). `init_state()` seeds this; `ensure()` backfills older sessions; `plan_turn()` returns the `phase` + `directive` text.

### Report pipeline — `evaluators.py`
On `/end`: a **splitter** routes the transcript into a Legal brief and a Negotiation brief, fed to the **Legal** and **Negotiation** evaluators. The **third evaluator is "how your opponent saw you"** (`evaluate_perception`) — fed the AI's private per-turn NoteTaker notes, NOT a client-interests agent. Returns summary + per-agent comments + weak spots + `tokens_used`. `report_pdf.py` renders the downloadable PDF (`/sessions/{id}/report.pdf`, fpdf2; text is sanitised to Latin-1).

### State — `store.py`, `player_memory.py`
JSON only. Cases in `backend/data/cases/*.json` (two-sided: `sides.tenant` / `sides.landlord`, each with role/goal/BATNA/private_facts; the AI gets the side the player did **not** pick — `ai_packet()`). One session file per game in `backend/data/sessions/` (gitignored); `list_sessions()` hides 0-turn drafts. `player_memory.py` is a persistent, user-editable profile (`data/player_profile.json`) that accrues weak spots across sessions and feeds a digest into the Director.

### Frontend (`frontend/`, Next.js App Router + TS)
`app/page.tsx` (pick case + side) → `app/play/page.tsx` (the scene; reads `?sid=`). **Case File** and **Previous Simulations** are non-destructive overlays over the live scene — only **End** finalizes the report. `app/profile/page.tsx` edits the training profile. All API calls and types are in `lib/api.ts` (`API_BASE`, default `http://localhost:8000`).

## Key env vars (backend/.env)
`GEMINI_API_KEY` (required), `USE_ADK` (default 1), `LLM_PROVIDER` (default gemini), `LLM_FLASH_MODEL` / `LLM_LITE_MODEL` / `LLM_PRO_MODEL`, `LLM_FAST_MODE`, `LLM_THINKING`, `COMPROMISE_MIN` / `COMPROMISE_MAX`.
