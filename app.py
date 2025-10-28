import streamlit as st
import requests

# -----------------------------
# 🌐 API Endpoint
# -----------------------------
API_URL = "http://127.0.0.1:8000/api/analyze"

# -----------------------------
# ⚙️ Page Setup
# -----------------------------
st.set_page_config(page_title="Credit Risk Assessment Agent", page_icon="💼", layout="wide")

# -----------------------------
# 💅 Clean Professional Theme
# -----------------------------
st.markdown("""
<style>
    /* Import professional font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global styles */
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    
    /* Main background */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Title styling */
    h1 {
        color: #ffffff;
        font-weight: 700;
        font-size: 2.5rem !important;
        margin-bottom: 0.5rem !important;
        letter-spacing: -0.02em;
    }
    
    /* Subtitle */
    .subtitle {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Card containers */
    .card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    /* Section headers */
    .section-header {
        color: #60a5fa !important;
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* Input styling */
    .stTextInput input {
        background-color: rgba(15, 23, 42, 0.8) !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        font-size: 1rem !important;
        padding: 0.75rem !important;
    }
    
    .stTextInput input:focus {
        border-color: #60a5fa !important;
        box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.2) !important;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        font-size: 1rem;
        width: 100%;
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 20px rgba(59, 130, 246, 0.3);
    }
    
    /* Metric styling */
    [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 1.5rem !important;
        font-weight: 600 !important;
    }
    
    [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-size: 0.875rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Force all text to be visible */
    p, div, span, li {
        color: #e2e8f0 !important;
    }
    
    /* Info boxes */
    .info-box {
        background: rgba(59, 130, 246, 0.1);
        border-left: 4px solid #3b82f6;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        color: #e0e7ff;
    }
    
    /* Warning/Alert styling */
    .stAlert {
        background: rgba(251, 191, 36, 0.1) !important;
        border-left: 4px solid #fbbf24 !important;
        color: #fef3c7 !important;
        border-radius: 8px !important;
    }
    
    /* Details box */
    .details-box {
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-left: 3px solid #60a5fa;
        border-radius: 8px;
        padding: 1.25rem;
        margin-top: 1rem;
        line-height: 1.8;
        color: #e2e8f0 !important;
    }
    
    .details-box * {
        color: #e2e8f0 !important;
    }
    
    .details-box strong {
        color: #60a5fa !important;
        font-weight: 600;
    }
    
    /* Report section */
    .report {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 8px;
        padding: 1.5rem;
        margin-top: 1rem;
        line-height: 1.8;
        color: #e2e8f0 !important;
    }
    
    .report * {
        color: #e2e8f0 !important;
    }
    
    .report h3, .report h4 {
        color: #60a5fa !important;
        margin-top: 1.5rem !important;
        margin-bottom: 0.75rem !important;
    }
    
    .report ul {
        margin-left: 1.5rem;
        color: #cbd5e1 !important;
    }
    
    .report li {
        color: #cbd5e1 !important;
    }
    
    .report strong {
        color: #93c5fd !important;
    }
    
    /* Risk badges */
    .risk-badge {
        display: inline-block;
        padding: 0.4rem 1rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.9rem;
        margin: 0.5rem 0;
    }
    
    .risk-low {
        background: rgba(34, 197, 94, 0.2);
        color: #86efac;
        border: 1px solid rgba(34, 197, 94, 0.4);
    }
    
    .risk-medium {
        background: rgba(251, 191, 36, 0.2);
        color: #fde047;
        border: 1px solid rgba(251, 191, 36, 0.4);
    }
    
    .risk-high {
        background: rgba(239, 68, 68, 0.2);
        color: #fca5a5;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    
    /* Caption text */
    .stCaptionContainer {
        color: #94a3b8 !important;
    }
    
    /* Divider */
    hr {
        border-color: rgba(148, 163, 184, 0.2);
        margin: 2rem 0;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-top-color: #60a5fa !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# 🧠 Helper Functions
# -----------------------------
def risk_badge(level: str):
    if not level:
        return '<span class="risk-badge">⚪ Unknown</span>'
    level_lower = level.lower()
    if "low" in level_lower:
        return '<span class="risk-badge risk-low">🟢 Low Risk</span>'
    elif "medium" in level_lower:
        return '<span class="risk-badge risk-medium">🟠 Medium Risk</span>'
    elif "high" in level_lower:
        return '<span class="risk-badge risk-high">🔴 High Risk</span>'
    return f'<span class="risk-badge">{level.title()}</span>'

# -----------------------------
# 🏦 Header
# -----------------------------
st.markdown("<h1>💼 Credit Risk Assessment Agent</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>Analyze UK company credit risk using Companies House data and AI-powered insights</p>", unsafe_allow_html=True)

# -----------------------------
# 🔍 Company Lookup Section
# -----------------------------
st.markdown("<div class='section-header'>🔍 Company Lookup</div>", unsafe_allow_html=True)

col1, col2 = st.columns([3, 1])
with col1:
    company_number = st.text_input(
        "Company Number",
        placeholder="e.g., 08804411 (Revolut Ltd)",
        label_visibility="collapsed"
    )
with col2:
    analyze_btn = st.button("🔎 Analyze", use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------
# 📊 Analysis Logic
# -----------------------------
if analyze_btn:
    if not company_number:
        st.warning("⚠️ Please enter a valid company number.")
    else:
        with st.spinner("🔄 Retrieving company data and analyzing risk..."):
            try:
                response = requests.get(API_URL, params={"company_number": company_number}, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                # Store in session state
                st.session_state['result'] = result
                st.session_state['company_number'] = company_number
                
            except requests.exceptions.RequestException as e:
                st.error(f"❌ API request failed: {str(e)}")
                st.stop()
            except Exception as e:
                st.error(f"❌ Unexpected error: {str(e)}")
                st.stop()

# -----------------------------
# 📊 Display Results
# -----------------------------
if 'result' in st.session_state:
    result = st.session_state['result']
    profile = result.get("profile", {})
    risk = result.get("risk", {})
    llm = result.get("llm_report", "")

    # 🏢 Company Profile Card
    st.markdown("<div class='section-header'>🏢 Company Profile</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Company Name", profile.get("company_name", "N/A"))
    with col2:
        st.metric("Status", profile.get("company_status", "Active").upper())
    with col3:
        st.metric("Incorporated", profile.get("date_of_creation", "N/A"))

    # Address
    addr = profile.get("registered_office_address", {})
    address_parts = [
        addr.get("address_line_1"),
        addr.get("locality"),
        addr.get("country"),
        addr.get("postal_code")
    ]
    address = ", ".join(filter(None, address_parts))
    if address:
        st.caption(f"📍 {address}")

    # Company Details Box
    accounts = profile.get("accounts", {})
    conf_statement = profile.get("confirmation_statement", {})
    
    st.markdown(f"""
    <div class='details-box'>
        <strong>Company Number:</strong> {profile.get("company_number", "N/A")}<br>
        <strong>Company Type:</strong> {profile.get("type", "N/A")}<br>
        <strong>Accounting Reference Date:</strong> {accounts.get("accounting_reference_date", {}).get("month", "N/A")}/{accounts.get("accounting_reference_date", {}).get("day", "N/A")}<br>
        <strong>Next Accounts Due:</strong> {accounts.get("next_due", "N/A")}<br>
        <strong>Next Confirmation Statement:</strong> {conf_statement.get("next_due", "N/A")}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # 📈 Risk Summary Card
    st.markdown("<div class='section-header'>⚠️ Risk Assessment</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Credit Score", risk.get("credit_score", "N/A"))
    with col2:
        st.markdown(f"**Risk Level:** {risk_badge(risk.get('risk_level', 'Unknown'))}", unsafe_allow_html=True)

    # Risk Reasons
    if reasons := risk.get("reasons", []):
        st.markdown("**Key Risk Factors:**")
        reasons_html = "<ul style='margin-left: 1.5rem; color: #cbd5e1;'>"
        for reason in reasons:
            reasons_html += f"<li>{reason}</li>"
        reasons_html += "</ul>"
        st.markdown(reasons_html, unsafe_allow_html=True)

    # Legal Summary
    if legal := risk.get("legal_summary"):
        st.markdown(f"""
        <div class='info-box'>
            <strong>⚖️ Legal Health:</strong> {legal}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # 🧠 AI-Generated Report Card
    if llm:
        st.markdown("<div class='section-header'>🤖 AI-Generated Credit Risk Report</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='report'>{llm}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #64748b; font-size: 0.875rem;'>Powered by Companies House API • Built with Streamlit</p>", unsafe_allow_html=True)