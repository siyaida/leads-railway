import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class SearchSession(Base):
    __tablename__ = "search_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    raw_query = Column(Text, nullable=False)
    parsed_query = Column(Text, nullable=True)  # JSON text
    status = Column(
        String,
        default="pending",
        nullable=False,
    )  # pending, searching, enriching, generating, completed, failed
    result_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", backref="sessions")
    results = relationship("SearchResult", back_populates="session", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="session", cascade="all, delete-orphan")
