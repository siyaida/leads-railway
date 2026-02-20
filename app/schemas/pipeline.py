from typing import Optional
from pydantic import BaseModel


class PipelineRunRequest(BaseModel):
    query: str
    sender_context: Optional[str] = ""


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
