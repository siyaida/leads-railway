import asyncio
import logging
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"

# Domains that produce noise (job boards, reference sites, etc.)
NOISE_DOMAINS = {
    "indeed.com", "glassdoor.com", "linkedin.com",
    "wikipedia.org", "wikidata.org",
    "salary.com", "payscale.com", "ziprecruiter.com",
    "monster.com", "careerbuilder.com", "simplyhired.com",
    "facebook.com", "twitter.com", "x.com", "instagram.com",
    "youtube.com", "tiktok.com", "reddit.com",
    "quora.com", "medium.com",
    "amazon.com", "ebay.com", "alibaba.com",
    "gov.sa", "mc.gov.sa",
}

# Location to Google gl/hl country code mapping
LOCATION_COUNTRY_CODES = {
    "saudi arabia": ("sa", "en"),
    "saudi": ("sa", "en"),
    "ksa": ("sa", "en"),
    "riyadh": ("sa", "en"),
    "jeddah": ("sa", "en"),
    "dammam": ("sa", "en"),
    "uae": ("ae", "en"),
    "dubai": ("ae", "en"),
    "abu dhabi": ("ae", "en"),
    "qatar": ("qa", "en"),
    "doha": ("qa", "en"),
    "bahrain": ("bh", "en"),
    "kuwait": ("kw", "en"),
    "oman": ("om", "en"),
    "egypt": ("eg", "en"),
    "cairo": ("eg", "en"),
    "jordan": ("jo", "en"),
    "united states": ("us", "en"),
    "usa": ("us", "en"),
    "uk": ("gb", "en"),
    "united kingdom": ("gb", "en"),
    "london": ("gb", "en"),
    "germany": ("de", "en"),
    "france": ("fr", "en"),
    "india": ("in", "en"),
}


def _get_geo_params(location: Optional[str]) -> dict:
    """Get gl and hl parameters based on location string."""
    if not location:
        return {}
    loc_lower = location.lower().strip()
    for key, (gl, hl) in LOCATION_COUNTRY_CODES.items():
        if key in loc_lower:
            return {"gl": gl, "hl": hl}
    return {}


def _is_noise_url(domain: str) -> bool:
    """Check if a domain is a known noise source."""
    domain_lower = domain.lower()
    for noise in NOISE_DOMAINS:
        if noise in domain_lower:
            return True
    return False


async def _search_single(
    query: str, api_key: str, num_results: int = 20, location: Optional[str] = None,
) -> list[dict]:
    """Execute a single search query against the Serper API."""
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "num": num_results,
    }
    if location:
        payload["location"] = location

    # Add geo-targeting parameters
    geo = _get_geo_params(location)
    payload.update(geo)

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(SERPER_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    results = []

    # Extract from organic results
    organic = data.get("organic", [])
    for i, item in enumerate(organic):
        url = item.get("link", "")
        domain = ""
        if url:
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.replace("www.", "")
            except Exception:
                domain = ""

        if _is_noise_url(domain):
            continue

        results.append(
            {
                "title": item.get("title", ""),
                "url": url,
                "snippet": item.get("snippet", ""),
                "domain": domain,
                "position": i + 1,
                "raw_data": item,
            }
        )

    # Extract from knowledge graph if present
    kg = data.get("knowledgeGraph", {})
    if kg:
        kg_website = kg.get("website", "")
        if kg_website:
            try:
                parsed = urlparse(kg_website if kg_website.startswith("http") else f"https://{kg_website}")
                kg_domain = parsed.netloc.replace("www.", "")
                if not _is_noise_url(kg_domain):
                    results.append({
                        "title": kg.get("title", ""),
                        "url": kg_website if kg_website.startswith("http") else f"https://{kg_website}",
                        "snippet": kg.get("description", ""),
                        "domain": kg_domain,
                        "position": 0,
                        "raw_data": kg,
                    })
            except Exception:
                pass

    # Extract from places results if present
    places = data.get("places", [])
    for place in places:
        place_url = place.get("website", "")
        if place_url:
            try:
                parsed = urlparse(place_url if place_url.startswith("http") else f"https://{place_url}")
                place_domain = parsed.netloc.replace("www.", "")
                if not _is_noise_url(place_domain):
                    results.append({
                        "title": place.get("title", ""),
                        "url": place_url if place_url.startswith("http") else f"https://{place_url}",
                        "snippet": place.get("address", ""),
                        "domain": place_domain,
                        "position": 0,
                        "raw_data": place,
                    })
            except Exception:
                pass

    return results


async def search(
    queries: list[str], num_results: int = 20, api_key_override: Optional[str] = None,
    location: Optional[str] = None,
) -> list[dict]:
    """Execute multiple search queries concurrently and deduplicate by URL."""
    api_key = api_key_override or settings.get_api_key("serper")
    if not api_key:
        return [
            {
                "error": "Serper API key is not configured. Please add it in Settings.",
            }
        ]

    tasks = [_search_single(query, api_key, num_results, location=location) for query in queries]

    all_results = []
    try:
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        seen_urls = set()
        seen_domains = set()
        for result_or_error in results_lists:
            if isinstance(result_or_error, Exception):
                logger.error(f"Serper search error: {result_or_error}")
                continue
            for item in result_or_error:
                url = item.get("url", "")
                domain = item.get("domain", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    # Allow multiple URLs per domain but track it
                    if domain:
                        seen_domains.add(domain)
                    all_results.append(item)
    except Exception as e:
        logger.error(f"Unexpected error in serper search: {e}")
        return [{"error": str(e)}]

    logger.info(f"Serper search: {len(all_results)} results from {len(seen_domains)} unique domains across {len(queries)} queries")
    return all_results


async def test_api_key(api_key: str) -> dict:
    """Test a Serper API key by making a simple search request."""
    try:
        results = await _search_single("test", api_key, num_results=1)
        return {
            "service": "serper",
            "status": "valid",
            "message": f"API key is valid. Test search returned {len(results)} result(s).",
        }
    except httpx.HTTPStatusError as e:
        return {
            "service": "serper",
            "status": "invalid",
            "message": f"API key validation failed: HTTP {e.response.status_code} - {e.response.text[:200]}",
        }
    except Exception as e:
        return {
            "service": "serper",
            "status": "invalid",
            "message": f"API key validation failed: {str(e)}",
        }
