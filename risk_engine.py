from datetime import datetime
from gazette_scraper import scrape_gazette_events
from sector_benchmarks import get_sector_risk


def compute_risk_score(profile: dict):
    score = 70
    reasons = []

    # ── Company status ────────────────────────────────────────────────────────
    status = (profile.get("company_status") or "").lower()
    if status != "active":
        score -= 40
        reasons.append(f"Company status is '{status or 'unknown'}'")

    # ── Company age ───────────────────────────────────────────────────────────
    creation = profile.get("date_of_creation")
    age_years = None
    if creation:
        try:
            age_years = (datetime.now() - datetime.fromisoformat(creation)).days / 365.25
            if age_years < 2:
                score -= 20
                reasons.append("Company less than 2 years old — limited track record")
            elif age_years < 5:
                score -= 10
                reasons.append("Company under 5 years old")
        except Exception:
            pass

    # ── Accounts recency ──────────────────────────────────────────────────────
    last_accounts = profile.get("accounts_summary", {}) or profile.get("accounts", {})
    last_accounts = last_accounts.get("last_accounts", {})
    made_up_to = None
    if isinstance(last_accounts, dict):
        made_up_to = last_accounts.get("made_up_to") or last_accounts.get("period_end_on")

    if made_up_to:
        try:
            diff = (datetime.now() - datetime.fromisoformat(made_up_to)).days / 365.25
            if diff > 2:
                score -= 20
                reasons.append("Last accounts older than 2 years — possible compliance failure")
        except Exception:
            pass
    else:
        score -= 15
        reasons.append("No accounts filed on record")

    # ── Financial ratios + Altman Z'-Score + YoY trend ───────────────────────
    financials = profile.get("financials", {})
    ratios = financials.get("ratios", {})
    altman = financials.get("altman_z")
    trend = financials.get("trend", {})

    # Altman Z'-Score (primary financial signal when available)
    if altman:
        z = altman["z_score"]
        zone = altman["zone"]
        if zone == "Distress":
            score -= 25
            reasons.append(f"Altman Z'-Score {z} — Distress Zone (< 1.23): high probability of financial failure")
        elif zone == "Grey":
            score -= 10
            reasons.append(f"Altman Z'-Score {z} — Grey Zone (1.23–2.9): elevated financial stress")
        else:
            score += 8
            reasons.append(f"Altman Z'-Score {z} — Safe Zone (> 2.9): financially healthy balance sheet")

    # Current ratio (liquidity — still useful even without full Z-Score)
    elif ratios.get("current_ratio") is not None:
        cr = ratios["current_ratio"]
        if cr < 0.8:
            score -= 15
            reasons.append(f"Current ratio {cr} — significant short-term liquidity stress")
        elif cr < 1.0:
            score -= 8
            reasons.append(f"Current ratio {cr} — current liabilities exceed current assets")
        elif cr >= 2.0:
            score += 5
            reasons.append(f"Strong liquidity: current ratio {cr}")

    # Gearing (leverage signal)
    if ratios.get("gearing_pct") is not None:
        gearing = ratios["gearing_pct"]
        if gearing > 200:
            score -= 10
            reasons.append(f"Very high gearing ({gearing}%) — heavily leveraged balance sheet")
        elif gearing > 100:
            score -= 5
            reasons.append(f"Elevated gearing ({gearing}%)")

    # Year-over-year trend signals
    turnover_trend = trend.get("turnover", {})
    profit_trend = trend.get("profit_loss", {})
    if turnover_trend.get("change_pct") is not None:
        chg = turnover_trend["change_pct"]
        if chg <= -20:
            score -= 12
            reasons.append(f"Revenue declined {abs(chg):.1f}% year-on-year — significant deterioration")
        elif chg <= -10:
            score -= 6
            reasons.append(f"Revenue declined {abs(chg):.1f}% year-on-year")
        elif chg >= 20:
            score += 4
            reasons.append(f"Strong revenue growth: +{chg:.1f}% year-on-year")
    if profit_trend.get("change_pct") is not None:
        pchg = profit_trend["change_pct"]
        prior = profit_trend.get("prior", 0)
        curr = profit_trend.get("current", 0)
        if prior > 0 and curr < 0:
            score -= 10
            reasons.append("Profit turned to loss year-on-year — material deterioration")
        elif pchg <= -30 and prior > 0:
            score -= 6
            reasons.append(f"Profit declined {abs(pchg):.1f}% year-on-year")

    # ── Filing history: lateness and paper filings ────────────────────────────
    filing_history = profile.get("filing_history", {})
    recent_filings = filing_history.get("recent", [])
    if recent_filings:
        paper_count = sum(1 for f in recent_filings if f.get("paper_filed"))
        late_count = 0
        for f in recent_filings:
            filed = f.get("date")
            due = f.get("action_date")
            if filed and due:
                try:
                    gap = (datetime.fromisoformat(filed) - datetime.fromisoformat(due)).days
                    if gap > 30:
                        late_count += 1
                except Exception:
                    pass
        if late_count >= 3:
            score -= 10
            reasons.append(f"{late_count} filings submitted significantly late")
        elif late_count >= 1:
            score -= 4
            reasons.append(f"{late_count} filing(s) submitted late")
        if paper_count >= 5:
            score -= 4
            reasons.append(f"{paper_count} paper filings detected (digital governance signal)")
        elif paper_count >= 3:
            score -= 2
            reasons.append(f"{paper_count} paper filings detected (digital governance signal)")

    # ── Directors ─────────────────────────────────────────────────────────────
    directors = profile.get("directors", []) or profile.get("officers", []) or []
    if isinstance(directors, dict) and "items" in directors:
        directors = directors["items"]

    if len(directors) == 0:
        score -= 20
        reasons.append("No active directors listed")
    elif len(directors) > 10:
        score -= 10
        reasons.append("High director count / possible governance complexity")

    # ── Charges (Companies House) ─────────────────────────────────────────────
    charges_data = profile.get("charges", {})
    outstanding_charges = charges_data.get("outstanding_count", 0)
    if outstanding_charges >= 5:
        score -= 15
        reasons.append(f"High outstanding charge count ({outstanding_charges}) — significant secured debt burden")
    elif outstanding_charges >= 2:
        score -= 8
        reasons.append(f"{outstanding_charges} outstanding registered charges")
    elif outstanding_charges == 1:
        score -= 3
        reasons.append("1 outstanding registered charge")

    # ── Insolvency (Companies House) ──────────────────────────────────────────
    insolvency_data = profile.get("insolvency", {})
    if insolvency_data.get("has_insolvency"):
        score -= 30
        cases = insolvency_data.get("cases", [])
        types = list({c.get("type", "unknown") for c in cases})
        reasons.append(f"Formal insolvency proceedings on record: {', '.join(types)}")

    # ── Winding-up petitions (Gazette) ────────────────────────────────────────
    winding_up = profile.get("winding_up_notices", [])
    if winding_up:
        types_seen = list({n.get("notice_type", "notice") for n in winding_up})
        count = len(winding_up)
        if count >= 2:
            score -= 20
            reasons.append(f"{count} winding-up / insolvency notices in The Gazette — serious distress signal")
        else:
            score -= 12
            reasons.append(f"Winding-up / insolvency notice found in The Gazette: {types_seen[0]}")

    # ── Director network risk ─────────────────────────────────────────────────
    # Weight by dissolved/total ratio — a director with 9 dissolved out of 27
    # active posts has a lower concern rate than one with 3 dissolved and 1 active.
    director_network = profile.get("director_network", [])
    high_ratio_dirs = []
    for d in director_network:
        dissolved = d.get("dissolved_count", 0)
        active = d.get("active_count", 0)
        total = dissolved + active
        ratio = dissolved / total if total > 0 else 0
        if dissolved >= 3 and ratio >= 0.25:
            high_ratio_dirs.append((d, dissolved, ratio))
        elif dissolved >= 5:
            high_ratio_dirs.append((d, dissolved, ratio))

    if len(high_ratio_dirs) >= 2:
        score -= 12
        names = ", ".join(d["name"].split(",")[0] for d, _, _ in high_ratio_dirs[:2])
        reasons.append(f"Multiple directors with high dissolved-company ratio: {names}")
    elif high_ratio_dirs:
        score -= 5
        d, dissolved, ratio = high_ratio_dirs[0]
        reasons.append(f"Director {d['name'].split(',')[0]} has {dissolved} dissolved company associations ({ratio:.0%} of appointments)")

    # Serial insolvency flag — only if the dissolution rate is genuinely alarming
    serial_risk = [d for d in director_network if d.get("dissolved_count", 0) >= 4
                   and d.get("dissolved_count", 0) / max(d.get("active_count", 0) + d.get("dissolved_count", 0), 1) >= 0.3]
    if serial_risk:
        names = ", ".join(d["name"].split(",")[0] for d in serial_risk[:2])
        reasons.append(f"Serial insolvency signal: {names} — 30%+ of career appointments ended in dissolution")

    # ── Legal enrichment (Gazette / CH status) ────────────────────────────────
    company_number = profile.get("company_number", "")
    legal_data = scrape_gazette_events(company_number)

    legal_summary = []
    if insolvency_data.get("has_insolvency"):
        legal_summary.append("formal insolvency proceedings on record")
    elif any("Insolvency" in n["title"] for n in legal_data["notices"]):
        score -= 10
        legal_summary.append("insolvency notices in Gazette")
        reasons.append("Insolvency notices found in official Gazette")

    if winding_up:
        legal_summary.append(f"{len(winding_up)} winding-up / insolvency notice(s) in The Gazette")

    if outstanding_charges > 0:
        legal_summary.append(f"{outstanding_charges} outstanding charge(s) at Companies House")
    elif any("Charges" in n["title"] for n in legal_data["notices"]):
        legal_summary.append("charge notices in Gazette")

    if "dissolved" in legal_data["note"].lower() or "liquidation" in legal_data["note"].lower():
        legal_summary.append("company dissolved or in liquidation (archived)")
        reasons.append("Company dissolved or in liquidation")

    if not legal_summary:
        legal_summary.append("no insolvency, winding-up, or charge records found")

    legal_summary_text = "Legal Health: " + ", ".join(legal_summary).capitalize() + "."

    # ── Ownership structure complexity (PSC analysis) ─────────────────────────
    psc_list = profile.get("persons_with_significant_control", [])
    offshore_psc = []
    for psc in psc_list:
        country = (psc.get("country_of_residence") or psc.get("jurisdiction") or "").lower()
        uk_terms = ("united kingdom", "england", "wales", "scotland", "northern ireland", "gb")
        if country and not any(t in country for t in uk_terms):
            offshore_psc.append(country)
    if len(offshore_psc) >= 2:
        score -= 5
        reasons.append(f"Multiple non-UK controllers ({len(offshore_psc)}) — complex cross-border ownership structure")
    elif offshore_psc:
        pass  # Single offshore PSC is normal for subsidiaries — not penalised

    # ── GLEIF LEI verification ────────────────────────────────────────────────
    lei_data = profile.get("opencorporates", {})  # field name kept for compat
    if lei_data:
        lei_status = (lei_data.get("lei_status") or "").upper()
        if lei_status == "LAPSED":
            score -= 12
            reasons.append(f"LEI lapsed (GLEIF) — company has not renewed its Legal Entity Identifier, a compliance red flag")
        elif lei_status == "RETIRED":
            score -= 15
            reasons.append("LEI retired (GLEIF) — Legal Entity Identifier retired, entity may no longer be active")
        elif lei_status == "ISSUED":
            score += 4
            reasons.append(f"Valid LEI registered (GLEIF: {lei_data.get('lei','')})")
        elif lei_status == "PENDING_TRANSFER":
            reasons.append("LEI pending transfer (GLEIF) — possible ownership change in progress")

    # ── News sentiment signal ─────────────────────────────────────────────────
    # Terms grouped by event type — co-occurring terms in the same group count
    # as ONE event, preventing a single AML fine generating 3 separate signals.
    news = profile.get("recent_news", [])
    if news:
        term_groups = [
            ("regulatory_action", ["fined", "penalty", "sanction", "censure", "enforcement"]),
            ("legal_action",      ["lawsuit", "sued", "litigation", "court", "claim"]),
            ("fraud",             ["fraud", "fraudulent", "scam", "deception"]),
            ("insolvency",        ["insolvency", "bankrupt", "administration", "liquidation", "collapse"]),
            ("investigation",     ["investigation", "probe", "inquiry", "scrutiny"]),
            ("breach",            ["breach", "violation", "infringement", "non-compliance"]),
            ("scandal",           ["scandal", "misconduct", "wrongdoing"]),
        ]
        triggered_groups = set()
        all_hit_terms = []
        for item in news:
            text = (item.get("title", "") + " " + item.get("snippet", "")).lower()
            for group_name, terms in term_groups:
                if any(t in text for t in terms):
                    triggered_groups.add(group_name)
                    hit = next(t for t in terms if t in text)
                    if hit not in all_hit_terms:
                        all_hit_terms.append(hit)

        n = len(triggered_groups)
        if n >= 3:
            score -= 12
            reasons.append(f"Multiple distinct negative news event types: {', '.join(all_hit_terms[:4])}")
        elif n == 2:
            score -= 7
            reasons.append(f"Negative news signals detected: {', '.join(all_hit_terms[:3])}")
        elif n == 1:
            score -= 4
            reasons.append(f"Negative news signal: {', '.join(all_hit_terms[:2])}")

    # ── Sector benchmark ──────────────────────────────────────────────────────
    sic_codes = profile.get("sic_codes", []) or []
    sector = get_sector_risk(sic_codes)
    adj = sector["score_adjustment"]
    score += adj
    if adj <= -7:
        reasons.append(
            f"High-risk sector: {sector['label']} "
            f"(~{sector['failure_rate']}% 5-year failure rate, ONS data)"
        )
    elif adj >= 3:
        reasons.append(
            f"Lower-risk sector: {sector['label']} "
            f"(~{sector['failure_rate']}% 5-year failure rate)"
        )

    # ── Clamp & classify ──────────────────────────────────────────────────────
    score = max(1, min(100, score))
    risk_level = "Low Risk" if score >= 68 else "Medium Risk" if score >= 45 else "High Risk"

    return {
        "credit_score": int(score),
        "risk_level": risk_level,
        "reasons": reasons,
        "legal_check": legal_data,
        "legal_summary": legal_summary_text,
        "sector": sector,
    }
