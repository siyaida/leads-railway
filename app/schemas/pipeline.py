from typing import Literal, Optional
from pydantic import BaseModel


class PipelineRunRequest(BaseModel):
    query: str
    sender_context: Optional[str] = ""
    tone: Literal["direct", "friendly", "formal", "bold"] = "direct"
    channel: Literal["email", "linkedin", "social_dm"] = "email"


class LogEntry(BaseModel):
    step: str
    emoji: str = ""
    message: str
    detail: Optional[str] = None
    timestamp: str


class PipelineStatusResponse(BaseModel):
    session_id: str
    status: str
    result_count: int
    message: str = ""
    current_step: str = ""
    progress_pct: float = 0
    logs: list[LogEntry] = []
