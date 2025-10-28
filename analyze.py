# routes/analyze.py
from fastapi import APIRouter, Query
from ingestors.comp_house_ingestor import fetch_company_data
from agent_core.orchestrator import generate_full_company_risk_report

router = APIRouter(prefix="/api", tags=["Analyze"])

@router.get("/analyze")
def analyze_company(company_number: str = Query(..., description="UK Company number")):
    """
    Analyze a UK company's credit risk using Companies House data.
    """
    try:
        # 1️⃣ Fetch company profile
        profile = fetch_company_data(company_number)
        if not profile or not isinstance(profile, dict):
            return {"error": f"No data found for company number {company_number}"}

        # 2️⃣ Generate risk report bundle
        result = generate_full_company_risk_report(profile)

        # 3️⃣ Return full structured response
        return {
            "company_number": company_number,
            "company_name": profile.get("company_name"),
            "profile": profile,
            "risk": result["risk"],
            "baseline_report": result["baseline_report"],
            "llm_report": result["llm_report"],
        }

    except Exception as e:
        return {"error": f"Internal error: {e}"}
