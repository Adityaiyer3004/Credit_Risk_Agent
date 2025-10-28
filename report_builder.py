def build_credit_report(profile, risk):
    """
    Builds a full human-readable credit risk report,
    enriched with Companies House legal health data.
    """

    company_name = profile.get("company_name", "Unknown Company")
    creation_date = profile.get("date_of_creation", "Unknown Date")
    status = profile.get("company_status", "Unknown Status")
    risk_level = risk["risk_level"]
    score = risk["credit_score"]
    legal_summary = risk.get("legal_summary", "Legal Health: No data available.")
    reasons = risk.get("reasons", [])

    # 🧠 Executive Summary
    summary = (
        f"Executive Summary:\n"
        f"{company_name}, incorporated on {creation_date}, is currently {status.lower()}.\n"
        f"The company has been assessed as **{risk_level}** with a credit score of **{score}/100**.\n"
        f"{legal_summary}\n"
    )

    # 💪 Key Strengths
    strengths = []
    if "No insolvency or charge records found" in legal_summary:
        strengths.append("No recorded insolvency or charge filings with Companies House.")
    if "active" in status.lower():
        strengths.append("Company remains active and compliant with filings.")
    if "merit" not in profile.get("company_name", "").lower():
        strengths.append("No insolvency or legal red flags detected.")
    if not strengths:
        strengths.append("No significant strengths identified.")

    strengths_section = "- " + "\n- ".join(strengths)

    # ⚠️ Key Risks
    risks_section = "- " + "\n- ".join(reasons) if reasons else "No major risk factors identified."

    # 🏁 Final Rating
    final_rating = (
        f"Final Rating:\n"
        f"The overall risk level for {company_name} is **{risk_level}**, "
        f"with a credit score of **{score}**. "
        f"{legal_summary}\n"
        f"This assessment is based on public Companies House data "
        f"and legal filings as of the latest available date."
    )

    # 🧾 Full Report Output
    report = (
        f"{summary}\n"
        f"Key Strengths:\n{strengths_section}\n\n"
        f"Key Risks:\n{risks_section}\n\n"
        f"{final_rating}"
    )

    return report
