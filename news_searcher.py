import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

_NOISE_DOMAINS = [
    "wikipedia.org",
    "find-and-update.company-information.service.gov.uk",
    "beta.companieshouse.gov.uk",
    "companieshouse.gov.uk",
    "gov.uk",
    "chargeflow.io",
    "statista.com",
    "businessofapps.com",
    "reddit.com",
    "linkedin.com",
    "glassdoor.com",
    "indeed.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "tiktok.com",
    "youtube.com",
]

_LEGAL_SUFFIXES = re.compile(
    r"\b(PAYMENTS|HOLDINGS|GROUP|FINANCIAL|TECHNOLOGIES|SERVICES|"
    r"SOLUTIONS|INTERNATIONAL|VENTURES|CAPITAL|MANAGEMENT|"
    r"UK|LTD|LIMITED|PLC|LLP|CORP|INC)\b",
    re.IGNORECASE,
)


def _short_name(company_name: str) -> str:
    """Strip legal/structural suffixes to get a clean trade name for searching."""
    name = _LEGAL_SUFFIXES.sub("", company_name)
    name = re.sub(r"\s{2,}", " ", name).strip().strip(",").strip()
    return name or company_name


def search_company_news(company_name: str) -> list[dict]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return []

    short = _short_name(company_name)
    query = f'"{short}" UK company financial risk lawsuit fine investigation 2024 2025'

    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": 8,
                "search_depth": "basic",
                "include_answer": False,
                "include_raw_content": False,
                "exclude_domains": _NOISE_DOMAINS,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return []

        results = []
        for r in resp.json().get("results", []):
            url = r.get("url", "")
            title = r.get("title", "")
            snippet = r.get("content", "")[:400]

            if any(bad in url.lower() for bad in _NOISE_DOMAINS):
                continue
            if re.search(r"(statistics|stats for \d{4}|filing.history|terms.of.service|services.agreement|privacy.policy|annual.report\b)", title, re.I):
                continue
            if re.search(r"(founding.story|how.it.works|sign.up|pricing|faq)", title, re.I):
                continue

            # Require the company's short name to appear in the title —
            # prevents headlines about third parties polluting sentiment scoring
            short = _short_name(company_name)
            name_words = [w for w in short.lower().split() if len(w) >= 4]
            if name_words and not any(w in title.lower() for w in name_words):
                continue

            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "published": r.get("published_date", ""),
            })

        return results[:5]

    except Exception:
        return []
