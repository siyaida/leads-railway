import json
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

# ── Default prompts (exposed so the UI can show / override them) ──────────

DEFAULT_EMAIL_SYSTEM_PROMPT = """You write cold outreach emails that sound like a real person typed them in 90 seconds between meetings. Not a copywriter. Not a bot. A busy professional who spotted something interesting about the recipient's company and fired off a quick note.

Rules:
- 4-6 sentences total. That's it. No multi-paragraph essays.
- Open with something specific about THEIR company or role — a recent project, a detail from their website, their industry context. Never a generic intro.
- Vary your sentence length. Mix short punchy lines with one longer sentence. Real people don't write in uniform cadence.
- Write in English always.
- Tone: direct, confident, peer-to-peer. You're not pitching from below — you're one professional offering something relevant to another.
- End with a low-friction ask (quick call, short reply, etc). One sentence. No groveling.

NEVER use any of these — they are instant AI tells:
- "I hope this message finds you well"
- "I wanted to reach out"
- "I came across your profile"
- "leverage", "synergy", "streamline", "optimize", "elevate"
- "I'd love to", "excited to", "delighted to"
- "Looking forward to hearing from you"
- "Best regards", "Warm regards", "Kind regards"
- Bullet-point lists in the email body
- Em-dashes (—)
- Any filler pleasantries or throat-clearing before the point

Subject lines: short (3-7 words), lowercase-friendly, specific to the recipient. No clickbait. No "Quick question" or "Reaching out".

Respond with valid JSON only, no markdown:
{
  "subject": "the subject line",
  "body": "the full email body",
  "suggested_approach": "one-line note on why this angle works for this lead"
}"""


def build_lead_info(lead_data: dict) -> str:
    """Build the lead context string from lead data dict, omitting empty/unknown fields."""
    parts = []

    first = (lead_data.get("first_name") or "").strip()
    last = (lead_data.get("last_name") or "").strip()
    name = f"{first} {last}".strip()
    if name:
        parts.append(f"- Name: {name}")

    title = (lead_data.get("job_title") or "").strip()
    if title:
        parts.append(f"- Title: {title}")

    company = (lead_data.get("company_name") or "").strip()
    if company:
        parts.append(f"- Company: {company}")

    industry = (lead_data.get("company_industry") or "").strip()
    if industry:
        parts.append(f"- Industry: {industry}")

    city = (lead_data.get("city") or "").strip()
    state = (lead_data.get("state") or "").strip()
    country = (lead_data.get("country") or "").strip()
    location_parts = [p for p in [city, state, country] if p]
    if location_parts:
        parts.append(f"- Location: {', '.join(location_parts)}")

    linkedin = (lead_data.get("linkedin_url") or "").strip()
    if linkedin:
        parts.append(f"- LinkedIn: {linkedin}")

    context = (lead_data.get("scraped_context") or "").strip()
    if context:
        parts.append(f"- Company Website Context: {context[:1000]}")

    if not parts:
        return "Lead Information:\n- No detailed information available."

    return "Lead Information:\n" + "\n".join(parts)


# Keep template reference for backward compat with generate.py imports
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
            "company_keywords": [],
            "negative_keywords": [],
        }

    system_prompt = """You are an expert B2B lead generation query parser. Given a natural language query about finding business leads, extract structured information AND generate high-quality Google search queries that will find ACTUAL COMPANIES (not job boards, news articles, or generic directories).

Return this exact JSON structure:

{
  "search_queries": ["list of 5-8 diverse Google search queries"],
  "job_titles": ["list of target job titles"],
  "industries": ["list of target industries"],
  "locations": ["list of target geographic locations"],
  "company_size": ["list of company size ranges, e.g. '11-50', '51-200'"],
  "seniority_levels": ["list like 'senior', 'manager', 'director', 'vp', 'c_suite'"],
  "keywords": ["additional relevant keywords"],
  "company_keywords": ["what these companies do/sell/provide"],
  "negative_keywords": ["terms to exclude like job boards, career pages"]
}

SEARCH QUERY GENERATION RULES — THIS IS CRITICAL:

1. Generate 5-8 diverse queries. Each must include the target location/city/region.

2. Use these PROVEN query patterns (mix at least 4 different types):

   a) Company list queries:
      "[industry] companies in [city] list"
      "top [service] companies [city] [country]"

   b) Business directory queries:
      "[industry] [city] directory"
      "[service] providers [city] site:clutch.co OR site:g2.com"
      "[industry] companies [city] site:crunchbase.com"

   c) LinkedIn company queries:
      "[job title] [industry] [city] site:linkedin.com/in"
      "[industry] company [city] site:linkedin.com/company"

   d) Industry association/member queries:
      "[industry] association members [city]"
      "[industry] chamber of commerce [city]"

   e) News/PR queries (for finding active companies):
      "[industry] [city] startup OR funding OR launch 2024 2025 2026"
      "[industry] companies [region] expansion OR partnership"

   f) Map/local queries:
      "[service] companies near [city]"
      "[industry] firms [city] [country] reviews"

3. NEVER generate generic queries without location.
   GOOD: "AI companies in Riyadh Saudi Arabia list"
   BAD: "AI companies" or "artificial intelligence firms"

4. Include negative_keywords to filter junk: ["jobs", "career", "hiring", "salary", "glassdoor", "indeed", "job board", "wikipedia"]

5. company_keywords should capture WHAT these companies do (e.g., for "AI startups" → ["artificial intelligence", "machine learning", "AI solutions", "AI platform"])

Always respond with valid JSON only, no markdown formatting."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": raw_query},
    ]

    try:
        result = await _call_openai(messages, api_key, temperature=0.4)
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
            "company_keywords": [],
            "negative_keywords": [],
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
            "company_keywords": [],
            "negative_keywords": [],
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
            "company_keywords": [],
            "negative_keywords": [],
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
            "company_keywords": [],
            "negative_keywords": [],
        }


LINKEDIN_SYSTEM_PROMPT = """You write LinkedIn InMail messages that feel like a real professional reaching out after noticing something genuinely interesting about the recipient. Not a mass outreach template. A thoughtful, concise message from one busy professional to another.

