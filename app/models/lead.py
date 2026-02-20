import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("search_sessions.id"), nullable=False, index=True)
    search_result_id = Column(String, ForeignKey("search_results.id"), nullable=True)

    # Contact info
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    email_status = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    headline = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)

    # Location
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)

    # Company info
    company_name = Column(String, nullable=True)
    company_domain = Column(String, nullable=True)
    company_industry = Column(String, nullable=True)
    company_size = Column(String, nullable=True)
    company_linkedin_url = Column(String, nullable=True)

    # Enrichment
    scraped_context = Column(Text, nullable=True)
    personalized_email = Column(Text, nullable=True)
    email_subject = Column(String, nullable=True)
    suggested_approach = Column(Text, nullable=True)

    # Status
    is_selected = Column(Boolean, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    session = relationship("SearchSession", back_populates="leads")
    search_result = relationship("SearchResult")
