import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Updated endpoints per Apollo docs (2025)
APOLLO_SEARCH_URL = "https://api.apollo.io/api/v1/mixed_people/api_search"
APOLLO_ENRICH_URL = "https://api.apollo.io/api/v1/people/match"


def _headers(api_key: str) -> dict:
    return {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }


async def search_people(
    domain: str,
    title_keywords: Optional[list[str]] = None,
    seniority: Optional[list[str]] = None,
    locations: Optional[list[str]] = None,
    api_key_override: Optional[str] = None,
) -> list[dict]:
    """Search for people at a company, then enrich each to get full contact data.

    Step 1: POST /api/v1/mixed_people/api_search  → obfuscated results + IDs
    Step 2: POST /api/v1/people/match (per person)  → full email, phone, name
    """
    api_key = api_key_override or settings.get_api_key("apollo")
    if not api_key:
        return [{"error": "Apollo API key is not configured. Please add it in Settings."}]

    # ── Step 1: Search ────────────────────────────────────────────────
    payload: dict = {
        "q_organization_domains_list": [domain],
        "page": 1,
        "per_page": 10,
    }

    if title_keywords:
        payload["person_titles"] = title_keywords
    if seniority:
        payload["person_seniorities"] = seniority
    if locations:
        payload["person_locations"] = locations

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                APOLLO_SEARCH_URL,
                json=payload,
                headers=_headers(api_key),
            )
            resp.raise_for_status()
            search_data = resp.json()

        people_raw = search_data.get("people", [])
        if not people_raw:
            logger.info(f"Apollo search returned 0 people for {domain}")
            return []

        logger.info(f"Apollo search returned {len(people_raw)} people for {domain}")

        # ── Step 2: Enrich each person by ID ──────────────────────────
        results = []
        async with httpx.AsyncClient(timeout=20.0) as client:
            for person_stub in people_raw:
                person_id = person_stub.get("id")
                if not person_id:
                    continue
                try:
                    enrich_resp = await client.post(
                        APOLLO_ENRICH_URL,
                        json={"id": person_id},
                        headers=_headers(api_key),
                    )
                    enrich_resp.raise_for_status()
                    enriched = enrich_resp.json().get("person") or {}

                    org = enriched.get("organization") or {}
                    results.append({
                        "first_name": enriched.get("first_name", ""),
                        "last_name": enriched.get("last_name", ""),
                        "email": enriched.get("email", ""),
                        "email_status": enriched.get("email_status", ""),
                        "phone": _get_phone(enriched),
                        "title": enriched.get("title", ""),
                        "headline": enriched.get("headline", ""),
                        "linkedin_url": enriched.get("linkedin_url", ""),
                        "city": enriched.get("city", ""),
                        "state": enriched.get("state", ""),
                        "country": enriched.get("country", ""),
                        "organization_name": org.get("name", ""),
                        "organization_domain": org.get("primary_domain", domain),
                        "organization_industry": org.get("industry", ""),
                        "organization_size": _get_company_size(org),
                        "organization_linkedin_url": org.get("linkedin_url", ""),
                    })
                except httpx.HTTPStatusError as e:
                    # Log but continue with other people
                    logger.warning(
                        f"Apollo enrich failed for {person_id}: "
                        f"{e.response.status_code} - {e.response.text[:200]}"
                    )
                    # Fall back to stub data from search
                    results.append(_stub_to_result(person_stub, domain))
                except Exception as e:
                    logger.warning(f"Apollo enrich error for {person_id}: {e}")
                    results.append(_stub_to_result(person_stub, domain))

        return results

    except httpx.HTTPStatusError as e:
        logger.error(f"Apollo search error: {e.response.status_code} - {e.response.text[:300]}")
        return [{"error": f"Apollo API error: {e.response.status_code} - {e.response.text[:200]}"}]
    except Exception as e:
        logger.error(f"Unexpected error in Apollo search: {e}")
        return [{"error": str(e)}]


def _stub_to_result(stub: dict, domain: str) -> dict:
    """Convert an obfuscated search stub to a result dict (partial data)."""
    org = stub.get("organization") or {}
    return {
        "first_name": stub.get("first_name", ""),
        "last_name": "",  # search only returns last_name_obfuscated
        "email": "",
        "email_status": "unavailable",
        "phone": "",
        "title": stub.get("title", ""),
        "headline": "",
        "linkedin_url": "",
        "city": "",
        "state": "",
        "country": "",
        "organization_name": org.get("name", ""),
        "organization_domain": domain,
        "organization_industry": "",
        "organization_size": "",
        "organization_linkedin_url": "",
    }


def _get_phone(person: dict) -> str:
    """Extract best phone number from Apollo person data."""
    phone_numbers = person.get("phone_numbers", [])
    if phone_numbers and isinstance(phone_numbers, list):
        for pn in phone_numbers:
            if isinstance(pn, dict) and pn.get("sanitized_number"):
                return pn["sanitized_number"]
            if isinstance(pn, str):
                return pn
    return person.get("phone", "") or ""


def _get_company_size(org: dict) -> str:
    """Extract company size range from Apollo organization data."""
    if not org:
        return ""
    estimated = org.get("estimated_num_employees")
    if estimated:
        return str(estimated)
    size_range = org.get("employee_count_range", "")
    if size_range:
        return str(size_range)
    return ""


async def test_api_key(api_key: str) -> dict:
    """Test an Apollo API key with the new api_search endpoint."""
    payload = {
        "q_organization_domains_list": ["apollo.io"],
        "page": 1,
        "per_page": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                APOLLO_SEARCH_URL,
                json=payload,
                headers=_headers(api_key),
            )
            response.raise_for_status()
            data = response.json()
            people_count = len(data.get("people", []))
            total = data.get("total_entries", 0)
            return {
                "service": "apollo",
                "status": "valid",
                "message": f"API key is valid. Search returned {people_count} result(s) from {total:,} total entries.",
            }
    except httpx.HTTPStatusError as e:
        return {
            "service": "apollo",
            "status": "invalid",
            "message": f"API key validation failed: HTTP {e.response.status_code} - {e.response.text[:200]}",
        }
    except Exception as e:
        return {
            "service": "apollo",
            "status": "invalid",
            "message": f"API key validation failed: {str(e)}",
        }
