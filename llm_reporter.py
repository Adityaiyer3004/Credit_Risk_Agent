import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# ---------------------------------------------------------
# 🧩 Load environment variables
# ---------------------------------------------------------
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def generate_risk_report(company_name: str, profile: dict, risk: dict) -> str:
    """
    Generates a structured, professional credit-risk report using Groq's Llama 3.1 model.
    Now includes the Legal Health summary from Companies House.
    """
    if not GROQ_API_KEY:
        return "❌ Missing GROQ_API_KEY in .env file."

    # -----------------------------------------------------
    # 🧠 Initialize Groq LLM
    # -----------------------------------------------------
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="llama-3.1-8b-instant",  # low-latency inference
        temperature=0.3,
        max_tokens=400
    )

    # -----------------------------------------------------
    # 🏦 Structured prompt for LLM report
    # -----------------------------------------------------
    prompt = f"""
You are a senior credit-risk analyst for a regulated financial institution.
Write a factual, concise credit risk report following this exact 4-part structure.
Avoid any markdown, emojis, or speculation.

1. Executive Summary – short factual overview (2–3 sentences).
2. Key Strengths – up to 3 short bullet points.
3. Key Risks – up to 3 short bullet points.
4. Final Rating – restate the overall risk level and credit score with a brief rationale (1–2 sentences).

Company Details:
- Name: {company_name}
- Status: {profile.get('company_status', 'Unknown')}
- Incorporated: {profile.get('date_of_creation', 'Unknown')}
- Accounts Last Filed: {profile.get('accounts', {}).get('last_accounts', {}).get('made_up_to', 'N/A')}
- Risk Score: {risk.get('credit_score')}
- Risk Level: {risk.get('risk_level')}
- Legal Health: {risk.get('legal_summary', 'Not available')}
- Key Reasons: {', '.join(risk.get('reasons', []))}

Be analytical, professional, and concise. Do not repeat data points verbatim — interpret them.
Mention the Legal Health summary explicitly in the Executive Summary or Final Rating.
"""

    # -----------------------------------------------------
    # 🧾 Generate report text
    # -----------------------------------------------------
        # -----------------------------------------------------
    # 🧾 Generate report text
    # -----------------------------------------------------
    try:
        response = llm.invoke(prompt)
        return response.content.strip()

    except Exception as e:
        error_text = str(e)
        if "403" in error_text or "Access denied" in error_text:
            return (
                "⚠️ Groq API blocked by VPN or network restriction. "
                "Please disable VPN and retry."
            )
        elif "timed out" in error_text or "connection" in error_text.lower():
            return (
                "⚠️ Network issue: unable to reach Groq API. "
                "Check your internet or VPN settings."
            )
        else:
            return f"⚠️ Report generation failed: {error_text}"
