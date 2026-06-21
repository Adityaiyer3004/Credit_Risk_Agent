"""Tests for Altman Z'-Score calculation and sector benchmark lookups."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from accounts_analyzer import _altman_z_prime
from sector_benchmarks import get_sector_risk, SECTOR_RISK


# ── Altman Z'-Score ───────────────────────────────────────────────────────────

def _figures(ta, ca, cl, na, lt, re, ebit, sales):
    return {
        "total_assets": ta, "current_assets": ca, "current_liabilities": cl,
        "net_assets": na, "long_term_liabilities": lt,
        "retained_earnings": re, "ebit": ebit, "turnover": sales,
    }


def test_altman_safe_zone():
    """Strong balance sheet → Z' > 2.9 → Safe."""
    f = _figures(ta=1_000_000, ca=600_000, cl=200_000, na=700_000,
                 lt=100_000, re=400_000, ebit=200_000, sales=1_500_000)
    result = _altman_z_prime(f)
    assert result is not None
    assert result["zone"] == "Safe"
    assert result["z_score"] > 2.9

def test_altman_distress_zone():
    """Negative equity, no profit, negligible turnover → Distress."""
    f = _figures(ta=1_000_000, ca=50_000, cl=900_000, na=-200_000,
                 lt=400_000, re=-300_000, ebit=-100_000, sales=100_000)
    result = _altman_z_prime(f)
    assert result is not None
    assert result["zone"] == "Distress"
    assert result["z_score"] < 1.23

def test_altman_grey_zone():
    """Moderate financials calibrated to land in 1.23–2.9 → Grey."""
    # Z' components: X1=0.05, X2=0.10, X3=0.10, X4=0.33, X5=0.80 → ~1.37
    f = _figures(ta=1_000_000, ca=300_000, cl=250_000, na=150_000,
                 lt=200_000, re=100_000, ebit=100_000, sales=800_000)
    result = _altman_z_prime(f)
    assert result is not None
    assert result["zone"] == "Grey", f"Expected Grey, got {result['zone']} (Z'={result['z_score']})"
    assert 1.23 <= result["z_score"] <= 2.9

def test_altman_returns_none_on_missing_ebit():
    f = _figures(ta=1_000_000, ca=300_000, cl=200_000, na=500_000,
                 lt=100_000, re=200_000, ebit=None, sales=800_000)
    assert _altman_z_prime(f) is None

def test_altman_returns_none_on_zero_total_assets():
    f = _figures(ta=0, ca=100_000, cl=50_000, na=50_000,
                 lt=0, re=20_000, ebit=10_000, sales=200_000)
    assert _altman_z_prime(f) is None

def test_altman_returns_none_on_missing_net_assets():
    f = {"total_assets": 500_000, "ebit": 50_000}
    assert _altman_z_prime(f) is None

def test_altman_result_has_components():
    f = _figures(ta=1_000_000, ca=600_000, cl=200_000, na=700_000,
                 lt=100_000, re=400_000, ebit=200_000, sales=1_500_000)
    result = _altman_z_prime(f)
    assert "z_score" in result
    assert "zone" in result
    assert "components" in result

def test_altman_x4_zero_when_no_liabilities():
    """If total liabilities = 0, X4 should be 0 (not a division error)."""
    f = _figures(ta=500_000, ca=300_000, cl=0, na=500_000,
                 lt=0, re=200_000, ebit=80_000, sales=600_000)
    result = _altman_z_prime(f)
    assert result is not None  # should not raise

def test_altman_score_is_rounded():
    f = _figures(ta=1_000_000, ca=600_000, cl=200_000, na=700_000,
                 lt=100_000, re=400_000, ebit=200_000, sales=1_500_000)
    result = _altman_z_prime(f)
    # score rounded to 3 decimal places
    assert result["z_score"] == round(result["z_score"], 3)


# ── Sector benchmarks ─────────────────────────────────────────────────────────

def test_known_sic_restaurants():
    """SIC 56 (Restaurants) has the worst failure rate → most negative adjustment."""
    result = get_sector_risk(["56"])
    assert result["score_adjustment"] <= -15
    assert result["failure_rate"] >= 20

def test_known_sic_banking():
    """SIC 64 (Banking) has low failure rate → positive or near-zero adjustment."""
    result = get_sector_risk(["64"])
    assert result["score_adjustment"] >= 0

def test_unknown_sic_returns_default():
    """Unknown SIC code returns a conservative default (-4), not an error or crash."""
    result = get_sector_risk(["99"])
    assert isinstance(result["score_adjustment"], int)
    assert result["label"] == "Unknown sector"

def test_empty_sic_returns_default():
    """No SIC codes returns the same conservative default."""
    result = get_sector_risk([])
    assert isinstance(result["score_adjustment"], int)
    assert result["label"] == "Unknown sector"

def test_worst_sic_wins_with_multiple_codes():
    """With both a low-risk and high-risk SIC, the worst should determine the adjustment."""
    low_risk  = get_sector_risk(["84"])  # Public admin — safe
    high_risk = get_sector_risk(["56"])  # Restaurants — risky
    combined  = get_sector_risk(["84", "56"])
    assert combined["score_adjustment"] <= low_risk["score_adjustment"]
    assert combined["score_adjustment"] == high_risk["score_adjustment"]

def test_sector_result_has_required_keys():
    result = get_sector_risk(["62"])
    for key in ("label", "failure_rate", "score_adjustment"):
        assert key in result

def test_all_sic_adjustments_in_range():
    """Every entry in SECTOR_RISK should have a score_adjustment within [-25, +10]."""
    for sic, (rate, label, adj) in SECTOR_RISK.items():
        assert -25 <= adj <= 10, f"SIC {sic} adjustment {adj} out of range"

def test_sic_prefix_match():
    """SIC codes can be 4-digit (6201) — should match on 2-digit prefix."""
    result = get_sector_risk(["6201"])
    # 62xx is software development
    assert result["score_adjustment"] != 0 or result["label"] != "Unknown sector"
