from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ParsedQuery(BaseModel):
    search_queries: List[str] = []
    job_titles: List[str] = []
    industries: List[str] = []
    locations: List[str] = []
    company_size: List[str] = []
    seniority_levels: List[str] = []
    keywords: List[str] = []


class SearchResultResponse(BaseModel):
    id: str
    session_id: str
    title: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None
    domain: Optional[str] = None
    position: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    id: str
    user_id: str
    raw_query: str
    parsed_query: Optional[str] = None
    status: str
    result_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    result_count: int
    message: str = ""
