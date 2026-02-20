import csv
import io
from typing import Dict, List, Optional

from app.models.lead import Lead

# Maps internal field keys → CSV header name + extractor
FIELD_DEFINITIONS: Dict[str, Dict] = {
    "first_name": {"header": "First Name", "get": lambda l: l.first_name or ""},
    "last_name": {"header": "Last Name", "get": lambda l: l.last_name or ""},
    "email": {"header": "Email", "get": lambda l: l.email or ""},
    "phone": {"header": "Phone Number", "get": lambda l: l.phone or ""},
    "job_title": {"header": "Job Title", "get": lambda l: l.job_title or ""},
    "linkedin_url": {"header": "LinkedIn URL", "get": lambda l: l.linkedin_url or ""},
    "company_name": {"header": "Company Name", "get": lambda l: l.company_name or ""},
    "company_domain": {"header": "Company Domain Name", "get": lambda l: l.company_domain or ""},
    "website_url": {
        "header": "Website URL",
        "get": lambda l: f"https://{l.company_domain}" if l.company_domain else "",
    },
    "industry": {"header": "Industry", "get": lambda l: l.company_industry or ""},
    "company_size": {"header": "Number of Employees", "get": lambda l: l.company_size or ""},
    "company_linkedin_url": {
        "header": "Company LinkedIn URL",
        "get": lambda l: l.company_linkedin_url or "",
    },
    "description": {
        "header": "Description",
        "get": lambda l: " | ".join(
            filter(None, [l.headline, (l.scraped_context or "")[:500]])
        ),
    },
    "city": {"header": "City", "get": lambda l: l.city or ""},
    "state": {"header": "State/Region", "get": lambda l: l.state or ""},
    "country": {"header": "Country/Region", "get": lambda l: l.country or ""},
    "street_address": {"header": "Street Address", "get": lambda _: ""},
    "email_subject": {"header": "Email Subject", "get": lambda l: l.email_subject or ""},
    "personalized_email": {
        "header": "Personalized Email Draft",
        "get": lambda l: l.personalized_email or "",
    },
    "suggested_approach": {
        "header": "Suggested Approach",
        "get": lambda l: l.suggested_approach or "",
    },
}

# Ordered field keys for each export type
EXPORT_TYPES: Dict[str, List[str]] = {
    "contacts": [
        "first_name", "last_name", "email", "phone", "job_title", "linkedin_url",
    ],
    "companies": [
        "company_name", "company_domain", "website_url", "industry",
        "company_size", "company_linkedin_url",
    ],
    "contacts_companies": [
        "first_name", "last_name", "email", "phone", "job_title", "linkedin_url",
        "company_name", "company_domain", "website_url", "industry",
        "company_size",
    ],
    "outreach": [
        "first_name", "last_name", "email", "job_title", "company_name",
        "email_subject", "personalized_email", "suggested_approach",
    ],
    "full": list(FIELD_DEFINITIONS.keys()),
}

ALL_FIELD_KEYS = list(FIELD_DEFINITIONS.keys())


def get_export_fields(
    export_type: str = "full",
    custom_fields: Optional[List[str]] = None,
) -> List[str]:
    """Return the list of field keys for a given export type."""
    if export_type == "custom" and custom_fields:
        return [f for f in custom_fields if f in FIELD_DEFINITIONS]
    return EXPORT_TYPES.get(export_type, EXPORT_TYPES["full"])


def generate_csv(
    leads: List[Lead],
    export_type: str = "full",
    custom_fields: Optional[List[str]] = None,
) -> bytes:
    """Generate a HubSpot-ready CSV from a list of Lead objects.

    Returns UTF-8 BOM encoded CSV bytes ready for download.
    """
    fields = get_export_fields(export_type, custom_fields)
    fieldnames = [FIELD_DEFINITIONS[f]["header"] for f in fields]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
    writer.writeheader()

    for lead in leads:
        row = {
            FIELD_DEFINITIONS[f]["header"]: FIELD_DEFINITIONS[f]["get"](lead)
            for f in fields
        }
        writer.writerow(row)

    csv_content = output.getvalue()
    output.close()

    # UTF-8 BOM encoding for Excel compatibility
    bom = b"\xef\xbb\xbf"
    return bom + csv_content.encode("utf-8")
