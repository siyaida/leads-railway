import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class SearchResult(Base):
    __tablename__ = "search_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("search_sessions.id"), nullable=False, index=True)
    title = Column(String, nullable=True)
    url = Column(String, nullable=True)
    snippet = Column(Text, nullable=True)
    domain = Column(String, nullable=True)
    position = Column(Integer, nullable=True)
    raw_data = Column(Text, nullable=True)  # JSON text
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("SearchSession", back_populates="results")
