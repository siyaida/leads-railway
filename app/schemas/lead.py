from datetime import datetime
from typing import Optional
from pydantic import BaseModel, model_validator


class LeadResponse(BaseModel):
    id: str
    session_id: str
    search_result_id: Optional[str] = ""
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    email: Optional[str] = ""
    email_status: Optional[str] = ""
    phone: Optional[str] = ""
    job_title: Optional[str] = ""
    headline: Optional[str] = ""
    linkedin_url: Optional[str] = ""
    city: Optional[str] = ""
    state: Optional[str] = ""
    country: Optional[str] = ""
    company_name: Optional[str] = ""
    company_domain: Optional[str] = ""
    company_industry: Optional[str] = ""
    company_size: Optional[str] = ""
    company_linkedin_url: Optional[str] = ""
    scraped_context: Optional[str] = ""
    personalized_email: Optional[str] = ""
    email_subject: Optional[str] = ""
    suggested_approach: Optional[str] = ""
    is_selected: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def none_to_empty(self):
        """Convert None string fields to empty strings."""
        for field_name, field_info in self.model_fields.items():
            if field_name in ("updated_at", "created_at", "is_selected"):
                continue
            val = getattr(self, field_name)
            if val is None:
                object.__setattr__(self, field_name, "")
        return self


class LeadUpdate(BaseModel):
    is_selected: Optional[bool] = None


class EmailUpdate(BaseModel):
    personalized_email: Optional[str] = None
    email_subject: Optional[str] = None
    suggested_approach: Optional[str] = None
