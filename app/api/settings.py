import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.settings import ApiKeyUpdate, ApiKeyTestResponse, SettingsResponse, ModelInfo, ModelUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/", response_model=SettingsResponse)
def get_settings(
    current_user: User = Depends(get_current_user),
):
    """Return which API keys are configured with masked values."""
    masked = settings.get_all_api_keys_masked()
    return SettingsResponse(
        serper=masked["serper"],
        apollo=masked["apollo"],
        openai=masked["openai"],
        current_model=settings.get_model(),
    )


@router.put("/keys", response_model=SettingsResponse)
def update_keys(
    payload: ApiKeyUpdate,
    current_user: User = Depends(get_current_user),
):
    """Save new API keys and return updated masked status."""
    if payload.serper is not None:
        settings.set_api_key("serper", payload.serper)
    if payload.apollo is not None:
        settings.set_api_key("apollo", payload.apollo)
    if payload.openai is not None:
        settings.set_api_key("openai", payload.openai)

    masked = settings.get_all_api_keys_masked()
    return SettingsResponse(
        serper=masked["serper"],
        apollo=masked["apollo"],
        openai=masked["openai"],
        current_model=settings.get_model(),
    )


@router.post("/test/{service}", response_model=ApiKeyTestResponse)
async def test_api_key(
    service: str,
    current_user: User = Depends(get_current_user),
):
    """Test a specific API key by making a real API call."""
    valid_services = ("serper", "apollo", "openai")
    if service not in valid_services:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid service. Must be one of: {', '.join(valid_services)}",
        )

    api_key = settings.get_api_key(service)
    if not api_key:
        return ApiKeyTestResponse(
            service=service,
            status="invalid",
            message=f"{service} API key is not configured.",
        )

    try:
        if service == "serper":
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://google.serper.dev/search",
                    json={"q": "test", "num": 1},
                    headers={
                        "X-API-KEY": api_key,
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
            return ApiKeyTestResponse(
                service=service,
                status="valid",
                message="Serper API key is valid. Test search succeeded.",
            )

        elif service == "apollo":
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.apollo.io/api/v1/mixed_people/api_search",
                    json={
                        "q_organization_domains_list": ["apollo.io"],
                        "page": 1,
                        "per_page": 1,
                    },
                    headers={
                        "X-Api-Key": api_key,
                        "Content-Type": "application/json",
                        "Cache-Control": "no-cache",
                    },
                )
                response.raise_for_status()
                data = response.json()
                total = data.get("total_entries", 0)
            return ApiKeyTestResponse(
                service=service,
                status="valid",
                message=f"Apollo API key is valid. Found {total:,} entries.",
            )

        elif service == "openai":
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                    },
                )
                response.raise_for_status()
            return ApiKeyTestResponse(
                service=service,
                status="valid",
                message="OpenAI API key is valid. Models endpoint responded successfully.",
            )

    except httpx.HTTPStatusError as e:
        logger.warning(f"API key test failed for {service}: HTTP {e.response.status_code}")
        return ApiKeyTestResponse(
            service=service,
            status="invalid",
            message=f"API key validation failed: HTTP {e.response.status_code} - {e.response.text[:200]}",
        )
    except Exception as e:
        logger.error(f"API key test error for {service}: {e}")
        return ApiKeyTestResponse(
            service=service,
            status="invalid",
            message=f"API key validation failed: {str(e)}",
        )


AVAILABLE_MODELS = [
    # GPT-5.2 family (newest, Dec 2025)
    ModelInfo(
        id="gpt-5.2",
        name="GPT-5.2",
        description="OpenAI's most capable model. 400K context, superior outreach quality, multi-step reasoning.",
        cost="~$2.00/1M tokens",
        recommended_for="email_generation",
    ),
    ModelInfo(
        id="gpt-5.2-mini",
        name="GPT-5.2 Mini",
        description="Fast variant of 5.2. Excellent quality at lower cost. Best for lead generation.",
        cost="~$0.40/1M tokens",
        recommended_for="all",
    ),
    # GPT-4.1 family
    ModelInfo(
        id="gpt-4.1",
        name="GPT-4.1",
        description="Most capable GPT-4 series. Excellent for complex outreach and nuanced emails.",
        cost="~$2.00/1M tokens",
        recommended_for="email_generation",
    ),
    ModelInfo(
        id="gpt-4.1-mini",
        name="GPT-4.1 Mini",
        description="Fast, cheap, excellent quality. Best overall value for lead generation.",
        cost="~$0.40/1M tokens",
        recommended_for="all",
    ),
    ModelInfo(
        id="gpt-4.1-nano",
        name="GPT-4.1 Nano",
        description="Ultra-fast and cheapest. Great for query parsing at high volume.",
        cost="~$0.10/1M tokens",
        recommended_for="query_parsing",
    ),
    # GPT-4o family
    ModelInfo(
        id="gpt-4o",
        name="GPT-4o",
        description="Strong multimodal model. Great for email generation quality.",
        cost="~$2.50/1M tokens",
        recommended_for="email_generation",
    ),
    ModelInfo(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        description="Fast and cost-effective. Good for high-volume lead generation.",
        cost="~$0.15/1M tokens",
        recommended_for="query_parsing",
    ),
    # o-series (reasoning models)
    ModelInfo(
        id="o3",
        name="o3",
        description="Advanced reasoning model. Best for complex research queries and strategic outreach.",
        cost="~$10.00/1M tokens",
        recommended_for="email_generation",
    ),
    ModelInfo(
        id="o3-mini",
        name="o3 Mini",
        description="Fast reasoning model. Good balance of intelligence and speed.",
        cost="~$1.10/1M tokens",
        recommended_for="all",
    ),
    ModelInfo(
        id="o4-mini",
        name="o4 Mini",
        description="Latest reasoning model. Excellent at structured tasks and planning.",
        cost="~$1.10/1M tokens",
        recommended_for="all",
    ),
]


@router.get("/models", response_model=list[ModelInfo])
def get_models(
    current_user: User = Depends(get_current_user),
):
    """Return available OpenAI models with descriptions."""
    return AVAILABLE_MODELS


@router.put("/model")
def update_model(
    payload: ModelUpdate,
    current_user: User = Depends(get_current_user),
):
    """Update the configured OpenAI model."""
    valid_ids = {m.id for m in AVAILABLE_MODELS}
    if payload.model not in valid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model. Must be one of: {', '.join(valid_ids)}",
        )
    settings.set_model(payload.model)
    return {"model": payload.model, "status": "updated"}
