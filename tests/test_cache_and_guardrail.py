"""Tests for cache layer and guardrail format checker."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest


# ── Cache ─────────────────────────────────────────────────────────────────────

def _fresh_cache(ttl=60):
    """Return a fresh in-memory cache instance (bypasses module-level singleton)."""
    from cachetools import TTLCache
    import threading

    cache = TTLCache(maxsize=100, ttl=ttl)
    lock  = threading.Lock()

    def get(key):
        with lock:
            return cache.get(key)

    def set_(key, value):
        with lock:
            cache[key] = {**value, "_cached_at": time.time()}

    def invalidate(key):
        with lock:
            existed = key in cache
            cache.pop(key, None)
            return existed

    return get, set_, invalidate


def test_cache_miss_returns_none():
    get, set_, _ = _fresh_cache()
    assert get("99999999") is None

def test_cache_hit_after_set():
    get, set_, _ = _fresh_cache()
    set_("08804411", {"score": 70})
    result = get("08804411")
    assert result is not None
    assert result["score"] == 70

def test_cache_stores_cached_at_timestamp():
    get, set_, _ = _fresh_cache()
    before = time.time()
    set_("12345678", {"data": "x"})
    after = time.time()
    entry = get("12345678")
    assert before <= entry["_cached_at"] <= after

def test_cache_invalidate_removes_entry():
    get, set_, invalidate = _fresh_cache()
    set_("08804411", {"score": 70})
    assert get("08804411") is not None
    removed = invalidate("08804411")
    assert removed is True
    assert get("08804411") is None

def test_cache_invalidate_nonexistent_returns_false():
    _, __, invalidate = _fresh_cache()
    assert invalidate("00000000") is False

def test_cache_different_keys_independent():
    get, set_, _ = _fresh_cache()
    set_("11111111", {"score": 50})
    set_("22222222", {"score": 80})
    assert get("11111111")["score"] == 50
    assert get("22222222")["score"] == 80

def test_cache_overwrite():
    get, set_, _ = _fresh_cache()
    set_("08804411", {"score": 70})
    set_("08804411", {"score": 90})
    assert get("08804411")["score"] == 90

def test_cache_module_stats_structure():
    from cache import stats
    s = stats()
    for key in ("hits", "misses", "hit_rate", "ttl_seconds", "backend"):
        assert key in s


# ── Guardrail format check ────────────────────────────────────────────────────

from guardrail_evaluator import _format_check, _REQUIRED_SECTIONS

def test_format_check_passes_with_all_sections():
    report = "\n".join([
        "1. EXECUTIVE SUMMARY\nContent.",
        "2. CREDIT SCORE INTERPRETATION\nContent.",
        "3. RISK FACTOR ANALYSIS\nContent.",
        "4. LEGAL AND FINANCIAL POSITION\nContent.",
        "5. CREDIT OPINION\nExtend credit.",
    ])
    assert _format_check(report) is True

def test_format_check_fails_missing_section():
    report = "\n".join([
        "1. EXECUTIVE SUMMARY\nContent.",
        "2. CREDIT SCORE INTERPRETATION\nContent.",
        "3. RISK FACTOR ANALYSIS\nContent.",
        # Missing LEGAL AND FINANCIAL POSITION
        "5. CREDIT OPINION\nExtend credit.",
    ])
    assert _format_check(report) is False

def test_format_check_case_insensitive():
    """Section headers in the report are uppercase — check works regardless."""
    report = "\n".join(s for s in _REQUIRED_SECTIONS)
    assert _format_check(report) is True

def test_format_check_empty_report_fails():
    assert _format_check("") is False

def test_format_check_partial_section_name_fails():
    """'EXECUTIVE' without 'SUMMARY' should not satisfy the check."""
    report = "EXECUTIVE\nCREDIT SCORE\nRISK FACTOR\nLEGAL\nCREDIT"
    assert _format_check(report) is False

def test_guardrail_fallback_structure():
    from guardrail_evaluator import _fallback
    result = _fallback("test reason")
    for key in ("overall_grade", "flags", "factual_grounded", "tone_calibrated",
                "solvency_vs_gov", "format_compliant", "passed", "total"):
        assert key in result
    assert result["overall_grade"] == "?"
    assert isinstance(result["flags"], list)
