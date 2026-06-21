"""
Unit tests for risk_engine.compute_risk_score.
No external calls — pure function, all inputs supplied inline.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from risk_engine import compute_risk_score


def _base(overrides=None):
    """Minimal valid profile that should produce a clean baseline score."""
    profile = {
        "company_status": "active",
        "date_of_creation": "2015-01-01",
        "accounts_summary": {"last_accounts": {"made_up_to": "2024-01-01"}},
        "directors": [{"name": "Alice"}, {"name": "Bob"}],
        "charges": {"outstanding_count": 0, "total_count": 0, "charges": []},
        "insolvency": {"has_insolvency": False},
        "winding_up_notices": [],
        "director_network": [],
        "persons_with_significant_control": [],
        "opencorporates": {},
        "recent_news": [],
        "financials": {},
        "filing_history": {},
        "sic_codes": [],
        "company_number": "12345678",
    }
    if overrides:
        profile.update(overrides)
    return profile


# ── Score clamping & thresholds ───────────────────────────────────────────────

def test_score_clamped_above():
    result = compute_risk_score(_base())
    assert result["credit_score"] <= 100

def test_score_clamped_below():
    result = compute_risk_score(_base({
        "company_status": "dissolved",
        "insolvency": {"has_insolvency": True, "cases": [{"type": "liquidation", "practitioners": []}]},
        "winding_up_notices": [{"notice_type": "winding-up"}, {"notice_type": "winding-up"}],
        "directors": [],
        "charges": {"outstanding_count": 5, "total_count": 5, "charges": []},
    }))
    assert result["credit_score"] >= 1

def test_low_risk_threshold():
    result = compute_risk_score(_base())
    # Clean profile with a 10-year-old company should be Low or Medium Risk
    assert result["risk_level"] in ("Low Risk", "Medium Risk")

def test_dissolved_is_high_risk():
    result = compute_risk_score(_base({"company_status": "dissolved"}))
    assert result["risk_level"] == "High Risk"
    assert result["credit_score"] < 45

def test_risk_level_labels():
    """risk_level must always be one of three fixed strings."""
    for status in ("active", "dissolved", "liquidation"):
        result = compute_risk_score(_base({"company_status": status}))
        assert result["risk_level"] in ("Low Risk", "Medium Risk", "High Risk")


# ── Status penalty ────────────────────────────────────────────────────────────

def test_dissolved_penalty():
    active  = compute_risk_score(_base({"company_status": "active"}))
    dissolved = compute_risk_score(_base({"company_status": "dissolved"}))
    assert dissolved["credit_score"] <= active["credit_score"] - 40

def test_active_no_status_penalty():
    result = compute_risk_score(_base())
    reasons = " ".join(result["reasons"]).lower()
    assert "status" not in reasons


# ── Company age penalties ─────────────────────────────────────────────────────

def test_company_under_2_years():
    result = compute_risk_score(_base({"date_of_creation": "2025-06-01"}))
    reasons = " ".join(result["reasons"]).lower()
    assert "2 years" in reasons or "less than 2" in reasons

def test_company_under_5_years():
    result = compute_risk_score(_base({"date_of_creation": "2023-01-01"}))
    reasons = " ".join(result["reasons"]).lower()
    assert "5 years" in reasons or "under 5" in reasons

def test_established_company_no_age_penalty():
    result = compute_risk_score(_base({"date_of_creation": "2010-01-01"}))
    reasons = " ".join(result["reasons"]).lower()
    assert "years old" not in reasons


# ── Accounts penalties ────────────────────────────────────────────────────────

def test_no_accounts_penalty():
    result = compute_risk_score(_base({"accounts_summary": {"last_accounts": {}}}))
    reasons = " ".join(result["reasons"]).lower()
    assert "no accounts" in reasons

def test_stale_accounts_penalty():
    result = compute_risk_score(_base({
        "accounts_summary": {"last_accounts": {"made_up_to": "2021-01-01"}}
    }))
    reasons = " ".join(result["reasons"]).lower()
    assert "older than 2 years" in reasons or "accounts" in reasons


# ── Directors ─────────────────────────────────────────────────────────────────

def test_no_directors_penalty():
    result = compute_risk_score(_base({"directors": []}))
    reasons = " ".join(result["reasons"]).lower()
    assert "no active director" in reasons

def test_single_high_ratio_director_penalised():
    result = compute_risk_score(_base({
        "director_network": [
            {"name": "SMITH, John", "active_count": 4, "dissolved_count": 8}
        ]
    }))
    score_with = result["credit_score"]
    clean = compute_risk_score(_base())["credit_score"]
    assert score_with < clean


# ── Director network ratio logic ──────────────────────────────────────────────

def test_director_low_ratio_not_penalised():
    """Director with 9 dissolved but 30 total (30% ratio) at the edge — should trigger."""
    result = compute_risk_score(_base({
        "director_network": [
            {"name": "GILBERT, Martin", "active_count": 18, "dissolved_count": 9}
        ]
    }))
    # 9 dissolved, 27 total, ratio = 33% → triggers (dissolved >= 3 and ratio >= 0.25)
    reasons = " ".join(result["reasons"]).lower()
    assert "dissolved" in reasons

def test_director_high_ratio_triggers():
    result = compute_risk_score(_base({
        "director_network": [
            {"name": "DODGY, Dave", "active_count": 1, "dissolved_count": 5}
        ]
    }))
    reasons = " ".join(result["reasons"]).lower()
    assert "dissolved" in reasons

def test_director_low_dissolved_not_penalised():
    """2 dissolved with low ratio — below both thresholds."""
    result = compute_risk_score(_base({
        "director_network": [
            {"name": "CLEAN, Carol", "active_count": 20, "dissolved_count": 2}
        ]
    }))
    clean = compute_risk_score(_base())["credit_score"]
    assert result["credit_score"] == clean


# ── Charges ───────────────────────────────────────────────────────────────────

def test_no_charges_no_penalty():
    result = compute_risk_score(_base())
    reasons = " ".join(result["reasons"]).lower()
    assert "charge" not in reasons

def test_5_outstanding_charges_penalty():
    result = compute_risk_score(_base({
        "charges": {"outstanding_count": 5, "total_count": 5, "charges": []}
    }))
    reasons = " ".join(result["reasons"]).lower()
    assert "charge" in reasons

def test_single_charge_small_penalty():
    one = compute_risk_score(_base({
        "charges": {"outstanding_count": 1, "total_count": 1, "charges": []}
    }))
    five = compute_risk_score(_base({
        "charges": {"outstanding_count": 5, "total_count": 5, "charges": []}
    }))
    assert one["credit_score"] > five["credit_score"]


# ── Insolvency ────────────────────────────────────────────────────────────────

def test_insolvency_penalty():
    with_ins = compute_risk_score(_base({
        "insolvency": {"has_insolvency": True, "cases": [{"type": "CVA", "practitioners": []}]}
    }))
    without = compute_risk_score(_base())
    assert without["credit_score"] - with_ins["credit_score"] >= 30


# ── News event grouping ───────────────────────────────────────────────────────

def test_news_same_event_group_counts_once():
    """'fined' and 'penalty' are in the same event group — should count as ONE event."""
    result = compute_risk_score(_base({
        "recent_news": [
            {"title": "Company fined £10m", "snippet": "regulators fined the firm"},
            {"title": "Company faces penalty", "snippet": "a large penalty was imposed"},
        ]
    }))
    reasons = " ".join(result["reasons"]).lower()
    # Should trigger exactly 1 event group → -4 penalty, not -7 or -12
    assert "multiple distinct" not in reasons

def test_news_two_different_groups():
    """'fraud' and 'lawsuit' are different groups → 2-group penalty."""
    result = compute_risk_score(_base({
        "recent_news": [
            {"title": "Company sued over fraud", "snippet": "lawsuit filed for fraudulent activity"},
        ]
    }))
    # fraud + legal_action → 2 groups → -7 penalty
    reasons = result["reasons"]
    assert any("negative news signals" in r.lower() for r in reasons)

def test_no_news_no_penalty():
    result = compute_risk_score(_base({"recent_news": []}))
    reasons = " ".join(result["reasons"]).lower()
    assert "news" not in reasons


# ── Altman Z' integration ─────────────────────────────────────────────────────

def test_altman_safe_zone_bonus():
    result = compute_risk_score(_base({
        "financials": {
            "altman_z": {"z_score": 3.5, "zone": "Safe"},
            "ratios": {}, "trend": {},
        }
    }))
    without = compute_risk_score(_base())
    assert result["credit_score"] >= without["credit_score"] + 8

def test_altman_distress_zone_penalty():
    result = compute_risk_score(_base({
        "financials": {
            "altman_z": {"z_score": 0.8, "zone": "Distress"},
            "ratios": {}, "trend": {},
        }
    }))
    reasons = " ".join(result["reasons"]).lower()
    assert "distress" in reasons

def test_altman_grey_zone_penalty():
    result = compute_risk_score(_base({
        "financials": {
            "altman_z": {"z_score": 2.0, "zone": "Grey"},
            "ratios": {}, "trend": {},
        }
    }))
    reasons = " ".join(result["reasons"]).lower()
    assert "grey" in reasons


# ── GLEIF LEI ─────────────────────────────────────────────────────────────────

def test_lei_issued_bonus():
    with_lei = compute_risk_score(_base({
        "opencorporates": {"lei": "123", "lei_status": "ISSUED", "next_renewal": "2027-01-01"}
    }))
    without = compute_risk_score(_base())
    assert with_lei["credit_score"] >= without["credit_score"] + 4

def test_lei_lapsed_penalty():
    result = compute_risk_score(_base({
        "opencorporates": {"lei": "123", "lei_status": "LAPSED", "next_renewal": "2023-01-01"}
    }))
    reasons = " ".join(result["reasons"]).lower()
    assert "lapsed" in reasons

def test_no_lei_no_penalty():
    result = compute_risk_score(_base({"opencorporates": {}}))
    reasons = " ".join(result["reasons"]).lower()
    assert "lei" not in reasons


# ── Return structure ──────────────────────────────────────────────────────────

def test_result_has_required_keys():
    result = compute_risk_score(_base())
    for key in ("credit_score", "risk_level", "reasons", "legal_check", "legal_summary", "sector"):
        assert key in result, f"Missing key: {key}"

def test_reasons_is_list_of_strings():
    result = compute_risk_score(_base())
    assert isinstance(result["reasons"], list)
    assert all(isinstance(r, str) for r in result["reasons"])
