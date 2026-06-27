"""Legal Dojo FastAPI backend (v2 — gamified multi-agent trainer)."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import agents
import case_pipeline
import evaluators
import personalities
import player_memory
import report_pdf
import store
import tts as tts_module
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from models import (
    ChatRequest,
    ChatResponse,
    EndRequest,
    GenerateCaseRequest,
    GenerateFromTextRequest,
    GenerateParodyCaseRequest,
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


@app.post("/cases/generate")
def generate_case(req: GenerateCaseRequest):
    try:
        case = case_pipeline.generate_case(req.query)
    except Exception as e:
        raise HTTPException(500, f"Case generation failed: {e}")
    if req.save:
        try:
            store.save_case(case)
        except FileExistsError:
            store.save_case(case, overwrite=True)
    return case


@app.post("/cases/generate-from-text")
def generate_case_from_text(req: GenerateFromTextRequest):
    try:
        case = case_pipeline.generate_case_from_text(req.text)
    except Exception as e:
        raise HTTPException(500, f"Case generation failed: {e}")
    if req.save:
        try:
            store.save_case(case)
        except FileExistsError:
            store.save_case(case, overwrite=True)
    return case


@app.post("/cases/generate-parody")
def generate_parody_case(req: GenerateParodyCaseRequest):
    try:
        case = case_pipeline.generate_parody_case(req.text, req.substitutions)
    except Exception as e:
        raise HTTPException(500, f"Parody case generation failed: {e}")
    if req.save:
        try:
            store.save_case(case)
        except FileExistsError:
            store.save_case(case, overwrite=True)
    return case


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
        "sources": case.get("sources", []),
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

@app.get("/personalities")
def list_personalities():
    return personalities.list_personalities()


@app.post("/sessions", response_model=StartResponse)
def start_session(req: StartRequest):
    try:
        session = store.create_session(req.case_id, req.side, personality=req.personality)
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


@app.delete("/sessions/{sid}/turns/last")
def undo_last_turn(sid: str):
    try:
        session = store.load_session(sid)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    if session.get("status") == "ended":
        raise HTTPException(400, "Cannot undo a completed session")
    turns = session.get("turns", [])
    if not turns:
        raise HTTPException(400, "No turns to undo")
    session["turns"] = turns[:-1]
    # Roll back ai_memory and concession state by one turn if possible
    if session.get("ai_memory"):
        session["ai_memory"] = session["ai_memory"][:-1]
    store.save_session(session)
    return {"turns": len(session["turns"])}


@app.get("/sessions/{sid}/casefile")
def get_casefile(sid: str):
    try:
        session = store.load_session(sid)
        case = store.load_case(session["case_id"])
    except FileNotFoundError:
        raise HTTPException(404, "Not found")
    return store.player_packet(case, session["side"])


_ANNOYED_SIGNALS = {
    "threatening", "threat", "aggressive", "hostile", "disrespectful",
    "bad faith", "bad-faith", "unreasonable", "intimidat", "bully",
    "coercive", "manipulat", "bluffing", "ultimatum", "insult", "rude",
    "abusive", "condescending", "dismissive", "arrogant",
}


def _emotion_from_turn(turn: dict) -> str:
    """Derive emotion from what the AI actually perceived this turn.

    'annoyed' fires when the AI's private note records threatening, hostile,
    or bad-faith behaviour from the player — not just because the AI is in an
    aggressive phase. 'deal' fires when the AI is conceding/compromising.
    """
    note = str(turn.get("note", "")).lower()
    if any(signal in note for signal in _ANNOYED_SIGNALS):
        return "annoyed"
    if turn.get("phase") in ("concede", "compromise"):
        return "deal"
    return "neutral"


@app.post("/sessions/{sid}/chat", response_model=ChatResponse)
def chat(sid: str, req: ChatRequest):
    try:
        session = store.load_session(sid)
        case = store.load_case(session["case_id"])
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    if session.get("status") == "ended":
        raise HTTPException(409, "This negotiation has already ended.")
    student_msg = req.message
    if req.interrupt_count > 0:
        if req.interrupt_count % 3 == 0:
            # Every third interruption: explicitly call it out
            student_msg = (
                "[NOTE: The student has now cut you off mid-speech for the "
                f"{req.interrupt_count}th time. Open your response by firmly telling them "
                "to stop interrupting — e.g. 'I'd appreciate it if you'd let me finish' — "
                "then continue your argument.] " + req.message
            )
        else:
            # Otherwise: just let irritation colour the tone, don't mention it
            student_msg = (
                "[NOTE: The student just cut you off mid-speech. Let a slight edge of "
                "irritation colour your tone — don't address it directly, just continue "
                "with noticeably less patience.] " + req.message
            )
    turn = agents.run_turn(case, session, student_msg)
    if req.interrupt_count > 0:
        turn["student"] = req.message
    store.save_session(session)
    return ChatResponse(adversary=turn["adversary"], turn_number=turn["n"],
                        phase=turn["phase"], emotion=_emotion_from_turn(turn))


@app.post("/sessions/{sid}/nudge", response_model=ChatResponse)
def nudge_session(sid: str):
    """AI takes the initiative when the player has gone silent (timer expired)."""
    try:
        session = store.load_session(sid)
        case = store.load_case(session["case_id"])
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    if session.get("status") == "ended":
        raise HTTPException(409, "This negotiation has already ended.")
    timeout_prompt = (
        "[TIMEOUT: The student has gone silent. Seize the initiative — press your "
        "strongest argument harder, challenge a weakness you spotted, or raise a new "
        "demand. Do NOT mention or acknowledge the silence directly.]"
    )
    turn = agents.run_turn(case, session, timeout_prompt)
    turn["student"] = ""  # don't surface the internal prompt in the transcript
    store.save_session(session)
    phase = turn["phase"]
    return ChatResponse(adversary=turn["adversary"], turn_number=turn["n"],
                        phase=turn["phase"], emotion=_emotion_from_turn(turn))


@app.post("/sessions/{sid}/end")
def end_session(sid: str, req: EndRequest = EndRequest()):
    try:
        session = store.load_session(sid)
        case = store.load_case(session["case_id"])
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    report = evaluators.compose_report(case, session, accepted=req.accepted)
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
    report = session["report"]
    # Backfill full criterion titles for reports saved before the title field was added
    criteria = report.get("criteria") or []
    titles = [c["title"] for c in evaluators._CRITERIA]
    for i, item in enumerate(criteria):
        if i < len(titles):
            item["short_name"] = titles[i]
    return report


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


# ---------------------------------------------------------------------------
# Speech-to-text
# Primary: OpenAI Whisper API (whisper-1) — cloud, high accuracy, legal prompt
# Fallback: faster-whisper local (small/int8) — no API key needed
# ---------------------------------------------------------------------------

# Short bias hint — do NOT make this a sentence Whisper can hallucinate-complete.
_LEGAL_PROMPT = "BATNA, without prejudice, indemnity, liability, injunction."

_openai_client = None
_whisper_model  = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        import openai as _openai_lib
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _openai_client = _openai_lib.OpenAI(api_key=key)
    return _openai_client


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
    return _whisper_model


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    data = await audio.read()
    ext = os.path.splitext(audio.filename or "recording.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(data)
        tmp_path = f.name
    try:
        # Primary: OpenAI Whisper API
        try:
            client = _get_openai_client()
            with open(tmp_path, "rb") as audio_f:
                result = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_f,
                    language="en",
                    prompt=_LEGAL_PROMPT,
                )
            return {"text": result.text.strip()}
        except Exception:
            pass
        # Fallback: local faster-whisper
        segments, _ = _get_whisper().transcribe(tmp_path, language="en", beam_size=5)
        return {"text": " ".join(s.text.strip() for s in segments).strip()}
    finally:
        os.unlink(tmp_path)
