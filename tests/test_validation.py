"""Tests for UK company number validation and Altman Z'-Score calculation."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app

client = TestClient(app, raise_server_exceptions=False)
API_KEY = os.getenv("CREDIT_RISK_API_KEY", "test-key")
HEADERS = {"X-API-Key": API_KEY}


# ── Company number validation ─────────────────────────────────────────────────

VALID_NUMBERS = [
    "08804411",   # standard 8-digit
    "8804411",    # 7-digit → should pad to 00884411? no, pad to 08804411
    "00000001",   # leading zeros
    "SC123456",   # Scottish
    "NI123456",   # Northern Ireland
    "OC123456",   # LLP
    "LP123456",   # Limited Partnership
]

INVALID_NUMBERS = [
    "ABC12345",   # bad prefix
    "123",        # too short
    "NOTANUMBER", # no digits
    "12345678901",# too long
    "",           # empty
    "$$$$$$$$",   # special chars
]

@pytest.mark.parametrize("cn", VALID_NUMBERS)
def test_valid_company_numbers_not_422(cn):
    with patch("analyze.fetch_company_data") as mock_fetch, \
         patch("analyze.generate_full_company_risk_report") as mock_report:
        mock_fetch.return_value = {
            "company_name": "Test Co",
            "company_number": cn.zfill(8),
            "company_status": "active",
        }
        mock_report.return_value = {
            "risk": {"credit_score": 70, "risk_level": "Low Risk", "reasons": []},
            "baseline_report": "",
            "llm_report": "",
            "guardrail": {"overall_grade": "A", "flags": [], "passed": 4, "total": 4},
        }
        r = client.get(f"/api/analyze?company_number={cn}", headers=HEADERS)
        assert r.status_code != 422, f"Expected valid number {cn!r} to pass, got 422"

@pytest.mark.parametrize("cn", INVALID_NUMBERS)
def test_invalid_company_numbers_return_422(cn):
    r = client.get(f"/api/analyze?company_number={cn}", headers=HEADERS)
    assert r.status_code == 422, f"Expected {cn!r} to return 422, got {r.status_code}"

def test_numeric_number_padded_to_8_digits():
    """A 7-digit number like '8804411' should be padded to '08804411'."""
    with patch("analyze.fetch_company_data") as mock_fetch, \
         patch("analyze.generate_full_company_risk_report") as mock_report:
        mock_fetch.return_value = {"company_name": "Test", "company_number": "08804411", "company_status": "active"}
        mock_report.return_value = {
            "risk": {"credit_score": 70, "risk_level": "Low Risk", "reasons": []},
            "baseline_report": "", "llm_report": "",
            "guardrail": {"overall_grade": "A", "flags": [], "passed": 4, "total": 4},
        }
        r = client.get("/api/analyze?company_number=8804411", headers=HEADERS)
        assert r.status_code == 200
        # Normalised number should appear in response
        assert r.json().get("company_number") == "08804411"


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_no_api_key_returns_401():
    r = client.get("/api/analyze?company_number=08804411")
    assert r.status_code == 401

def test_wrong_api_key_returns_401():
    r = client.get("/api/analyze?company_number=08804411", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401

def test_correct_api_key_passes_auth():
    with patch("analyze.fetch_company_data") as mock_fetch, \
         patch("analyze.generate_full_company_risk_report") as mock_report:
        mock_fetch.return_value = {"company_name": "Test", "company_number": "08804411", "company_status": "active"}
        mock_report.return_value = {
            "risk": {"credit_score": 70, "risk_level": "Low Risk", "reasons": []},
            "baseline_report": "", "llm_report": "",
            "guardrail": {"overall_grade": "A", "flags": [], "passed": 4, "total": 4},
        }
        r = client.get("/api/analyze?company_number=08804411", headers=HEADERS)
        assert r.status_code == 200


# ── Response structure ────────────────────────────────────────────────────────

def test_response_has_required_fields():
    with patch("analyze.fetch_company_data") as mock_fetch, \
         patch("analyze.generate_full_company_risk_report") as mock_report:
        mock_fetch.return_value = {"company_name": "Test Co", "company_number": "08804411", "company_status": "active"}
        mock_report.return_value = {
            "risk": {"credit_score": 70, "risk_level": "Low Risk", "reasons": ["Valid LEI registered"]},
            "baseline_report": "baseline",
            "llm_report": "1. EXECUTIVE SUMMARY\nTest.\n2. CREDIT SCORE INTERPRETATION\nTest.\n3. RISK FACTOR ANALYSIS\nTest.\n4. LEGAL AND FINANCIAL POSITION\nTest.\n5. CREDIT OPINION\nTest.",
            "guardrail": {"overall_grade": "A", "flags": [], "passed": 4, "total": 4,
                         "factual_grounded": True, "tone_calibrated": True,
                         "solvency_vs_gov": True, "format_compliant": True},
        }
        r = client.get("/api/analyze?company_number=08804411", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        for field in ("company_number", "company_name", "profile", "risk", "llm_report", "guardrail"):
            assert field in body, f"Missing field: {field}"

def test_ch_not_found_returns_404():
    with patch("analyze.fetch_company_data") as mock_fetch:
        mock_fetch.return_value = {"error": "not found", "message": "Company not found"}
        r = client.get("/api/analyze?company_number=00000000", headers=HEADERS)
        assert r.status_code == 404
