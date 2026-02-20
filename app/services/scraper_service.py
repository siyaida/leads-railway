import asyncio
import logging
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Limit concurrent scraping to 5 at a time
_semaphore = asyncio.Semaphore(5)

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)


async def scrape(url: str) -> dict:
    """Scrape a URL and extract useful content for lead enrichment."""
    async with _semaphore:
        return await _scrape_impl(url)


async def _scrape_impl(url: str) -> dict:
    """Internal scraping implementation."""
    result = {
        "url": url,
        "title": "",
        "meta_description": "",
        "text_content": "",
        "emails": [],
        "social_links": [],
        "error": None,
    }

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=True, verify=False
        ) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            result["error"] = f"Non-HTML content type: {content_type}"
            return result

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.decompose()

        # Title
        title_tag = soup.find("title")
        if title_tag:
            result["title"] = title_tag.get_text(strip=True)

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            result["meta_description"] = meta_desc.get("content", "")

        # Text content (first 2000 chars)
        body = soup.find("body")
        if body:
            text = body.get_text(separator=" ", strip=True)
            # Clean up excessive whitespace
            text = re.sub(r"\s+", " ", text)
            result["text_content"] = text[:2000]

        # Extract emails from the full HTML
        full_text = soup.get_text()
        found_emails = set(EMAIL_REGEX.findall(full_text))
        # Filter out common false positives
        filtered_emails = [
            e
            for e in found_emails
            if not e.endswith((".png", ".jpg", ".gif", ".css", ".js"))
            and "example.com" not in e
            and "sentry.io" not in e
        ]
        result["emails"] = list(filtered_emails)[:10]

        # Social links
        social_domains = [
            "linkedin.com",
            "twitter.com",
            "x.com",
            "facebook.com",
            "instagram.com",
            "youtube.com",
            "github.com",
        ]
        social_links = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            for domain in social_domains:
                if domain in href:
                    social_links.add(href)
                    break
        result["social_links"] = list(social_links)[:20]

    except httpx.TimeoutException:
        result["error"] = "Request timed out after 10 seconds"
    except httpx.HTTPStatusError as e:
        result["error"] = f"HTTP {e.response.status_code}"
    except Exception as e:
        result["error"] = f"Scraping failed: {str(e)[:200]}"

    return result


async def scrape_many(urls: list[str]) -> list[dict]:
    """Scrape multiple URLs concurrently (limited by semaphore)."""
    tasks = [scrape(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    final = []
    for r in results:
        if isinstance(r, Exception):
            final.append({"url": "", "error": str(r)})
        else:
            final.append(r)
    return final
