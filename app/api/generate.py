import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.search_session import SearchSession
from app.models.lead import Lead
from app.services import llm_service
from app.services.llm_service import DEFAULT_EMAIL_SYSTEM_PROMPT, LEAD_INFO_TEMPLATE, build_lead_info

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generate", tags=["generate"])


# ── Schemas ───────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    sender_context: str = ""
    system_prompt: Optional[str] = None
    tone: Literal["direct", "friendly", "formal", "bold"] = "direct"


class LeadPromptPreview(BaseModel):
    lead_id: str
    lead_name: str
    lead_info: str


class PromptPreviewResponse(BaseModel):
    system_prompt: str
    sender_context: str
    original_query: str
    lead_info_template: str
    leads: list[LeadPromptPreview]


# ── Helpers ───────────────────────────────────────────────────────────────

def _get_session_or_404(session_id: str, user_id: str, db: Session) -> SearchSession:
    session = (
        db.query(SearchSession)
        .filter(
            SearchSession.id == session_id,
            SearchSession.user_id == user_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return session


def _lead_to_dict(lead: Lead) -> dict:
    return {
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "job_title": lead.job_title,
        "company_name": lead.company_name,
        "company_industry": lead.company_industry,
        "city": lead.city,
        "state": lead.state,
        "country": lead.country,
        "linkedin_url": lead.linkedin_url,
        "scraped_context": lead.scraped_context,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/{session_id}/prompt-preview", response_model=PromptPreviewResponse)
def get_prompt_preview(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the system prompt, lead data, and context that would be used for generation."""
    session = _get_session_or_404(session_id, current_user.id, db)

    selected_leads = (
        db.query(Lead)
        .filter(Lead.session_id == session_id, Lead.is_selected == True)
        .all()
    )

    lead_previews = []
    for lead in selected_leads:
        ld = _lead_to_dict(lead)
        name = f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "Unknown"
        lead_previews.append(
            LeadPromptPreview(
                lead_id=lead.id,
                lead_name=name,
                lead_info=build_lead_info(ld),
            )
        )

    return PromptPreviewResponse(
        system_prompt=DEFAULT_EMAIL_SYSTEM_PROMPT,
        sender_context="",
        original_query=session.raw_query,
        lead_info_template=LEAD_INFO_TEMPLATE,
        leads=lead_previews,
    )


@router.post("/{session_id}")
async def generate_emails_for_session(
    session_id: str,
    body: GenerateRequest = GenerateRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger email generation for all selected leads in a session."""
    session = _get_session_or_404(session_id, current_user.id, db)

    leads = (
        db.query(Lead)
        .filter(Lead.session_id == session_id, Lead.is_selected == True)
        .all()
    )

    if not leads:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No selected leads found for this session",
        )

    success_count = 0
    error_count = 0

    for lead in leads:
        try:
            lead_data = _lead_to_dict(lead)
            email_result = await llm_service.generate_email(
                lead_data=lead_data,
                sender_context=body.sender_context or "",
                original_query=session.raw_query,
                custom_system_prompt=body.system_prompt,
                tone=body.tone,
            )

            if "error" not in email_result:
                lead.personalized_email = email_result.get("body", "")
                lead.email_subject = email_result.get("subject", "")
                lead.suggested_approach = email_result.get("suggested_approach", "")
                success_count += 1
            else:
                logger.warning(f"Email generation error for lead {lead.id}: {email_result['error']}")
                error_count += 1
        except Exception as e:
            logger.error(f"Email generation exception for lead {lead.id}: {e}")
            error_count += 1
            continue

    db.commit()

    return {
        "session_id": session_id,
        "total_leads": len(leads),
        "success_count": success_count,
        "error_count": error_count,
        "message": f"Generated emails for {success_count}/{len(leads)} selected leads.",
    }
