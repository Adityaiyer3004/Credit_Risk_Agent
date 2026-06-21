"""
Fetches filed annual accounts from Companies House (iXBRL format),
extracts financial figures, computes ratios, and calculates the
Altman Z'-Score — the gold-standard academic model for private company
credit distress prediction (Altman 1983, revised 2000).

Z' = 0.717X1 + 0.847X2 + 3.107X3 + 0.420X4 + 0.998X5
  X1 = Working Capital / Total Assets
  X2 = Retained Earnings / Total Assets (approximated via net assets)
  X3 = EBIT / Total Assets (approximated via profit/loss)
  X4 = Book Value of Equity / Total Liabilities
  X5 = Sales / Total Assets

Zones: Z' > 2.9 Safe  |  1.23–2.9 Grey  |  < 1.23 Distress
"""

import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY")
CH_BASE = "https://api.company-information.service.gov.uk"
DOC_BASE = "https://document-api.company-information.service.gov.uk"

_ACCOUNT_TYPES = ("AA", "ACCOUNTS", "LLP_AA", "LLP_ACCOUNTS")

# iXBRL tag name candidates — ordered from most to least preferred
_TAGS = {
    "turnover": [
        "TurnoverRevenue", "Turnover", "Revenue", "GrossProfitLoss",
        "RevenueFromContractsWithCustomers",
    ],
    "profit_loss": [
        "ProfitLoss", "ProfitLossForPeriod",
        "ProfitLossOnOrdinaryActivitiesAfterTax", "NetIncomeLoss",
    ],
    "net_assets": [
        "NetAssetsLiabilities", "TotalNetAssetsLiabilities",
        "NetAssetsLiabilitiesIncludingPensionAssetLiability",
        "Equity", "ShareholdersEquityIncludingMinorityInterests",
    ],
    "current_assets": [
        "CurrentAssets", "TotalCurrentAssets",
    ],
    "current_liabilities": [
        "CreditorsAmountsFallingDueWithinOneYear",
        "CreditorsDueWithinOneYear", "CurrentLiabilities",
        "TotalCurrentLiabilities",
    ],
    "total_assets": [
        "Assets", "TotalAssets",
        "TotalAssetsLessCurrentLiabilities",
        "FixedAssets",
    ],
    "cash": [
        "CashBankInHand", "CashBankOnHand",
        "CashCashEquivalents", "Cash",
    ],
    "long_term_liabilities": [
        "CreditorsAmountsFallingDueAfterMoreThanOneYear",
        "LongTermBorrowings", "NonCurrentLiabilities",
        "CreditorsDueAfterOneYear",
    ],
    "retained_earnings": [
        "RetainedEarnings", "ProfitLossAccountReserve",
        "AccumulatedProfitLoss", "RetainedEarningsAccumulatedLosses",
    ],
    "ebit": [
        "OperatingProfitLoss", "ProfitLossOnOrdinaryActivitiesBeforeTax",
        "EBIT", "EarningsBeforeInterestAndTax",
    ],
}

_NONFRACTION_RE = re.compile(
    r'<ix:nonFraction((?:\s+[^>]+)*)\s*>(.*?)</ix:nonFraction>',
    re.IGNORECASE | re.DOTALL,
)
_ATTR_NAME_RE = re.compile(r'\bname="([^"]+)"', re.IGNORECASE)
_ATTR_SCALE_RE = re.compile(r'\bscale="([^"]+)"', re.IGNORECASE)


def _parse_value(raw: str, scale_str: str = "") -> int | None:
    try:
        val = float(raw.replace(",", "").replace(" ", "").strip())
        if scale_str:
            try:
                val *= 10 ** int(scale_str)
            except ValueError:
                pass
        return int(val)
    except (ValueError, TypeError):
        return None


def _extract_figures(html: str) -> dict:
    figures = {k: None for k in _TAGS}
    found = set()

    for m in _NONFRACTION_RE.finditer(html):
        attrs, raw_val = m.group(1), m.group(2).strip()
        nm = _ATTR_NAME_RE.search(attrs)
        if not nm:
            continue
        short_name = nm.group(1).split(":")[-1]
        sc = _ATTR_SCALE_RE.search(attrs)
        scale_str = sc.group(1) if sc else ""

        for field, candidates in _TAGS.items():
            if field in found:
                continue
            if any(short_name.lower() == c.lower() for c in candidates):
                val = _parse_value(raw_val, scale_str)
                if val is not None and val != 0:
                    found.add(field)
                    figures[field] = val
                    break

    return figures


