# agent_core/orchestrator.py
from agent_core.risk_engine import compute_risk_score
from agent_core.report_builder import build_credit_report
from agent_core.llm_reporter import generate_risk_report

def generate_full_company_risk_report(profile):
    # Compute risk
    risk = compute_risk_score(profile)

    # Build baseline (human) report
    baseline_report = build_credit_report(profile, risk)

    # Generate Groq AI report
    company_name = profile.get("company_name", "Unknown Company")
    llm_report = generate_risk_report(company_name, profile, risk)

    return {
        "profile": profile,
        "risk": risk,
        "baseline_report": baseline_report,
        "llm_report": llm_report
    }
