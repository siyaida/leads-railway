import json
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

# ── Default prompts (exposed so the UI can show / override them) ──────────

DEFAULT_EMAIL_SYSTEM_PROMPT = """You are an expert B2B sales email writer. Write personalized, compelling outreach emails
that feel genuine and not spammy. Focus on value proposition and relevance to the recipient's role.

Respond with valid JSON only:
{
  "subject": "Email subject line",
  "body": "Full email body text",
  "suggested_approach": "Brief strategy note about why this approach works for this lead"
}

Keep emails concise (3-4 paragraphs max). Use the lead's name and company details naturally.
Do not use markdown formatting in the JSON values."""

LEAD_INFO_TEMPLATE = """Lead Information:
- Name: {first_name} {last_name}
- Title: {job_title}
- Company: {company_name}
- Industry: {company_industry}
- Location: {city}, {state}, {country}
- LinkedIn: {linkedin_url}
- Company Website Context: {scraped_context}"""


async def _call_openai(
    messages: list[dict],
    api_key: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> dict:
    """Make a direct HTTP call to OpenAI chat completions."""
    model = model or settings.get_model()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(OPENAI_CHAT_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


async def parse_query(raw_query: str) -> dict:
    """Use OpenAI to parse a natural language lead generation query into structured fields."""
    api_key = settings.get_api_key("openai")
    if not api_key:
        return {
            "error": "OpenAI API key is not configured. Please add it in Settings.",
            "search_queries": [raw_query],
            "job_titles": [],
            "industries": [],
            "locations": [],
            "company_size": [],
            "seniority_levels": [],
            "keywords": [],
        }

    system_prompt = """You are a lead generation query parser. Given a natural language query about finding business leads,
extract the following structured information as JSON:

{
  "search_queries": ["list of Google search queries to find relevant companies/people"],
  "job_titles": ["list of target job titles"],
  "industries": ["list of target industries"],
  "locations": ["list of target geographic locations"],
  "company_size": ["list of company size ranges, e.g. '11-50', '51-200'"],
  "seniority_levels": ["list like 'senior', 'manager', 'director', 'vp', 'c_suite'"],
  "keywords": ["additional relevant keywords"]
}

Generate 2-4 diverse Google search queries that would help find companies and decision-makers matching the request.
Always respond with valid JSON only, no markdown formatting."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": raw_query},
    ]

    try:
        result = await _call_openai(messages, api_key, temperature=0.3)
        content = result["choices"][0]["message"]["content"]
        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        parsed = json.loads(content)
        # Ensure all expected keys exist
        defaults = {
            "search_queries": [],
            "job_titles": [],
            "industries": [],
            "locations": [],
            "company_size": [],
            "seniority_levels": [],
            "keywords": [],
        }
        for key, default_val in defaults.items():
            if key not in parsed:
                parsed[key] = default_val
        return parsed
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenAI API error: {e.response.status_code} - {e.response.text}")
        return {
            "error": f"OpenAI API error: {e.response.status_code}",
            "search_queries": [raw_query],
            "job_titles": [],
            "industries": [],
            "locations": [],
            "company_size": [],
            "seniority_levels": [],
            "keywords": [],
        }
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"Failed to parse OpenAI response: {e}")
        return {
            "error": f"Failed to parse AI response: {str(e)}",
            "search_queries": [raw_query],
            "job_titles": [],
            "industries": [],
            "locations": [],
            "company_size": [],
            "seniority_levels": [],
            "keywords": [],
        }
    except Exception as e:
        logger.error(f"Unexpected error in parse_query: {e}")
        return {
            "error": str(e),
            "search_queries": [raw_query],
            "job_titles": [],
            "industries": [],
            "locations": [],
            "company_size": [],
            "seniority_levels": [],
            "keywords": [],
        }


def build_lead_info(lead_data: dict) -> str:
    """Build the lead context string from lead data dict."""
    return LEAD_INFO_TEMPLATE.format(
        first_name=lead_data.get("first_name", "") or "",
        last_name=lead_data.get("last_name", "") or "",
        job_title=lead_data.get("job_title", "Unknown") or "Unknown",
        company_name=lead_data.get("company_name", "Unknown") or "Unknown",
        company_industry=lead_data.get("company_industry", "Unknown") or "Unknown",
        city=lead_data.get("city", "") or "",
        state=lead_data.get("state", "") or "",
        country=lead_data.get("country", "") or "",
        linkedin_url=lead_data.get("linkedin_url", "N/A") or "N/A",
        scraped_context=(lead_data.get("scraped_context", "N/A") or "N/A")[:1000],
    )


async def generate_email(
    lead_data: dict,
    sender_context: str,
    original_query: str,
    custom_system_prompt: Optional[str] = None,
) -> dict:
    """Generate a personalized outreach email for a lead."""
    api_key = settings.get_api_key("openai")
    if not api_key:
        return {
            "error": "OpenAI API key is not configured. Please add it in Settings.",
            "subject": "",
            "body": "",
            "suggested_approach": "",
        }

    lead_info = build_lead_info(lead_data)
    system_prompt = custom_system_prompt or DEFAULT_EMAIL_SYSTEM_PROMPT

    user_prompt = f"""Original search intent: {original_query}

Sender context: {sender_context or 'Not provided'}

{lead_info}

Write a personalized outreach email for this lead."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        result = await _call_openai(messages, api_key, temperature=0.7)
        content = result["choices"][0]["message"]["content"]
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        parsed = json.loads(content)
        return {
            "subject": parsed.get("subject", ""),
            "body": parsed.get("body", ""),
            "suggested_approach": parsed.get("suggested_approach", ""),
        }
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenAI API error during email generation: {e.response.status_code}")
        return {
            "error": f"OpenAI API error: {e.response.status_code}",
            "subject": "",
            "body": "",
            "suggested_approach": "",
        }
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"Failed to parse email generation response: {e}")
        return {
            "error": f"Failed to parse AI response: {str(e)}",
            "subject": "",
            "body": "",
            "suggested_approach": "",
        }
    except Exception as e:
        logger.error(f"Unexpected error in generate_email: {e}")
        return {
            "error": str(e),
            "subject": "",
            "body": "",
            "suggested_approach": "",
        }