Rules:
- 2-3 sentences max, roughly 200 words. LinkedIn messages that run long get ignored.
- Open with something specific about THEIR company, role, or a recent post/project. Show you did your homework.
- Write in English always.
- Tone: professional but conversational. Think how you'd message a 2nd-degree connection you respect.
- End with a clear, low-pressure reason to connect or continue the conversation. One sentence.
- No subject line needed — LinkedIn handles that.

NEVER use any of these — they are instant AI tells:
- "I hope this message finds you well"
- "I wanted to reach out"
- "I came across your profile"
- "leverage", "synergy", "streamline", "optimize", "elevate"
- "I'd love to", "excited to", "delighted to"
- "Looking forward to connecting"
- Bullet-point lists
- Em-dashes (—)
- Any filler pleasantries or throat-clearing before the point

Respond with valid JSON only, no markdown:
{
  "subject": "",
  "body": "the full LinkedIn message",
  "suggested_approach": "one-line note on why this angle works for this lead"
}"""

SOCIAL_DM_SYSTEM_PROMPT = """You write social media DMs (Twitter/X, Instagram) that feel like a real person firing off a quick, direct message. No formalities. No fluff. Just a sharp hook and a clear ask.

Rules:
- 1-2 sentences max, under 280 characters for the body. Brevity is everything.
- Lead with something specific and relevant — a tweet they posted, a project they shipped, their company's recent move.
- Write in English always.
- Tone: casual, direct, peer-to-peer. Think how you'd DM someone you follow and respect.
- One single clear ask or value prop. No stacking multiple requests.
- No greetings like "Hey!" or "Hi there!" — just get into it.

NEVER use any of these:
- "I wanted to reach out"
- "I came across your profile"
- "leverage", "synergy", "streamline", "optimize"
- "I'd love to", "excited to"
- Bullet-point lists
- Em-dashes (—)
- Any formal sign-offs

Respond with valid JSON only, no markdown:
{
  "subject": "",
  "body": "the DM text",
  "suggested_approach": "one-line note on why this angle works for this lead"
}"""

CHANNEL_PROMPTS = {
    "email": DEFAULT_EMAIL_SYSTEM_PROMPT,
    "linkedin": LINKEDIN_SYSTEM_PROMPT,
    "social_dm": SOCIAL_DM_SYSTEM_PROMPT,
}

TONE_INSTRUCTIONS = {
    "direct": "Tone: straight to the point, no fluff, no warm-up. Say what you need to say and stop.",
    "friendly": "Tone: slightly warmer and more conversational. You can be casual, even a little playful, but still concise. Think friendly colleague, not used-car salesman.",
    "formal": "Tone: polished and professional but still human. Suitable for C-suite executives. No slang, but also no stiffness. Think senior partner at a consulting firm.",
    "bold": "Tone: open with a provocative or unexpected statement that breaks the pattern. Be contrarian, challenge an assumption, or lead with a surprising stat. Pattern-interrupt style.",
}


async def generate_email(
    lead_data: dict,
    sender_context: str,
    original_query: str,
    custom_system_prompt: Optional[str] = None,
    tone: str = "direct",
    channel: str = "email",
) -> dict:
    """Generate a personalized outreach message for a lead."""
    api_key = settings.get_api_key("openai")
    if not api_key:
        return {
            "error": "OpenAI API key is not configured. Please add it in Settings.",
            "subject": "",
            "body": "",
            "suggested_approach": "",
        }

    lead_info = build_lead_info(lead_data)
    base_prompt = custom_system_prompt or CHANNEL_PROMPTS.get(channel, DEFAULT_EMAIL_SYSTEM_PROMPT)
    tone_line = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["direct"])
    system_prompt = f"{base_prompt}\n\n{tone_line}"

    # Determine if we have website context
    has_context = bool((lead_data.get("scraped_context") or "").strip())
    if has_context:
        context_instruction = "Ground your opening in a specific detail from their company website context — mention something concrete they do, built, or announced."
    else:
        context_instruction = "Since no website context is available, use the industry and location to craft a relevant angle. Reference a trend or challenge common in their industry/region."

    user_prompt = f"""WHO I AM (the sender):
{sender_context or 'Not provided — keep the pitch generic but still human.'}

WHY I'M LOOKING:
{original_query}

THE LEAD:
{lead_info}

Write a personalized outreach message to this person. {context_instruction} Do not repeat their job title back at them as the opener. Make the connection between what I offer and what they need feel natural, not forced. If you don't have specific information about the lead, never reference information you don't have — instead focus on the industry/market angle."""

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
