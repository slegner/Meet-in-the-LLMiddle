"""Legal Dojo FastAPI backend (v2 — gamified multi-agent trainer)."""
from __future__ import annotations

from datetime import datetime, timezone

import agents
import evaluators
import player_memory
import report_pdf
import store
import tts as tts_module
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from models import (
    ChatRequest,
    ChatResponse,
    ProfileModel,
    StartRequest,
    StartResponse,
    TtsRequest,
)

app = FastAPI(title="Legal Dojo API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

@app.get("/cases")
def list_cases():
    return store.list_cases()


@app.get("/cases/{case_id}")
def get_case(case_id: str):
    try:
        case = store.load_case(case_id)
    except FileNotFoundError:
        raise HTTPException(404, "Case not found")
    # Expose both sides' goal/BATNA so the player can choose; hide private facts.
    return {
        "id": case["id"],
        "title": case["title"],
        "summary": case.get("summary", ""),
        "background": case["background"],
        "sides": {
            s: {
                "role": case["sides"][s]["role"],
                "goal": case["sides"][s]["goal"],
                "batna": case["sides"][s]["batna"],
            }
            for s in case["sides"]
        },
    }


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@app.post("/sessions", response_model=StartResponse)
def start_session(req: StartRequest):
    try:
        session = store.create_session(req.case_id, req.side)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(400, str(e))
    return StartResponse(session_id=session["id"], side=session["side"], case_title=session["case_title"])


@app.get("/sessions")
def list_sessions():
    return store.list_sessions()


@app.post("/sessions/prune")
def prune_sessions():
    return {"removed": store.prune_empty_sessions()}


@app.delete("/sessions/{sid}")
def delete_session(sid: str):
    return {"deleted": store.delete_session(sid)}


@app.get("/sessions/{sid}")
def get_session(sid: str):
    try:
        return store.load_session(sid)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")


@app.get("/sessions/{sid}/casefile")
def get_casefile(sid: str):
    try:
        session = store.load_session(sid)
        case = store.load_case(session["case_id"])
    except FileNotFoundError:
        raise HTTPException(404, "Not found")
    return store.player_packet(case, session["side"])


@app.post("/sessions/{sid}/chat", response_model=ChatResponse)
def chat(sid: str, req: ChatRequest):
    try:
        session = store.load_session(sid)
        case = store.load_case(session["case_id"])
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    if session.get("status") == "ended":
        raise HTTPException(409, "This negotiation has already ended.")
    turn = agents.run_turn(case, session, req.message)
    store.save_session(session)
    return ChatResponse(adversary=turn["adversary"], turn_number=turn["n"], phase=turn["phase"])


@app.post("/sessions/{sid}/end")
def end_session(sid: str):
    try:
        session = store.load_session(sid)
        case = store.load_case(session["case_id"])
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    report = evaluators.compose_report(case, session)
    session["report"] = report
    session["summary"] = evaluators.short_summary(report)
    session["status"] = "ended"
    session["ended_at"] = datetime.now(timezone.utc).isoformat()
    store.save_session(session)
    player_memory.update_from_session(session, report)
    return report


@app.get("/sessions/{sid}/report")
def get_report(sid: str):
    try:
        session = store.load_session(sid)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    if not session.get("report"):
        raise HTTPException(409, "No report yet — end the negotiation first.")
    return session["report"]


@app.get("/sessions/{sid}/report.pdf")
def get_report_pdf(sid: str):
    try:
        session = store.load_session(sid)
        case = store.load_case(session["case_id"])
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    pdf_bytes = report_pdf.build_report_pdf(case, session)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="legal-dojo-{sid}.pdf"'},
    )


@app.get("/sessions/{sid}/transcript", response_class=PlainTextResponse)
def get_transcript(sid: str):
    try:
        session = store.load_session(sid)
        case = store.load_case(session["case_id"])
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    text = report_pdf.build_transcript_md(case, session)
    return PlainTextResponse(
        text,
        headers={"Content-Disposition": f'attachment; filename="legal-dojo-{sid}.md"'},
    )


# ---------------------------------------------------------------------------
# Player memory (Training Profile)
# ---------------------------------------------------------------------------

@app.get("/tts")
def tts(text: str):
    text = (text or "").strip()
    if not text:
        raise HTTPException(400, "No text to speak.")
    return StreamingResponse(tts_module.stream_tts(text), media_type=tts_module.media_type())


@app.get("/player-memory")
def get_player_memory():
    return player_memory.load_profile()


@app.put("/player-memory")
def put_player_memory(profile: ProfileModel):
    return player_memory.save_profile(profile.model_dump())
