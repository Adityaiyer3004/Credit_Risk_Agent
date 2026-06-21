import streamlit as st
import streamlit.components.v1 as components
import requests

API_URL = "http://127.0.0.1:8000/api/analyze"

st.set_page_config(page_title="Credit Risk Intelligence", page_icon="💼", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

* { font-family: 'Inter', sans-serif !important; }

/* Moving gradient background */
.stApp {
    background: linear-gradient(-45deg, #0a0f1e, #0d1b3e, #130a2e, #0a1628);
    background-size: 400% 400%;
    animation: gradientShift 14s ease infinite;
    min-height: 100vh;
}
@keyframes gradientShift {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* Card slide-up */
@keyframes slideUp {
    from { opacity: 0; transform: translateY(28px); }
    to   { opacity: 1; transform: translateY(0); }
}
/* Active-status pulsing ring */
@keyframes statusPulse {
    0%, 100% { box-shadow: 0 0 0 0   rgba(34,197,94,0.5); }
    50%       { box-shadow: 0 0 0 8px rgba(34,197,94,0);   }
}
/* Glowing border sweep */
@keyframes borderGlow {
    0%,100% { border-color: rgba(96,165,250,0.08); }
    50%      { border-color: rgba(96,165,250,0.28); }
}

#MainMenu, footer, header { visibility: hidden; }

/* ── Hero ─────────────────────────── */
.hero {
    text-align: center;
    padding: 3.5rem 0 2.25rem;
    animation: slideUp 0.7s ease;
}
.hero-title {
    font-size: 2.75rem; font-weight: 800;
    background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 55%, #f472b6 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.035em; line-height: 1.1; margin-bottom: 0.55rem;
}
.hero-sub { color: #475569; font-size: 0.95rem; letter-spacing: 0.01em; }

/* ── Cards ────────────────────────── */
.card {
    background: rgba(13,20,40,0.78);
    border: 1px solid rgba(148,163,184,0.07);
    border-radius: 18px; padding: 1.7rem;
    margin-bottom: 1.2rem;
    backdrop-filter: blur(28px);
    animation: slideUp 0.55s ease both, borderGlow 4s ease infinite;
    transition: box-shadow 0.3s;
}
.card:hover { box-shadow: 0 16px 48px rgba(96,165,250,0.07); }

/* ── Labels ───────────────────────── */
.section-label {
    font-size: 0.66rem; font-weight: 700;
    letter-spacing: 0.14em; text-transform: uppercase;
    color: #334155; margin-bottom: 1.1rem;
}

/* ── Company header ───────────────── */
.co-name {
    font-size: 2rem; font-weight: 800;
    color: #f8fafc; letter-spacing: -0.025em; line-height: 1.1;
}
.status-active {
    display: inline-flex; align-items: center; gap: 0.35rem;
    background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.25);
    color: #86efac; padding: 0.28rem 0.85rem; border-radius: 20px;
    font-size: 0.73rem; font-weight: 700; letter-spacing: 0.05em;
    animation: statusPulse 2.4s infinite;
}
.status-other {
    display: inline-flex; align-items: center; gap: 0.35rem;
    background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.25);
    color: #fca5a5; padding: 0.28rem 0.85rem; border-radius: 20px;
    font-size: 0.73rem; font-weight: 700; letter-spacing: 0.05em;
}
.address-line { color: #475569; font-size: 0.84rem; margin-top: 0.55rem; }

/* ── Meta grid ────────────────────── */
.meta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(145px,1fr));
    gap: 0.7rem; margin-top: 1.2rem;
}
.meta-item {
    background: rgba(30,41,59,0.45);
    border: 1px solid rgba(148,163,184,0.05);
    border-radius: 10px; padding: 0.8rem 0.95rem;
}
.meta-lbl {
    font-size: 0.65rem; font-weight: 600; color: #334155;
    text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.28rem;
}
.meta-val { font-size: 0.88rem; font-weight: 600; color: #e2e8f0; }

/* ── Reason tags ──────────────────── */
.reason-tag {
    display: inline-block;
    background: rgba(30,41,59,0.7);
    border: 1px solid rgba(148,163,184,0.08);
    color: #94a3b8; padding: 0.28rem 0.7rem;
    border-radius: 6px; font-size: 0.78rem; margin: 0.18rem;
}

/* ── Legal box ────────────────────── */
.legal-box {
    background: rgba(59,130,246,0.05);
    border: 1px solid rgba(59,130,246,0.12);
    border-left: 3px solid #3b82f6;
    border-radius: 10px; padding: 0.85rem 1.1rem;
    color: #93c5fd; font-size: 0.86rem;
    margin-top: 0.9rem; line-height: 1.65;
}

/* ── PSC rows ─────────────────────── */
.psc-row {
    display: flex; justify-content: space-between; align-items: center;
    background: rgba(30,41,59,0.4);
    border: 1px solid rgba(148,163,184,0.05);
    border-radius: 10px; padding: 0.85rem 1.05rem; margin-bottom: 0.55rem;
    transition: border-color 0.25s;
}
.psc-row:hover { border-color: rgba(167,139,250,0.15); }
.psc-name { font-weight: 600; color: #e2e8f0; font-size: 0.88rem; }
.psc-detail { font-size: 0.74rem; color: #475569; margin-top: 0.12rem; }
.psc-badge {
    font-size: 0.68rem;
    background: rgba(167,139,250,0.1); border: 1px solid rgba(167,139,250,0.2);
    color: #c4b5fd; padding: 0.18rem 0.55rem;
    border-radius: 12px; white-space: nowrap; flex-shrink: 0; margin-left: 0.7rem;
}

/* ── AI report ────────────────────── */
.report-body {
    color: #94a3b8; line-height: 1.85;
    font-size: 0.88rem; white-space: pre-wrap;
}

/* ── Input ────────────────────────── */
.stTextInput input {
    background: rgba(10,15,30,0.92) !important;
    border: 1px solid rgba(148,163,184,0.11) !important;
    border-radius: 10px !important; color: #f8fafc !important;
    font-size: 0.95rem !important; padding: 0.85rem 1.1rem !important;
    transition: border-color 0.25s, box-shadow 0.25s !important;
}
.stTextInput input:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.12) !important;
}
.stTextInput input::placeholder { color: #334155 !important; }

/* ── Button ───────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
    color: #fff !important; border: none !important;
    border-radius: 10px !important; padding: 0.85rem 1.5rem !important;
    font-weight: 700 !important; font-size: 0.9rem !important;
    letter-spacing: 0.04em !important; width: 100% !important;
    transition: transform 0.2s, box-shadow 0.2s !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 14px 32px rgba(124,58,237,0.38) !important;
}

hr { border-color: rgba(148,163,184,0.06); margin: 2rem 0; }
p, div, span, li { color: #94a3b8; }
.stSpinner > div { border-top-color: #6366f1 !important; }
.footer { text-align:center; color:#1e293b; font-size:0.76rem; padding:2rem 0 1rem; }
</style>
""", unsafe_allow_html=True)


# ─── Helpers ───────────────────────────────────────────────────────────────────

def score_color(score):
    if score >= 80: return "#22c55e"
    if score >= 50: return "#fbbf24"
    return "#ef4444"

def animated_score_ring(score: int, risk_level: str) -> str:
    color = score_color(score)
    risk_colors = {
        "Low Risk": "#86efac", "Medium Risk": "#fde047", "High Risk": "#fca5a5"
    }
    risk_col = risk_colors.get(risk_level, "#94a3b8")
    r = 80
    circ = 2 * 3.14159265 * r
    return f"""
    <!DOCTYPE html><html><head>
    <meta charset="utf-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{
            margin:0; background:#0d1428;
            display:flex; justify-content:center; align-items:center;
            height:270px; overflow:hidden;
        }}
        .wrap {{ display:flex; flex-direction:column; align-items:center; gap:0.9rem; }}
        .ring-box {{ position:relative; width:190px; height:190px; }}
        svg {{ position:absolute; top:0; left:0; }}
        #ring {{
            stroke-dasharray: {circ:.2f};
            stroke-dashoffset: {circ:.2f};
            transition: stroke-dashoffset 1.6s cubic-bezier(.4,0,.2,1);
            filter: drop-shadow(0 0 10px {color}99);
        }}
        .inner {{
            position:absolute; top:50%; left:50%;
            transform:translate(-50%,-54%);
            text-align:center;
        }}
        .num {{
            font-family:'Inter',sans-serif; font-size:2.7rem;
            font-weight:800; color:{color}; line-height:1;
            text-shadow: 0 0 20px {color}66;
        }}
        .lbl {{
            font-family:'Inter',sans-serif; font-size:0.6rem;
            font-weight:700; color:#334155;
            text-transform:uppercase; letter-spacing:0.12em; margin-top:0.2rem;
        }}
        .risk-lbl {{
            font-family:'Inter',sans-serif; font-size:0.82rem;
            font-weight:700; color:{risk_col}; letter-spacing:0.02em;
        }}
    </style></head><body>
    <div class="wrap">
        <div class="ring-box">
            <svg viewBox="0 0 200 200" width="190" height="190">
                <circle cx="100" cy="100" r="{r}" fill="none"
                    stroke="#1e293b" stroke-width="11"/>
                <circle id="ring" cx="100" cy="100" r="{r}" fill="none"
                    stroke="{color}" stroke-width="11" stroke-linecap="round"
                    transform="rotate(-90 100 100)"/>
            </svg>
            <div class="inner">
                <div class="num" id="counter">0</div>
                <div class="lbl">Credit Score</div>
            </div>
        </div>
        <div class="risk-lbl">{risk_level}</div>
    </div>
    <script>
        const target = {score};
        const targetOffset = {circ - (score / 100) * circ:.2f};
        const ring = document.getElementById('ring');
        const counter = document.getElementById('counter');
        setTimeout(() => {{
            ring.style.strokeDashoffset = targetOffset;
            let cur = 0;
            const total = 1600, fps = 60, step = target / (total / (1000/fps));
            const t = setInterval(() => {{
                cur = Math.min(cur + step, target);
                counter.textContent = Math.round(cur);
                if (cur >= target) clearInterval(t);
            }}, 1000/fps);
        }}, 120);
    </script>
    </body></html>
    """

def animated_bars_html(comps: dict) -> str:
    rows = ""
    for i, (label, value) in enumerate(comps.items()):
        color = "#22c55e" if value >= 80 else "#fbbf24" if value >= 50 else "#ef4444"
        delay = i * 0.12
        rows += f"""
        <style>
          @keyframes bf{i} {{ from {{ width:0 }} to {{ width:{value}% }} }}
        </style>
        <div style="margin-bottom:0.85rem">
          <div style="display:flex;justify-content:space-between;margin-bottom:0.35rem">
            <span style="font-size:0.77rem;color:#64748b;font-weight:500;
                         font-family:Inter,sans-serif">{label}</span>
            <span style="font-size:0.77rem;color:{color};font-weight:700;
                         font-family:Inter,sans-serif">{value}</span>
          </div>
          <div style="background:rgba(30,41,59,0.55);border-radius:6px;
                      height:7px;overflow:hidden">
            <div style="height:100%;border-radius:6px;
                        background:linear-gradient(90deg,{color}88,{color});
                        box-shadow:0 0 10px {color}55;
                        width:0%;
                        animation:bf{i} 1.3s cubic-bezier(.4,0,.2,1) {delay:.2f}s forwards">
            </div>
          </div>
        </div>"""
    return rows

def build_components(risk: dict) -> dict:
    reasons = [r.lower() for r in risk.get("reasons", [])]
    c = {"Status":100,"Company Age":100,"Accounts":100,"Directors":100,"Legal Health":100,"Sector":100}
    for r in reasons:
        if "status"                          in r: c["Status"]       = 10
        elif "2 years old"                   in r: c["Company Age"]  = 25
        elif "5 years old"                   in r: c["Company Age"]  = 60
        elif "accounts"                      in r: c["Accounts"]     = 25
        elif "director"                      in r: c["Directors"]    = 20
        elif "insolvency"                    in r: c["Legal Health"] = 10
        elif "charge"                        in r: c["Legal Health"] = min(c["Legal Health"], 65)
        elif "dissolved" in r or "liquidation" in r: c["Legal Health"] = 5
        elif "sector" in r or "sic"          in r: c["Sector"]       = 85
    return c

def risk_badge(level: str) -> str:
    if not level: return '<span style="color:#94a3b8">— Unknown</span>'
    l = level.lower()
    if "low"    in l: return '<span style="background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.28);color:#86efac;padding:.4rem 1rem;border-radius:20px;font-size:.85rem;font-weight:700;display:inline-block">▲ Low Risk</span>'
    if "medium" in l: return '<span style="background:rgba(251,191,36,.12);border:1px solid rgba(251,191,36,.28);color:#fde047;padding:.4rem 1rem;border-radius:20px;font-size:.85rem;font-weight:700;display:inline-block">◆ Medium Risk</span>'
    if "high"   in l: return '<span style="background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.28);color:#fca5a5;padding:.4rem 1rem;border-radius:20px;font-size:.85rem;font-weight:700;display:inline-block">▼ High Risk</span>'
    return f'<span style="color:#94a3b8">{level}</span>'


# ─── Header ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero">
  <div class="hero-title">Credit Risk Intelligence</div>
  <div class="hero-sub">Real-time UK company credit assessment · Companies House + AI</div>
</div>
""", unsafe_allow_html=True)


# ─── Search ────────────────────────────────────────────────────────────────────

c1, c2 = st.columns([4, 1])
with c1:
    company_number = st.text_input(
        "num",
        placeholder="UK company number — e.g. 08804411 (Revolut)",
        label_visibility="collapsed",
    )
with c2:
    go_btn = st.button("Analyse →", use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)


# ─── Fetch ─────────────────────────────────────────────────────────────────────

if go_btn:
    if not company_number.strip():
        st.warning("Please enter a company number.")
    else:
        with st.spinner("Fetching live data and analysing risk…"):
            try:
                resp = requests.get(
                    API_URL,
                    params={"company_number": company_number.strip()},
                    timeout=60,
                )
                resp.raise_for_status()
                st.session_state["result"] = resp.json()
            except requests.exceptions.RequestException as e:
                st.error(f"Request failed: {e}")
                st.stop()


# ─── Display ───────────────────────────────────────────────────────────────────

if "result" not in st.session_state:
    st.stop()

result  = st.session_state["result"]
profile = result.get("profile", {})
risk    = result.get("risk", {})
llm     = result.get("llm_report", "")

if "error" in profile:
    st.error(f"Could not retrieve company: {profile.get('message', profile['error'])}")
    st.stop()


# ── 1. Company Profile ──────────────────────────────────────────────────────────

status_raw  = profile.get("company_status", "unknown")
status_cls  = "status-active" if status_raw.lower() == "active" else "status-other"
addr        = profile.get("registered_office_address", {})
address     = ", ".join(filter(None, [
    addr.get("address_line_1"), addr.get("locality"),
    addr.get("country"), addr.get("postal_code"),
]))
accounts    = profile.get("accounts", {})
conf        = profile.get("confirmation_statement", {})
directors   = profile.get("directors", [])
next_acc_due = (
    accounts.get("next_accounts", {}).get("due_on")
    or accounts.get("next_due", "N/A")
)

st.markdown(f"""
<div class="card">
  <div class="section-label">Company Profile</div>
  <div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap;margin-bottom:0.2rem">
    <span class="co-name">{profile.get("company_name","Unknown")}</span>
    <span class="{status_cls}">● {status_raw.upper()}</span>
  </div>
  <div class="address-line">📍 {address or "Address not available"}</div>
  <div class="meta-grid">
    <div class="meta-item"><div class="meta-lbl">Company Number</div><div class="meta-val">{profile.get("company_number","N/A")}</div></div>
    <div class="meta-item"><div class="meta-lbl">Incorporated</div><div class="meta-val">{profile.get("date_of_creation","N/A")}</div></div>
    <div class="meta-item"><div class="meta-lbl">Type</div><div class="meta-val">{profile.get("type","N/A").upper()}</div></div>
    <div class="meta-item"><div class="meta-lbl">Active Directors</div><div class="meta-val">{len(directors)}</div></div>
    <div class="meta-item"><div class="meta-lbl">Next Accounts Due</div><div class="meta-val">{next_acc_due}</div></div>
    <div class="meta-item"><div class="meta-lbl">Confirmation Due</div><div class="meta-val">{conf.get("next_due","N/A")}</div></div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── 2. Risk Dashboard ───────────────────────────────────────────────────────────

st.markdown("<div class='section-label' style='padding:0 0.1rem 0.6rem'>Risk Assessment</div>", unsafe_allow_html=True)

col_ring, col_bars = st.columns(2)

with col_ring:
    st.markdown("<div class='card' style='padding:1.4rem 1.7rem 0.8rem'>", unsafe_allow_html=True)
    st.markdown("<div class='section-label'>Credit Score</div>", unsafe_allow_html=True)
    components.html(
        animated_score_ring(risk.get("credit_score", 0), risk.get("risk_level", "")),
        height=280,
    )
    st.markdown("</div>", unsafe_allow_html=True)

with col_bars:
    comps = build_components(risk)
    st.markdown(f"""
    <div class="card">
      <div class="section-label">Risk Factor Breakdown</div>
      {animated_bars_html(comps)}
    </div>
    """, unsafe_allow_html=True)


# ── 3. Reasons + legal ──────────────────────────────────────────────────────────

if reasons := risk.get("reasons", []):
    tags = "".join(f"<span class='reason-tag'>⚠ {r}</span>" for r in reasons)
    st.markdown(f"<div style='margin:0.3rem 0 0.5rem'>{tags}</div>", unsafe_allow_html=True)

if legal := risk.get("legal_summary"):
    st.markdown(f"<div class='legal-box'>⚖️ {legal}</div>", unsafe_allow_html=True)


# ── 4. Persons with Significant Control ────────────────────────────────────────

psc_list = profile.get("persons_with_significant_control", [])
if psc_list:
    st.markdown("<br>", unsafe_allow_html=True)
    rows = ""
    for p in psc_list[:8]:
        name    = p.get("name", "Unknown")
        country = p.get("country_of_residence") or p.get("nationality", "")
        natures = p.get("natures_of_control", [])
        badge   = natures[0].replace("-", " ").title() if natures else "—"
        rows += f"""
        <div class="psc-row">
          <div>
            <div class="psc-name">{name}</div>
            <div class="psc-detail">{country}</div>
          </div>
          <span class="psc-badge">{badge}</span>
        </div>"""
    st.markdown(f"""
    <div class="card">
      <div class="section-label">Persons with Significant Control · {len(psc_list)} found</div>
      {rows}
    </div>
    """, unsafe_allow_html=True)


# ── 5. AI Report ────────────────────────────────────────────────────────────────

if llm:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="card">
      <div class="section-label">AI Credit Risk Report · Llama 3.3 70B via Groq</div>
      <div class="report-body">{llm}</div>
    </div>
    """, unsafe_allow_html=True)


# ─── Footer ────────────────────────────────────────────────────────────────────

st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("""
<div class="footer">
  Companies House API &nbsp;·&nbsp; Groq Llama 3.3 70B &nbsp;·&nbsp; Streamlit + Python
</div>
""", unsafe_allow_html=True)
