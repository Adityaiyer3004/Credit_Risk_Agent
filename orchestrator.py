from risk_engine import compute_risk_score
from report_builder import build_credit_report
from llm_reporter import generate_risk_report
from guardrail_evaluator import evaluate_report
from news_searcher import search_company_news
from gazette_winding_up import search_winding_up_petitions
from accounts_analyzer import fetch_financial_ratios
from opencorporates_client import fetch_opencorporates
from mlflow_tracker import log_analysis_run
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

    # Phase 2: generate report then guardrail-eval it (sequential — eval needs report text)
    llm_report, report_tokens = generate_risk_report(company_name, profile, risk)
    guardrail = evaluate_report(company_name, profile, risk, llm_report)
    guardrail_tokens = guardrail.pop("tokens", {})

    llm_usage = {
        "report":          report_tokens,
        "guardrail":       guardrail_tokens,
        "total_tokens":    report_tokens.get("total", 0) + guardrail_tokens.get("total", 0),
        "total_cost_usd":  round(
            report_tokens.get("cost_usd", 0) + guardrail_tokens.get("cost_usd", 0), 6
        ),
        "prompt_version":  _prompt_version(),
    }

    result = {
        "profile":         profile,
        "risk":            risk,
        "baseline_report": baseline_report,
        "llm_report":      llm_report,
        "guardrail":       guardrail,
        "llm_usage":       llm_usage,
    }

    log_analysis_run(
        company_name=company_name,
        company_number=company_number,
        risk=risk,
        guardrail=guardrail,
        llm_usage=llm_usage,
        cached=False,
    )

    return result


def _prompt_version() -> str:
    try:
        from pathlib import Path
        import yaml
        return yaml.safe_load((Path(__file__).parent / "prompts.yaml").read_text())["version"]
    except Exception:
        return "unknown"
