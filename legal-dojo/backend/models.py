"""Pydantic request/response models for the Legal Dojo API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StartRequest(BaseModel):
    case_id: str
    side: str  # "tenant" | "landlord"


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


class ProfileModel(BaseModel):
    display_name: str = "Trainee"
    notes: str = ""
    observations: list[str] = []


# Cases, case files, reports and history are assembled as plain dicts.
JSON = dict[str, Any]
