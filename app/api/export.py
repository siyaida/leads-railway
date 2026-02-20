import io
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.search_session import SearchSession
from app.models.lead import Lead
from app.services import export_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export", tags=["export"])

VALID_EXPORT_TYPES = {"contacts", "companies", "contacts_companies", "outreach", "full", "custom"}


@router.get("/{session_id}")
def export_leads(
    session_id: str,
    export_type: str = Query("full", description="Export type"),
    custom_fields: Optional[str] = Query(None, description="Comma-separated field keys for custom export"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and return a CSV file for the session's selected leads."""
    if export_type not in VALID_EXPORT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid export_type. Must be one of: {', '.join(sorted(VALID_EXPORT_TYPES))}",
        )

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

    # Get selected leads for this session
    leads = (
        db.query(Lead)
        .filter(Lead.session_id == session_id, Lead.is_selected == True)
        .order_by(Lead.created_at.desc())
        .all()
    )

    if not leads:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No selected leads found for this session",
        )

    # Parse custom fields
    custom_fields_list = (
        [f.strip() for f in custom_fields.split(",") if f.strip()]
        if custom_fields
        else None
    )

    # Generate CSV bytes
    csv_bytes = export_service.generate_csv(
        leads, export_type=export_type, custom_fields=custom_fields_list
    )

    # Build filename: siyada_{type}_{first8chars}_{date}.csv
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"siyada_{export_type}_{session_id[:8]}_{date_str}.csv"

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
