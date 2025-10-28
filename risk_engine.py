from datetime import datetime
from ingestors.gazette_scraper import scrape_gazette_events  # ✅ Companies House version


def compute_risk_score(profile: dict):
    """
    Compute a credit risk score (1–100) using Companies House data,
    enriched with legal (insolvency / charges) checks.
    """

    score = 50
    reasons = []

    # -----------------------------------------------------
    # 🔍 Basic company status
    # -----------------------------------------------------
    status = (profile.get("company_status") or "").lower()
    if status != "active":
        score -= 40
        reasons.append(f"Company status is '{status or 'unknown'}'")

    # -----------------------------------------------------
    # 📅 Company age
    # -----------------------------------------------------
    creation = profile.get("date_of_creation")
    if creation:
        try:
            yrs = (datetime.now() - datetime.fromisoformat(creation)).days / 365.25
            if yrs < 2:
                score -= 20
                reasons.append("Company less than 2 years old")
            elif yrs < 5:
                score -= 10
                reasons.append("Company under 5 years old")
        except Exception:
            pass

    # -----------------------------------------------------
    # 📊 Accounts recency
    # -----------------------------------------------------
    last_accounts = profile.get("accounts_summary", {}) or profile.get("accounts", {})
    last_accounts = last_accounts.get("last_accounts", last_accounts.get("last_accounts", {}))
    made_up_to = None

    if isinstance(last_accounts, dict):
        made_up_to = last_accounts.get("made_up_to") or last_accounts.get("period_end_on")

    if made_up_to:
        try:
            diff = (datetime.now() - datetime.fromisoformat(made_up_to)).days / 365.25
            if diff > 2:
                score -= 20
                reasons.append("Last accounts older than 2 years")
        except Exception:
            pass
    else:
        score -= 15
        reasons.append("No accounts filed")

    # -----------------------------------------------------
    # 👔 Directors
    # -----------------------------------------------------
    directors = profile.get("directors", []) or profile.get("officers", []) or []
    if isinstance(directors, dict) and "items" in directors:
        directors = directors["items"]

    if len(directors) == 0:
        score -= 20
        reasons.append("No active directors listed")
    elif len(directors) > 10:
        score -= 10
        reasons.append("High director turnover / many officers")

    # -----------------------------------------------------
    # ⚖️ Legal enrichment (Companies House)
    # -----------------------------------------------------
    company_number = profile.get("company_number", "")
    legal_data = scrape_gazette_events(company_number)

    legal_summary = []
    if any("Insolvency" in n["title"] for n in legal_data["notices"]):
        score -= 25
        legal_summary.append("insolvency record found")
        reasons.append("Company has insolvency record")

    if any("Charges" in n["title"] for n in legal_data["notices"]):
        score -= 10
        legal_summary.append("registered charges present")
        reasons.append("Registered charges found")

    if "dissolved" in legal_data["note"].lower() or "liquidation" in legal_data["note"].lower():
        legal_summary.append("company dissolved or in liquidation (archived data)")
        reasons.append("Company dissolved or in liquidation (historical data archived)")

    if not legal_summary:
        legal_summary.append("no insolvency or charge records found")

    legal_summary_text = "Legal Health: " + ", ".join(legal_summary).capitalize() + "."

    # -----------------------------------------------------
    # 📎 SIC / sector heuristics
    # -----------------------------------------------------
    sic_codes = profile.get("sic_codes", []) or []
    risky_sic_starts = ("64", "65", "66")
    if any(str(code).startswith(r) for code in sic_codes for r in risky_sic_starts):
        score -= 2
        reasons.append("Sector risk adjustment (financial/insurance SIC)")

    # -----------------------------------------------------
    # 🔒 Clamp & classify
    # -----------------------------------------------------
    score = max(1, min(100, score))

    if score >= 80:
        risk_level = "Low Risk"
    elif score >= 50:
        risk_level = "Medium Risk"
    else:
        risk_level = "High Risk"

    # -----------------------------------------------------
    # 🧾 Final structured output
    # -----------------------------------------------------
    return {
        "credit_score": int(score),
        "risk_level": risk_level,
        "reasons": reasons,
        "legal_check": legal_data,
        "legal_summary": legal_summary_text
    }
