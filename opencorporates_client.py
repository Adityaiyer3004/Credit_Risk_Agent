"""
GLEIF (Global Legal Entity Identifier Foundation) API client.
Completely free — no API key, no registration required.

An LEI (Legal Entity Identifier) is issued to a company after verified KYC
by a GLEIF-accredited Local Operating Unit. Required for all financial market
participants under MiFID II / EMIR. Having a valid LEI is a positive signal;
a lapsed or retired LEI is a governance and compliance red flag.

API docs: https://www.gleif.org/en/lei-data/gleif-api
"""

import requests

_GLEIF_BASE = "https://api.gleif.org/api/v1"


def fetch_opencorporates(company_number: str) -> dict:
    """
    Named fetch_opencorporates to avoid changing the import across the codebase.
    Searches GLEIF by Companies House registration number + GB jurisdiction.
    Returns {} on failure or if no LEI found.
    """
    try:
        resp = requests.get(
            f"{_GLEIF_BASE}/lei-records",
            params={
                "filter[entity.registeredAs]": company_number.upper(),
                "filter[entity.jurisdiction]": "GB",
                "page[size]": 1,
            },
            headers={"Accept": "application/vnd.api+json"},
            timeout=10,
        )
        if resp.status_code != 200:
            return {}

        records = resp.json().get("data", [])
        if not records:
            return {}

        rec = records[0]
        attrs = rec.get("attributes", {})
        entity = attrs.get("entity", {})
        registration = attrs.get("registration", {})

        lei_code = rec.get("id", "")
        entity_status = entity.get("status", "")
        lei_status = registration.get("status", "")
        next_renewal = registration.get("nextRenewalDate", "")[:10]
        legal_form = (entity.get("legalForm") or {}).get("id", "")

        return {
            "lei": lei_code,
            "entity_status": entity_status,
            "lei_status": lei_status,        # ISSUED | LAPSED | RETIRED | PENDING_TRANSFER
            "next_renewal": next_renewal,
            "legal_form": legal_form,
            "source": "GLEIF",
        }

    except Exception:
        return {}
