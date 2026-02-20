import asyncio
import logging
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"


async def _search_single(
    query: str, api_key: str, num_results: int = 10
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

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(SERPER_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    results = []
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
    return results


async def search(
    queries: list[str], num_results: int = 10, api_key_override: Optional[str] = None
) -> list[dict]:
    """Execute multiple search queries concurrently and deduplicate by URL."""
    api_key = api_key_override or settings.get_api_key("serper")
    if not api_key:
        return [
            {
                "error": "Serper API key is not configured. Please add it in Settings.",
            }
        ]

    tasks = [_search_single(query, api_key, num_results) for query in queries]

    all_results = []
    try:
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        seen_urls = set()
        for result_or_error in results_lists:
            if isinstance(result_or_error, Exception):
                logger.error(f"Serper search error: {result_or_error}")
                continue
            for item in result_or_error:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(item)
    except Exception as e:
        logger.error(f"Unexpected error in serper search: {e}")
        return [{"error": str(e)}]

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
