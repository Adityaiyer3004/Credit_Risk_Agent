import os
from pathlib import Path
from datetime import datetime, timezone
import yaml
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

_cfg = yaml.safe_load((Path(__file__).parent / "prompts.yaml").read_text())["report"]
_SYSTEM = _cfg["system"].strip()


def _extract_tokens(resp) -> dict:
    meta = getattr(resp, "usage_metadata", None) or {}
    fallback = getattr(resp, "response_metadata", {}).get("token_usage", {})
    inp = meta.get("input_tokens") or fallback.get("prompt_tokens", 0)
    out = meta.get("output_tokens") or fallback.get("completion_tokens", 0)
    tot = meta.get("total_tokens") or fallback.get("total_tokens", inp + out)
    return {
        "model": _cfg["model"],
        "input": inp,
        "output": out,
        "total": tot,
        "cost_usd": round(
            inp * _cfg["cost_per_1m_input_usd"] / 1_000_000
            + out * _cfg["cost_per_1m_output_usd"] / 1_000_000,
            6,
        ),
    }


def generate_risk_report(company_name: str, profile: dict, risk: dict) -> tuple[str, dict]:
    """Return (report_text, token_usage_dict)."""
    if not GROQ_API_KEY:
        return "GROQ_API_KEY not set in .env", {}

    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name=_cfg["model"],
        temperature=_cfg["temperature"],
        max_tokens=_cfg["max_tokens"],
    )

    # Enrich context
    creation = profile.get("date_of_creation", "")
    try:
        years = round((datetime.now() - datetime.fromisoformat(creation)).days / 365.25, 1)
        age_str = f"{years} years"
    except Exception:
        age_str = "unknown"

    sic_codes = profile.get("sic_codes", [])
    directors = profile.get("directors", [])
    accounts = profile.get("accounts", {})
    last_acc = accounts.get("last_accounts", {})
    acc_date = last_acc.get("made_up_to") or last_acc.get("period_end_on", "not filed")
    next_due = accounts.get("next_accounts", {}).get("due_on") or accounts.get("next_due", "unknown")
    notices = risk.get("legal_check", {}).get("notices", [])
    notice_titles = [n.get("title", "") for n in notices]
    reasons = risk.get("reasons", [])
    reasons_block = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(reasons)) if reasons else "  None identified"
    psc = profile.get("persons_with_significant_control", [])
    psc_names = ", ".join(p.get("name", "") for p in psc[:3]) if psc else "not available"

    # Charges summary
    charges_data = profile.get("charges", {})
    outstanding = charges_data.get("outstanding_count", 0)
    total_ch = charges_data.get("total_count", 0)
    charge_holders = []
    for c in charges_data.get("charges", [])[:5]:
        charge_holders.extend(c.get("persons_entitled", []))
    charge_holders = list(dict.fromkeys(charge_holders))[:4]
    if total_ch > 0:
        charges_summary = (
            f"{total_ch} total charges, {outstanding} outstanding. "
            f"Charge holders include: {', '.join(charge_holders) if charge_holders else 'undisclosed'}."
        )
    else:
        charges_summary = "No registered charges."

    # Insolvency summary
    insolvency_data = profile.get("insolvency", {})
    if insolvency_data.get("has_insolvency"):
        cases = insolvency_data.get("cases", [])
        types = [c.get("type", "") for c in cases]
        practitioners = []
        for c in cases:
            practitioners.extend(c.get("practitioners", []))
        insolvency_summary = (
            f"FORMAL INSOLVENCY ON RECORD. Proceedings: {', '.join(types)}. "
            f"Practitioners: {', '.join(practitioners[:3]) if practitioners else 'not listed'}."
        )
    else:
        insolvency_summary = "No formal insolvency proceedings on record."

    # Director network summary
    director_network = profile.get("director_network", [])
    if director_network:
        net_lines = []
        for d in director_network:
            net_lines.append(
                f"{d['name']}: {d['active_count']} active appointments, "
                f"{d['dissolved_count']} dissolved/insolvent company associations"
            )
        network_summary = "; ".join(net_lines)
    else:
        network_summary = "Director network data not available."

    # Filing history summary
    filing_history = profile.get("filing_history", {})
    recent_filings = filing_history.get("recent", [])
    total_filings = filing_history.get("total_count", 0)
    if recent_filings:
        paper_count = sum(1 for f in recent_filings if f.get("paper_filed"))
        filing_types = list({f.get("type", "") for f in recent_filings if f.get("type")})[:6]
        filing_summary = (
            f"Total filings on record: {total_filings}. "
            f"Most recent filing types: {', '.join(filing_types)}. "
            f"Paper filings in last 15: {paper_count}."
        )
    else:
        filing_summary = "No filing history available."

    # GLEIF LEI verification
    lei_data = profile.get("opencorporates", {})
    if lei_data and lei_data.get("lei"):
        oc_block = (
            f"LEI: {lei_data.get('lei')} | "
            f"Status: {lei_data.get('lei_status','unknown')} | "
            f"Entity status: {lei_data.get('entity_status','unknown')} | "
            f"Next renewal: {lei_data.get('next_renewal','unknown')}"
        )
    else:
        oc_block = "No LEI found in GLEIF register (may not be required for this company type)."

    # Financial ratios from filed accounts
    financials = profile.get("financials", {})
    fin_figures = financials.get("figures", {})
    fin_ratios = financials.get("ratios", {})
    fin_period = financials.get("period_end", "")
    if fin_figures:
        def _fmt(v):
            if abs(v) >= 1_000_000_000:
                return f"£{v/1_000_000_000:.2f}bn"
            if abs(v) >= 1_000_000:
                return f"£{v/1_000_000:.1f}m"
            if abs(v) >= 1_000:
                return f"£{v/1_000:.0f}k"
            return f"£{v:,}"
        lines = [f"Period ending: {fin_period}"]
        for key, label in [
            ("turnover", "Turnover/Revenue"),
            ("profit_loss", "Profit/Loss"),
            ("net_assets", "Net Assets"),
            ("current_assets", "Current Assets"),
            ("current_liabilities", "Current Liabilities"),
            ("cash", "Cash & Equivalents"),
        ]:
            if key in fin_figures:
                lines.append(f"  {label}: {_fmt(fin_figures[key])}")
        if fin_ratios.get("current_ratio"):
            lines.append(f"  Current Ratio: {fin_ratios['current_ratio']}")
        if fin_ratios.get("net_asset_ratio"):
            lines.append(f"  Net Asset Ratio: {fin_ratios['net_asset_ratio']}% of total assets")
        if fin_ratios.get("gearing_pct"):
            lines.append(f"  Gearing: {fin_ratios['gearing_pct']}%")

        altman = financials.get("altman_z")
        if altman:
            lines.append(
                f"  Altman Z'-Score: {altman['z_score']} ({altman['zone']} Zone)"
                f" — Safe >2.9 | Grey 1.23-2.9 | Distress <1.23"
            )

        trend = financials.get("trend", {})
        for metric, label in [("turnover", "Revenue"), ("profit_loss", "Profit/Loss"), ("net_assets", "Net Assets")]:
            t = trend.get(metric)
            if t:
                sign = "+" if t["change_pct"] > 0 else ""
                lines.append(f"  YoY {label}: {sign}{t['change_pct']}% ({_fmt(t['prior'])} → {_fmt(t['current'])})")

        financials_block = "\n".join(lines)
    else:
        financials_block = "  Financial statements not available in machine-readable format."

    # Winding-up / Gazette notices
    winding_up = profile.get("winding_up_notices", [])
    if winding_up:
        wu_lines = [f"  - [{n.get('date','')}] {n.get('notice_type','')}: {n.get('title','')}" for n in winding_up]
        winding_up_block = "\n".join(wu_lines)
    else:
        winding_up_block = "  None found in The Gazette."

    # Sector benchmark
    sector = risk.get("sector", {})
    sector_block = (
        f"{sector.get('label','Unknown')} — ~{sector.get('failure_rate','?')}% "
        f"5-year failure rate (ONS business demography data)"
    ) if sector else "Not determined."

    # Recent news summary
    news = profile.get("recent_news", [])
    if news:
        news_lines = []
        for item in news[:5]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")[:200]
            published = item.get("published", "")
            news_lines.append(f"  - [{published}] {title}: {snippet}")
        news_block = "\n".join(news_lines)
    else:
        news_block = "  No recent news found."

    user = f"""Write a credit risk report for this UK company using exactly the five sections below. No other sections.

1. EXECUTIVE SUMMARY
2. CREDIT SCORE INTERPRETATION
3. RISK FACTOR ANALYSIS
4. LEGAL AND FINANCIAL POSITION
5. CREDIT OPINION

Company data:
  Name: {company_name}
  Status: {profile.get("company_status", "unknown")}
  Incorporated: {profile.get("date_of_creation", "unknown")} ({age_str} ago)
  Company type: {profile.get("type", "unknown").upper()}
  SIC codes: {", ".join(str(s) for s in sic_codes) if sic_codes else "not specified"}
  Active directors: {len(directors)}
  Significant controllers: {psc_names}
  Last accounts filed to: {acc_date}
  Next accounts due: {next_due}
  Credit score: {risk.get("credit_score")}/100
  Risk level: {risk.get("risk_level")}
  Legal notices on file: {", ".join(notice_titles) if notice_titles else "none"}
  Legal summary: {risk.get("legal_summary", "no data")}
  Registered charges: {charges_summary}
  Insolvency proceedings: {insolvency_summary}
  Winding-up / Gazette notices:
{winding_up_block}
  GLEIF LEI verification: {oc_block}
  Filing compliance: {filing_summary}
  Director network: {network_summary}
  Sector benchmark: {sector_block}
  Score drivers:
{reasons_block}

Financial statements (from filed accounts):
{financials_block}

Recent news intelligence:
{news_block}

Section guidance:
1. EXECUTIVE SUMMARY — Two sentences. What the company does (infer from SIC), how long it has operated, and your headline credit view, factoring in the sector's historical failure rate.
2. CREDIT SCORE INTERPRETATION — Explain what a score of {risk.get("credit_score")}/100 means for a company of this age, type, and sector. Reference the sector benchmark failure rate. If an Altman Z'-Score is present, lead with it — it is more objective than the composite score.
3. RISK FACTOR ANALYSIS — Weave every score driver into analytical prose. Prioritise quantitative signals: Altman Z'-Score zone, year-on-year revenue and profit trends, current ratio, gearing. Contextualise director network quality and news signals within industry norms.
4. LEGAL AND FINANCIAL POSITION — Assess insolvency proceedings, Gazette winding-up notices, registered charges, and filing compliance. Evaluate balance sheet health from the financial statements — specifically liquidity, leverage, and net asset position. Note the GLEIF LEI status: a valid LEI is a positive compliance signal; a lapsed LEI is a red flag. Draw a conclusion about financial governance quality.
5. CREDIT OPINION — Two sentences maximum. State plainly whether you would recommend extending credit and under what conditions or limits. Be direct."""

    try:
        response = llm.invoke([SystemMessage(content=_SYSTEM), HumanMessage(content=user)])
        tokens = _extract_tokens(response)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        disclaimer = (
            "\n\n---\n"
            "DISCLAIMER: This report is generated from public register data and AI analysis. "
            "It is provided for informational purposes only and does not constitute financial advice, "
            "a regulated credit assessment, or a recommendation to extend or withhold credit. "
            f"Generated {ts}."
        )
        return response.content.strip() + disclaimer, tokens
    except Exception as e:
        err = str(e)
        if "403" in err or "Access denied" in err:
            return "Groq API blocked — disable VPN and retry.", {}
        if "timed out" in err.lower() or "connection" in err.lower():
            return "Network issue — unable to reach Groq API.", {}
        return f"Report generation failed: {err}", {}
