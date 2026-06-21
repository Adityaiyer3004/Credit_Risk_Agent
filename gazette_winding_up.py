"""
Searches The Gazette (official UK public record) for winding-up petitions,
administration notices, and voluntary liquidation notices for a given company.
These are the strongest free proxy for distressed debt signals in the UK.
"""

import re
import requests

_GAZETTE_SEARCH = "https://www.thegazette.co.uk/all-notices/notice"

_INSOLVENCY_KEYWORDS = re.compile(
    r"(winding.up|wound.up|voluntary.liquidation|compulsory.liquidation|"
    r"administration order|appointed administrator|statutory demand|"
    r"liquidator appointed|struck.off|dissolution order|petition.*wind)",
    re.IGNORECASE,
)

_DATE_RE = re.compile(r'\d{1,2}\s+\w+\s+\d{4}')

# Gazette structures notices inside <li> or <article> blocks with class patterns
# We look for result items that contain a heading + description
_RESULT_ITEM_RE = re.compile(
    r'(?:<li[^>]*class="[^"]*gazette-results-item[^"]*"[^>]*>|'
    r'<article[^>]*class="[^"]*(?:notice|result)[^"]*"[^>]*>)'
    r'(.*?)'
    r'(?:</li>|</article>)',
    re.S | re.I,
)

# Alternative: extract result headings from the page
_RESULT_HEADING_RE = re.compile(
    r'<(?:h[2-4]|a)[^>]*class="[^"]*(?:result-title|notice-title|search-result)[^"]*"[^>]*>'
    r'(.*?)</(?:h[2-4]|a)>',
    re.S | re.I,
)

# Detect "no results" page responses
_NO_RESULTS_RE = re.compile(
    r"(no results|no notices found|0 results|didn.t find any)",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_date(text: str) -> str:
    m = _DATE_RE.search(text)
    return m.group(0) if m else ""


def _classify_notice(text: str) -> str:
    t = text.lower()
    if "winding" in t or "wound" in t or "liquidator" in t:
        return "Winding-Up"
    if "administration" in t:
        return "Administration"
    if "statutory demand" in t:
        return "Statutory Demand"
    if "dissolution" in t or "struck" in t:
        return "Dissolution"
    return "Insolvency Notice"


def _is_valid_title(title: str, company_name: str, company_number: str) -> bool:
    """Require the notice title to be a real notice, not a navigation element."""
    if len(title) > 400 or len(title) < 10:
        return False
    # Must not be generic page titles
    generic = ("all notices", "the gazette", "search results", "skip to", "cookie")
    if any(g in title.lower() for g in generic):
        return False
    # Should mention the company name or number, or be an insolvency keyword match
    name_words = [w for w in company_name.lower().split() if len(w) > 3]
    has_name = any(w in title.lower() for w in name_words)
    has_number = company_number.lower() in title.lower()
    has_keyword = bool(_INSOLVENCY_KEYWORDS.search(title))
    return (has_name or has_number) and has_keyword


def search_winding_up_petitions(company_name: str, company_number: str) -> list[dict]:
    """
    Returns confirmed winding-up / insolvency Gazette notices for the company.
    Returns empty list on any network or parse error, or if no valid matches.
    """
    results = []
    seen_titles: set[str] = set()

    # Search by company number first (more precise), then by quoted name
    queries = [company_number, f'"{company_name}"']

    for query in queries:
        try:
            resp = requests.get(
                _GAZETTE_SEARCH,
                params={"text": query, "results-page-size": "10", "sort-by": "relevant"},
                headers={"User-Agent": "CreditRiskAgent/1.0 (credit risk research)"},
                timeout=12,
            )
            if resp.status_code != 200:
                continue

            html = resp.text

            # Bail out if Gazette says no results
            if _NO_RESULTS_RE.search(html):
                continue

            # Try structured notice blocks first
            blocks = _RESULT_ITEM_RE.findall(html)

            # Fallback: try heading-level elements
            if not blocks:
                headings = _RESULT_HEADING_RE.findall(html)
                blocks = headings if headings else []

            for block in blocks:
                clean = _clean(block)

                if not _INSOLVENCY_KEYWORDS.search(clean):
                    continue

                # Extract title — first sentence or up to 200 chars
                title = clean[:200].split(".")[0].strip()

                if not _is_valid_title(title, company_name, company_number):
                    continue

                key = title[:60].lower()
                if key in seen_titles:
                    continue
                seen_titles.add(key)

                results.append({
                    "title": title,
                    "date": _extract_date(clean),
                    "notice_type": _classify_notice(clean),
                })

                if len(results) >= 5:
                    break

        except Exception:
            continue

        if len(results) >= 5:
            break

    return results
