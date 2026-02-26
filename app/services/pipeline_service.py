import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.search_session import SearchSession
from app.models.search_result import SearchResult
from app.models.lead import Lead
from app.services import llm_service, serper_service, apollo_service, scraper_service
from app.services import pipeline_log as log

logger = logging.getLogger(__name__)


def _update_session_status(db: Session, session_id: str, status: str, result_count: Optional[int] = None) -> None:
    """Update the session status and optionally the result count."""
    session = db.query(SearchSession).filter(SearchSession.id == session_id).first()
    if session:
        session.status = status
        session.updated_at = datetime.now(timezone.utc)
        if result_count is not None:
            session.result_count = result_count
        db.commit()


def _is_junk_lead(lead: Lead) -> bool:
    """Check if a lead has no useful contact information."""
    has_name = bool((lead.first_name or "").strip() or (lead.last_name or "").strip())
    has_email = bool((lead.email or "").strip())
    has_linkedin = bool((lead.linkedin_url or "").strip())
    has_company = bool((lead.company_name or "").strip())

    # If no name AND no email AND no linkedin -> junk
    if not has_name and not has_email and not has_linkedin:
        return True
    # If no name AND no company -> also junk (can't identify the lead at all)
    if not has_name and not has_company:
        return True
    return False


async def run_pipeline(
    session_id: str,
    query: str,
    sender_context: str,
    db: Session,
    settings: Settings,
    tone: str = "direct",
    channel: str = "email",
) -> None:
    """Orchestrate the full lead generation pipeline.

    Steps:
    1. Parse the natural language query with LLM
    2. Search Google via Serper
    3. Scrape discovered URLs for context
    4. Enrich contacts with Apollo
    5. Generate personalized emails with LLM
    """
    try:
        # Set initial progress immediately so frontend sees activity
        log.set_progress(session_id, "starting", 2)
        log.add_log(session_id, "starting", "Pipeline started, preparing your search...", emoji="🚀")

        # ── Step 1: Parse query ──────────────────────────────────────
        _update_session_status(db, session_id, "searching")
        log.set_progress(session_id, "query", 5)
        log.add_log(session_id, "query", f"Parsing your query: \"{query}\"", emoji="🔍")

        parsed = await llm_service.parse_query(query)

        # Store parsed query in session
        session = db.query(SearchSession).filter(SearchSession.id == session_id).first()
        if session:
            session.parsed_query = json.dumps(parsed)
            db.commit()

        search_queries = parsed.get("search_queries", [query])
        if not search_queries:
            search_queries = [query]

        titles = parsed.get("job_titles", [])
        locations = parsed.get("locations", [])
        details = []
        if search_queries:
            details.append(f"{len(search_queries)} search queries")
        if titles:
            details.append(f"titles: {', '.join(titles[:3])}")
        if locations:
            details.append(f"locations: {', '.join(locations[:3])}")

        log.add_log(
            session_id, "query",
            f"Query parsed — {', '.join(details) if details else 'ready to search'}",
            emoji="✅",
        )
        log.set_progress(session_id, "search", 15)

        # ── Step 2: Serper search ────────────────────────────────────
        for i, sq in enumerate(search_queries):
            log.add_log(session_id, "search", f"Searching: \"{sq}\"", emoji="🌐")

        # Use first location for Serper geo-targeting
        serper_location = locations[0] if locations else None
        search_results = await serper_service.search(search_queries, location=serper_location)

        valid_results = [r for r in search_results if "error" not in r]
        if not valid_results:
            log.add_log(session_id, "search", "No search results found", emoji="❌")
            _update_session_status(db, session_id, "failed")
            return

        log.add_log(
            session_id, "search",
            f"Found {len(valid_results)} results from web search",
            emoji="✅",
        )
        log.set_progress(session_id, "search", 30)

        # Store search results in DB
        db_results = []
        for item in valid_results:
            sr = SearchResult(
                session_id=session_id,
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("snippet", ""),
                domain=item.get("domain", ""),
                position=item.get("position"),
                raw_data=json.dumps(item.get("raw_data", {})),
            )
            db.add(sr)
            db_results.append(sr)
        db.commit()

        _update_session_status(db, session_id, "enriching", result_count=len(db_results))

        # ── Step 3: Scrape URLs for context ──────────────────────────
        log.set_progress(session_id, "enrich", 35)
        urls_to_scrape = [r.url for r in db_results if r.url][:25]

        log.add_log(
            session_id, "enrich",
            f"Scraping {len(urls_to_scrape)} websites for context...",
            emoji="📄",
        )

        scraped_data = await scraper_service.scrape_many(urls_to_scrape)

        scraped_map = {}
        scraped_count = 0
        for sd in scraped_data:
            url = sd.get("url", "")
            if url and not sd.get("error"):
                context_parts = []
                if sd.get("title"):
                    context_parts.append(sd["title"])
                if sd.get("meta_description"):
                    context_parts.append(sd["meta_description"])
                if sd.get("text_content"):
                    context_parts.append(sd["text_content"][:1000])
                if sd.get("subpage_context"):
                    context_parts.append(sd["subpage_context"][:500])
                scraped_map[url] = " | ".join(context_parts)
                scraped_count += 1

        log.add_log(
            session_id, "enrich",
            f"Scraped {scraped_count}/{len(urls_to_scrape)} websites",
            emoji="✅",
        )
        log.set_progress(session_id, "enrich", 45)

        # ── Step 4: Apollo enrichment ────────────────────────────────
        unique_domains = list(set(r.domain for r in db_results if r.domain))[:15]
        title_keywords = parsed.get("job_titles", [])
        seniority = parsed.get("seniority_levels", [])

        log.add_log(
            session_id, "enrich",
            f"Enriching contacts from {len(unique_domains)} domains...",
            emoji="👥",
        )

        all_leads_data = []
        for i, domain in enumerate(unique_domains):
            try:
                people = await apollo_service.search_people(
                    domain=domain,
                    title_keywords=title_keywords if title_keywords else None,
                    seniority=seniority if seniority else None,
                    locations=locations if locations else None,
                )
                valid_people = [p for p in people if "error" not in p]

                matching_result = next(
                    (r for r in db_results if r.domain == domain), None
                )
                result_id = matching_result.id if matching_result else None
                url_for_domain = matching_result.url if matching_result else ""

                for person in valid_people:
                    person["_search_result_id"] = result_id
                    person["_scraped_context"] = scraped_map.get(url_for_domain, "")
                    all_leads_data.append(person)
                    name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
                    title = person.get("title", "")
                    if name:
                        detail = f"{name}"
                        if title:
                            detail += f" — {title}"
                        log.add_log(session_id, "enrich", f"Found: {detail} at {domain}", emoji="👤")

                pct = 45 + ((i + 1) / max(len(unique_domains), 1)) * 20
                log.set_progress(session_id, "enrich", pct)
            except Exception as e:
                logger.error(f"[{session_id}] Apollo error for domain {domain}: {e}")
                log.add_log(session_id, "enrich", f"Could not enrich {domain}", emoji="⚠️")
                continue

        # If Apollo returned no people, log it but DON'T create empty stub leads
        if not all_leads_data:
            log.add_log(
                session_id, "enrich",
                "No contacts found from enrichment. Creating leads from search results with available context...",
                emoji="ℹ️",
            )
            # Only create leads from search results that have scraped context or emails
            fallback_count = 0
            for sr in db_results:
                context = scraped_map.get(sr.url, "")
                # Only create a fallback lead if we have meaningful context
                if context and sr.domain:
                    lead = Lead(
                        session_id=session_id,
                        search_result_id=sr.id,
                        company_name=sr.title or sr.domain or "",
                        company_domain=sr.domain or "",
                        scraped_context=context,
                    )
                    db.add(lead)
                    fallback_count += 1
            if fallback_count:
                db.commit()
                log.add_log(session_id, "enrich", f"Created {fallback_count} leads from search results", emoji="✅")
            else:
                log.add_log(session_id, "enrich", "No usable leads found. Try refining your search query.", emoji="⚠️")
        else:
            log.add_log(
                session_id, "enrich",
                f"Enriched {len(all_leads_data)} contacts from {len(unique_domains)} companies",
                emoji="✅",
            )
            for person in all_leads_data:
                lead = Lead(
                    session_id=session_id,
                    search_result_id=person.get("_search_result_id"),
                    first_name=person.get("first_name", ""),
                    last_name=person.get("last_name", ""),
                    email=person.get("email", ""),
                    email_status=person.get("email_status", ""),
                    phone=person.get("phone", ""),
                    job_title=person.get("title", ""),
                    headline=person.get("headline", ""),
                    linkedin_url=person.get("linkedin_url", ""),
                    city=person.get("city", ""),
                    state=person.get("state", ""),
                    country=person.get("country", ""),
                    company_name=person.get("organization_name", ""),
                    company_domain=person.get("organization_domain", ""),
                    company_industry=person.get("organization_industry", ""),
                    company_size=person.get("organization_size", ""),
                    company_linkedin_url=person.get("organization_linkedin_url", ""),
                    scraped_context=person.get("_scraped_context", ""),
                )
                db.add(lead)
            db.commit()

        # Post-creation cleanup: remove junk leads that slipped through
        all_session_leads = db.query(Lead).filter(Lead.session_id == session_id).all()
        junk_count = 0
        for lead in all_session_leads:
            if _is_junk_lead(lead):
                db.delete(lead)
                junk_count += 1
        if junk_count:
            db.commit()
            logger.info(f"[{session_id}] Removed {junk_count} junk leads")

        log.set_progress(session_id, "generate", 70)

        # ── Step 5: Generate emails ──────────────────────────────────
        _update_session_status(db, session_id, "generating")

        leads = (
            db.query(Lead)
            .filter(Lead.session_id == session_id, Lead.is_selected == True)
            .all()
        )

        if not leads:
            log.add_log(session_id, "generate", "No leads to generate emails for.", emoji="⚠️")
            _update_session_status(db, session_id, "completed", result_count=0)
            log.set_progress(session_id, "export", 100)
            log.add_log(session_id, "export", "Pipeline complete but no leads were found. Try a different query.", emoji="⚠️")
            return

        channel_label = {"email": "emails", "linkedin": "LinkedIn messages", "social_dm": "social DMs"}.get(channel, "messages")
        log.add_log(
            session_id, "generate",
            f"Generating personalized {channel_label} for {len(leads)} leads...",
            emoji="✉️",
        )

        success_count = 0
        for i, lead in enumerate(leads):
            name = f"{lead.first_name or ''} {lead.last_name or ''}".strip() or lead.company_name or "lead"

            # Skip email generation for leads with no meaningful context
            has_any_info = bool(
                (lead.first_name or "").strip()
                or (lead.company_name or "").strip()
                or (lead.scraped_context or "").strip()
            )
            if not has_any_info:
                log.add_log(session_id, "generate", f"Skipped {name} — insufficient data", emoji="⏭️")
                pct = 70 + ((i + 1) / max(len(leads), 1)) * 25
                log.set_progress(session_id, "generate", pct)
                continue

            log.add_log(session_id, "generate", f"Writing {channel_label.rstrip('s')} for {name}...", emoji="✍️")

            try:
                lead_data = {
                    "first_name": lead.first_name,
                    "last_name": lead.last_name,
                    "job_title": lead.job_title,
                    "company_name": lead.company_name,
                    "company_industry": lead.company_industry,
                    "city": lead.city,
                    "state": lead.state,
                    "country": lead.country,
                    "linkedin_url": lead.linkedin_url,
                    "scraped_context": lead.scraped_context,
                }
                email_result = await llm_service.generate_email(
                    lead_data, sender_context, query, tone=tone, channel=channel
                )
                if "error" not in email_result:
                    lead.personalized_email = email_result.get("body", "")
                    lead.email_subject = email_result.get("subject", "")
                    lead.suggested_approach = email_result.get("suggested_approach", "")
                    success_count += 1
                    log.add_log(session_id, "generate", f"Email ready for {name}", emoji="✅")
                else:
                    logger.warning(
                        f"[{session_id}] Email generation error for lead {lead.id}: {email_result['error']}"
                    )
                    log.add_log(session_id, "generate", f"Failed for {name}: {email_result['error'][:80]}", emoji="⚠️")
            except Exception as e:
                logger.error(f"[{session_id}] Email generation failed for lead {lead.id}: {e}")
                log.add_log(session_id, "generate", f"Error for {name}", emoji="❌")
                continue

            pct = 70 + ((i + 1) / max(len(leads), 1)) * 25
            log.set_progress(session_id, "generate", pct)

        db.commit()

        # ── Done ─────────────────────────────────────────────────────
        final_count = (
            db.query(Lead).filter(Lead.session_id == session_id).count()
        )
        _update_session_status(db, session_id, "completed", result_count=final_count)
        log.set_progress(session_id, "export", 100)
        log.add_log(
            session_id, "export",
            f"Pipeline complete! {final_count} leads ready with {success_count} emails generated.",
            emoji="🎉",
        )

    except Exception as e:
        logger.error(f"[{session_id}] Pipeline failed: {e}", exc_info=True)
        log.add_log(session_id, "error", f"Pipeline failed: {str(e)[:120]}", emoji="❌")
        _update_session_status(db, session_id, "failed")
