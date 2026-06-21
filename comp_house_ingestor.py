import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY")
BASE_URL = "https://api.company-information.service.gov.uk/company"
OFFICERS_BASE = "https://api.company-information.service.gov.uk/officers"


def _get(url, auth, params=None):
    try:
        r = requests.get(url, auth=auth, params=params, timeout=10)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def _fetch_director_network(director, auth):
    """Return summary of a director's other appointments."""
    links = director.get("links", {})
    officer_path = links.get("officer", {}).get("appointments", "")
    if not officer_path:
        return None
    full_url = f"https://api.company-information.service.gov.uk{officer_path}"
    data = _get(full_url, auth, params={"items_per_page": 50})
    if not data:
        return None

    items = data.get("items", [])
    total = data.get("total_results", len(items))
    active, dissolved, resigned = [], [], []
    for apt in items:
        co_status = (apt.get("appointed_to", {}).get("company_status") or "").lower()
        co_name = apt.get("appointed_to", {}).get("company_name", "")
        co_number = apt.get("appointed_to", {}).get("company_number", "")
        entry = {"name": co_name, "number": co_number, "status": co_status}
        if apt.get("resigned_on"):
            if co_status in ("dissolved", "liquidation", "receivership"):
                dissolved.append(entry)
            else:
                resigned.append(entry)
        else:
            active.append(entry)

    return {
        "name": director.get("name", ""),
        "total_appointments": total,
        "active": active[:6],
        "dissolved_resigned": dissolved[:6],
        "active_count": len(active),
        "dissolved_count": len(dissolved),
    }


def fetch_company_data(company_number: str):
    try:
        auth = (API_KEY, "")

        # Core profile
        profile_resp = requests.get(f"{BASE_URL}/{company_number}", auth=auth, timeout=10)
        if profile_resp.status_code != 200:
            return {"error": profile_resp.status_code, "message": profile_resp.text}
        profile = profile_resp.json()

        # Fire parallel requests for all secondary endpoints
        endpoints = {
            "officers":   (f"{BASE_URL}/{company_number}/officers",
                           {"register_type": "directors", "items_per_page": 100}),
            "psc":        (f"{BASE_URL}/{company_number}/persons-with-significant-control",
                           {"items_per_page": 25}),
            "filing":     (f"{BASE_URL}/{company_number}/filing-history",
                           {"items_per_page": 30}),
            "charges":    (f"{BASE_URL}/{company_number}/charges",
                           {"items_per_page": 100}),
            "insolvency": (f"{BASE_URL}/{company_number}/insolvency",
                           None),
        }

        results = {}
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                pool.submit(_get, url, auth, params): key
                for key, (url, params) in endpoints.items()
            }
            for future in as_completed(futures):
                results[futures[future]] = future.result()

        # ── Officers / directors ──────────────────────────────────────────────
        if results.get("officers"):
            items = results["officers"].get("items", [])
            profile["directors"] = [o for o in items if not o.get("resigned_on")]

        # ── PSC ───────────────────────────────────────────────────────────────
        if results.get("psc"):
            profile["persons_with_significant_control"] = results["psc"].get("items", [])

        # ── Filing history ────────────────────────────────────────────────────
        if results.get("filing"):
            fdata = results["filing"]
            items = fdata.get("items", [])
            profile["filing_history"] = {
                "total_count": fdata.get("total_count", 0),
                "recent": [
                    {
                        "type": f.get("type"),
                        "description": f.get("description", ""),
                        "date": f.get("date"),
                        "action_date": f.get("action_date"),
                        "paper_filed": f.get("paper_filed", False),
                    }
                    for f in items[:15]
                ],
            }

        # ── Charges ───────────────────────────────────────────────────────────
        if results.get("charges"):
            cdata = results["charges"]
            items = cdata.get("items", [])
            outstanding = [c for c in items if (c.get("status") or "").lower() not in ("satisfied", "fully-satisfied", "part-satisfied")]
            profile["charges"] = {
                "total_count": cdata.get("total_count", len(items)),
                "outstanding_count": len(outstanding),
                "charges": [
                    {
                        "created": c.get("created_on", ""),
                        "status": c.get("status", ""),
                        "type": c.get("charge_number", ""),
                        "persons_entitled": [p.get("name", "") for p in c.get("persons_entitled", [])],
                        "particulars": (c.get("particulars", {}) or {}).get("description", ""),
                    }
                    for c in items[:10]
                ],
            }

        # ── Insolvency ────────────────────────────────────────────────────────
        if results.get("insolvency"):
            idata = results["insolvency"]
            cases = idata.get("cases", [])
            profile["insolvency"] = {
                "has_insolvency": len(cases) > 0,
                "cases": [
                    {
                        "type": c.get("type", ""),
                        "dates": c.get("dates", []),
                        "practitioners": [
                            p.get("name", "") for p in c.get("practitioners", [])
                        ],
                    }
                    for c in cases[:5]
                ],
            }

        # ── Director network (parallel, up to 4 directors) ────────────────────
        directors = profile.get("directors", [])
        if directors:
            network = []
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = {
                    pool.submit(_fetch_director_network, d, auth): d.get("name", "")
                    for d in directors[:4]
                }
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        network.append(result)
            profile["director_network"] = network

        return profile

    except Exception as e:
        return {"error": str(e)}
