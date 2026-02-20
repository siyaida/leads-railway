from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.search_session import SearchSession
from app.models.lead import Lead
from app.schemas.lead import LeadResponse, LeadUpdate, EmailUpdate

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.get("/{session_id}", response_model=List[LeadResponse])
def get_leads(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all leads for a specific session."""
    # Verify session belongs to current user
    session = (
        db.query(SearchSession)
        .filter(
            SearchSession.id == session_id,
            SearchSession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    leads = (
        db.query(Lead)
        .filter(Lead.session_id == session_id)
        .order_by(Lead.created_at.desc())
        .all()
    )
    return [LeadResponse.model_validate(lead) for lead in leads]


@router.patch("/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: str,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle is_selected on a lead."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    # Verify the lead's session belongs to the current user
    session = (
        db.query(SearchSession)
        .filter(
            SearchSession.id == lead.session_id,
            SearchSession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if payload.is_selected is not None:
        lead.is_selected = payload.is_selected

    db.commit()
    db.refresh(lead)
    return LeadResponse.model_validate(lead)


@router.patch("/{lead_id}/email", response_model=LeadResponse)
def update_lead_email(
    lead_id: str,
    payload: EmailUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the email content for a lead."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    # Verify access
    session = (
        db.query(SearchSession)
        .filter(
            SearchSession.id == lead.session_id,
            SearchSession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if payload.personalized_email is not None:
        lead.personalized_email = payload.personalized_email
    if payload.email_subject is not None:
        lead.email_subject = payload.email_subject
    if payload.suggested_approach is not None:
        lead.suggested_approach = payload.suggested_approach

    db.commit()
    db.refresh(lead)
    return LeadResponse.model_validate(lead)
