from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──


class Cadence(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


class ContentType(str, Enum):
    TEXT = "text"
    HTML = "html"


# ── Auth ──


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=30)
    email: str
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


class UserPublic(BaseModel):
    id: int
    username: str
    email: str


# ── Stories & Digest ──


class Story(BaseModel):
    rank: int
    headline: str
    tag: str = ""
    easy: str
    medium: str
    pro: str
    sources: list[str] = []


class DigestResponse(BaseModel):
    period_key: str
    cadence: str
    status: str
    story_count: int
    stories: list[Story]
    created_at: str


# ── Quiz ──


class QuizQuestion(BaseModel):
    id: int
    story_rank: int
    question: str
    options: list[str]
    correct_index: int = Field(ge=0, le=3)
    explanation: str = ""


class QuizResponse(BaseModel):
    period_key: str
    questions: list[QuizQuestion]


# ── Sources ──


class SourceCreate(BaseModel):
    name: str
    url: Optional[str] = None
    source_type: str = "newsletter"


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    active: Optional[bool] = None


class SourceResponse(BaseModel):
    id: int
    name: str
    url: Optional[str]
    source_type: str
    active: bool
    created_at: str


# ── Ingest ──


class IngestRequest(BaseModel):
    content: str
    content_type: ContentType = ContentType.TEXT
    source_id: Optional[int] = None


class IngestResponse(BaseModel):
    id: int
    parse_status: str
    article_count: int = 0
    error: Optional[str] = None


# ── Preferences ──


class PreferenceResponse(BaseModel):
    key: str
    value: str


class PreferenceUpdate(BaseModel):
    value: str


# ── Digest generation ──


class GenerateRequest(BaseModel):
    period_key: Optional[str] = None
    force: bool = False


class GenerateResponse(BaseModel):
    status: str
    digest_id: int


# Forward ref fix
AuthResponse.model_rebuild()
