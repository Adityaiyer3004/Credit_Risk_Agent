from risk_engine import compute_risk_score
from report_builder import build_credit_report
from llm_reporter import generate_risk_report
from guardrail_evaluator import evaluate_report
from news_searcher import search_company_news
from gazette_winding_up import search_winding_up_petitions
from accounts_analyzer import fetch_financial_ratios
from opencorporates_client import fetch_opencorporates
from concurrent.futures import ThreadPoolExecutor


def generate_full_company_risk_report(profile):
    company_name = profile.get("company_name", "Unknown Company")
    company_number = profile.get("company_number", "")

    # Phase 1: parallel external data fetches
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_news       = pool.submit(search_company_news, company_name)
        f_gazette    = pool.submit(search_winding_up_petitions, company_name, company_number)
        f_financials = pool.submit(fetch_financial_ratios, company_number)
        f_oc         = pool.submit(fetch_opencorporates, company_number)

    profile["recent_news"]        = f_news.result()
    profile["winding_up_notices"] = f_gazette.result()
    profile["financials"]         = f_financials.result()
    profile["opencorporates"]     = f_oc.result()

    risk            = compute_risk_score(profile)
    baseline_report = build_credit_report(profile, risk)

    # Phase 2: generate report, then guardrail-eval it (sequential — eval needs report text)
    llm_report = generate_risk_report(company_name, profile, risk)
    guardrail  = evaluate_report(company_name, profile, risk, llm_report)

    return {
        "profile":          profile,
        "risk":             risk,
        "baseline_report":  baseline_report,
        "llm_report":       llm_report,
        "guardrail":        guardrail,
    }
