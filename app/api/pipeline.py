from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, SessionLocal
from app.core.security import get_current_user
from app.models.user import User
from app.models.search_session import SearchSession
from app.schemas.pipeline import PipelineRunRequest, PipelineStatusResponse, LogEntry
from app.schemas.search import SessionResponse
from app.services import pipeline_service
from app.services import pipeline_log

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


async def _run_pipeline_background(
    session_id: str, query: str, sender_context: str, tone: str = "direct"
) -> None:
    """Wrapper that creates its own DB session for the background task."""
    db = SessionLocal()
    try:
        await pipeline_service.run_pipeline(
            session_id=session_id,
            query=query,
            sender_context=sender_context,
            db=db,
            settings=settings,
            tone=tone,
        )
    finally:
        db.close()


@router.post("/run", response_model=SessionResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_pipeline(
    payload: PipelineRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new lead generation pipeline run."""
    if not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty",
        )

    # Validate required API keys before starting the pipeline
    missing_keys = []
    warnings = []

    if not settings.get_api_key("serper"):
        missing_keys.append("serper")
    if not settings.get_api_key("openai"):
        missing_keys.append("openai")

    if missing_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "API keys not configured",
                "missing_keys": missing_keys,
                "message": (
                    "Please configure your API keys in Settings before generating leads. "
                    "Required: Serper.dev (web search), OpenAI (AI processing). "
                    "Optional: Apollo.io (contact enrichment)."
                ),
            },
        )

    if not settings.get_api_key("apollo"):
        warnings.append(
            "Apollo.io key not configured — leads will be created from "
            "search results only (no contact enrichment)."
        )

    # Create a new session
    session = SearchSession(
        user_id=current_user.id,
        raw_query=payload.query.strip(),
        status="pending",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Launch pipeline in background
    background_tasks.add_task(
        _run_pipeline_background,
        session.id,
        payload.query.strip(),
        payload.sender_context or "",
        payload.tone,
    )

    return SessionResponse.model_validate(session)


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all search sessions for the current user."""
    sessions = (
        db.query(SearchSession)
        .filter(SearchSession.user_id == current_user.id)
        .order_by(SearchSession.created_at.desc())
        .all()
    )
    return [SessionResponse.model_validate(s) for s in sessions]


@router.get("/{session_id}/status", response_model=PipelineStatusResponse)
def get_pipeline_status(
    session_id: str,
    after: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current status of a pipeline run, including activity logs."""
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

    status_messages = {
        "pending": "Pipeline is queued and will start shortly...",
        "searching": "Parsing your query and searching the web...",
        "enriching": "Enriching contacts with company data...",
        "generating": "Generating personalized emails...",
        "completed": f"Pipeline completed successfully with {session.result_count} leads.",
        "failed": "Pipeline encountered an error. Please try again.",
    }

    progress = pipeline_log.get_progress(session_id)
    raw_logs = pipeline_log.get_logs(session_id, after=after)
    log_entries = [LogEntry(**entry) for entry in raw_logs]

    return PipelineStatusResponse(
        session_id=session.id,
        status=session.status,
        result_count=session.result_count or 0,
        message=status_messages.get(session.status, "Unknown status"),
        current_step=progress.get("step", ""),
        progress_pct=progress.get("pct", 0),
        logs=log_entries,
    )
