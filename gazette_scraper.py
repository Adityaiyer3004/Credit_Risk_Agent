import os
import requests
from dotenv import load_dotenv

# ✅ Load environment variables
load_dotenv()
API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY")

def scrape_gazette_events(company_number: str):
    """
    Robust, API-based replacement for Gazette scraping.
    Uses Companies House insolvency + charges endpoints.
    """
    base_url = f"https://api.company-information.service.gov.uk/company/{company_number}"
    auth = (API_KEY, "")
    notices = []
    note = ""

    try:
        # 1️⃣ Insolvency check
        insolvency_url = f"{base_url}/insolvency"
        r1 = requests.get(insolvency_url, auth=auth, timeout=10)
        if r1.status_code == 200:
            data = r1.json()
            if data and data != {}:
                notices.append({
                    "title": "Insolvency Record",
                    "url": insolvency_url
                })
        elif r1.status_code != 404:
            note += f"Insolvency fetch returned {r1.status_code}. "

        # 2️⃣ Charges check
        charges_url = f"{base_url}/charges"
        r2 = requests.get(charges_url, auth=auth, timeout=10)
        if r2.status_code == 200:
            data = r2.json()
            if data.get("total_count", 0) > 0:
                notices.append({
                    "title": "Registered Charges",
                    "url": charges_url
                })
        elif r2.status_code != 404:
            note += f"Charges fetch returned {r2.status_code}. "

        # 3️⃣ Company status clarification
        profile_url = f"https://api.company-information.service.gov.uk/company/{company_number}"
        company = requests.get(profile_url, auth=auth, timeout=10).json()
        if company.get("company_status") in ("dissolved", "liquidation"):
            note += " (Company dissolved or in liquidation, historical data may be archived)"

        # 4️⃣ Output note
        if notices:
            note += f" Found {len(notices)} legal record(s) via Companies House."
        else:
            if not note:
                note = "No insolvency or charge records found"

        return {"notices": notices, "note": note}

    except Exception as e:
        return {"notices": [], "note": f"Companies House fetch failed: {e}"}
