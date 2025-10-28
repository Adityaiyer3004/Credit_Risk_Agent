import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY")
BASE_URL = "https://api.company-information.service.gov.uk/company"

def fetch_company_data(company_number: str):
    """Fetch basic company info from Companies House."""
    try:
        url = f"{BASE_URL}/{company_number}"
        response = requests.get(url, auth=(API_KEY, ""))

        if response.status_code != 200:
            return {"error": response.status_code, "message": response.text}

        return response.json()

    except Exception as e:
        return {"error": str(e)}