def _altman_z_prime(f: dict) -> dict | None:
    """
    Compute Altman Z'-Score for private companies.
    Requires total_assets, working capital components, and at least one of
    profit/ebit and equity/liabilities.
    """
    ta = f.get("total_assets")
    if not ta or ta <= 0:
        return None

    ca = f.get("current_assets", 0) or 0
    cl = f.get("current_liabilities", 0) or 0
    na = f.get("net_assets")
    lt = f.get("long_term_liabilities", 0) or 0
    re_ = f.get("retained_earnings") or f.get("net_assets")  # fallback
    ebit = f.get("ebit") or f.get("profit_loss")
    sales = f.get("turnover")
    total_liabilities = cl + lt

    if na is None or ebit is None:
        return None

    wc = ca - cl  # working capital
    equity = na

    x1 = wc / ta
    x2 = (re_ or 0) / ta
    x3 = ebit / ta
    x4 = equity / total_liabilities if total_liabilities > 0 else 0
    x5 = sales / ta if sales else 0

    z = 0.717 * x1 + 0.847 * x2 + 3.107 * x3 + 0.420 * x4 + 0.998 * x5

    if z > 2.9:
        zone = "Safe"
    elif z >= 1.23:
        zone = "Grey"
    else:
        zone = "Distress"

    return {
        "z_score": round(z, 3),
        "zone": zone,
        "components": {
            "X1_working_capital": round(x1, 4),
            "X2_retained_earnings": round(x2, 4),
            "X3_ebit": round(x3, 4),
            "X4_equity_liabilities": round(x4, 4),
            "X5_sales": round(x5, 4),
        },
    }


def _compute_ratios(f: dict) -> dict:
    ratios = {}
    ca, cl = f.get("current_assets"), f.get("current_liabilities")
    if ca and cl and cl != 0:
        ratios["current_ratio"] = round(ca / cl, 2)

    na, ta = f.get("net_assets"), f.get("total_assets")
    if na is not None and ta and ta != 0:
        ratios["net_asset_ratio"] = round(na / ta * 100, 1)

    lt, eq = f.get("long_term_liabilities"), f.get("net_assets")
    if lt and eq and eq != 0:
        ratios["gearing_pct"] = round(lt / eq * 100, 1)

    return ratios


def _fetch_one_year(filing, auth) -> dict:
    """Fetch and parse a single accounts filing. Returns {} on failure."""
    doc_meta_url = filing["links"].get("document_metadata", "")
    if not doc_meta_url:
        return {}
    if not doc_meta_url.startswith("http"):
        doc_meta_url = f"{DOC_BASE}{doc_meta_url}"

    try:
        meta = requests.get(doc_meta_url, auth=auth, timeout=10).json()
        resources = meta.get("resources", {})
        has_ixbrl = any("xhtml" in m or "xbrl" in m.lower() for m in resources)
        if not has_ixbrl:
            return {}

        content_url = doc_meta_url.rstrip("/") + "/content"
        resp = requests.get(
            content_url, auth=auth,
            headers={"Accept": "application/xhtml+xml"}, timeout=20,
        )
        if resp.status_code != 200 or "pdf" in resp.headers.get("content-type", ""):
            return {}

        html = resp.text
        if not html or "<ix:nonFraction" not in html:
            return {}

        return _extract_figures(html)
    except Exception:
        return {}


def fetch_financial_ratios(company_number: str) -> dict:
    """
    Returns: period_end, figures, ratios, altman_z, trend (YoY comparison).
    Falls back to {} if accounts are PDF-only or unavailable.
    """
    if not API_KEY:
        return {}
    auth = (API_KEY, "")

    try:
        fh_resp = requests.get(
            f"{CH_BASE}/company/{company_number}/filing-history",
            params={"category": "accounts", "items_per_page": 15},
            auth=auth, timeout=10,
        )
        if fh_resp.status_code != 200:
            return {}

        filings = [
            f for f in fh_resp.json().get("items", [])
            if f.get("type") in _ACCOUNT_TYPES
            and f.get("links", {}).get("document_metadata")
        ]
        if not filings:
            return {}

        # Fetch two most recent years in parallel for trend analysis
        latest, prior = filings[0], filings[1] if len(filings) > 1 else None

        with ThreadPoolExecutor(max_workers=2) as pool:
            f_latest = pool.submit(_fetch_one_year, latest, auth)
            f_prior = pool.submit(_fetch_one_year, prior, auth) if prior else None

        current_figures = f_latest.result()
        prior_figures = f_prior.result() if f_prior else {}

        populated = {k: v for k, v in current_figures.items() if v is not None}
        if not populated:
            return {}

        ratios = _compute_ratios(current_figures)
        altman = _altman_z_prime(current_figures)

        # Year-over-year trend
        trend = {}
        if prior_figures:
            for metric in ("turnover", "profit_loss", "net_assets"):
                curr = current_figures.get(metric)
                prev = prior_figures.get(metric)
                if curr is not None and prev and prev != 0:
                    pct = round((curr - prev) / abs(prev) * 100, 1)
                    trend[metric] = {"current": curr, "prior": prev, "change_pct": pct}

        return {
            "period_end": latest.get("date", ""),
            "figures": populated,
            "ratios": ratios,
            "altman_z": altman,
            "trend": trend,
        }

    except Exception:
        return {}
