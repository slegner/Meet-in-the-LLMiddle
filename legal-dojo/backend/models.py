"""Pydantic request/response models for the Legal Dojo API."""
from __future__ import annotations

from typing import Any, List

from pydantic import BaseModel


class StartRequest(BaseModel):
    case_id: str
    side: str  # "tenant" | "landlord"
    personality: str = "default"


class StartResponse(BaseModel):
    session_id: str
    side: str
    case_title: str


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    adversary: str
    turn_number: int
    phase: str
    emotion: str  # "neutral" | "annoyed" | "deal"


class EndRequest(BaseModel):
    accepted: bool = False


class TtsRequest(BaseModel):
    text: str


class ProfileModel(BaseModel):
    display_name: str = "Trainee"
    notes: str = ""
    observations: List[Any] = []  # list of {text, sessions_since_last_seen, added_at}
    timer_idle_secs: int = 30
    timer_response_secs: int = 120


class GenerateCaseRequest(BaseModel):
    query: str          # e.g. "commercial lease flood damage UK"
    save: bool = True   # write to data/cases/{id}.json immediately


# Cases, case files, reports and history are assembled as plain dicts.
JSON = dict[str, Any]
