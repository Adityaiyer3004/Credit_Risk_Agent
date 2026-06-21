"""
Append-only audit log for every credit risk analysis.

Format: JSON Lines (one JSON object per line) written to AUDIT_LOG_PATH.
Each entry is immutable once written — the file is opened in append mode only.

Fields logged per analysis:
  ts             ISO-8601 UTC timestamp
  request_id     UUID4 — unique per request, for cross-referencing with app logs
  ip             client IP address
  company_number normalised CH number
  company_name   legal name from Companies House
  score          credit score (0-100)
  risk_level     Low Risk / Medium Risk / High Risk
  guardrail      overall guardrail grade (A-D or ?)
  guardrail_flags list of flagged issues from the eval LLM
  cached         whether result was served from cache
  cache_age_s    seconds since result was cached (0 if live)
  elapsed_s      wall-clock seconds for fresh analysis (null if cached)
  sic_codes      SIC codes from CH profile
  company_status active / dissolved / etc.
"""

import json
import uuid
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOG_PATH_RAW = os.getenv("AUDIT_LOG_PATH", "audit.log")
# When AUDIT_LOG_PATH=/dev/stdout (Cloud Run), write structured JSON to stdout
# so Cloud Logging picks it up automatically as a structured log entry.
_STDOUT_MODE = _LOG_PATH_RAW in ("/dev/stdout", "stdout", "-")
_LOG_PATH = None if _STDOUT_MODE else Path(_LOG_PATH_RAW)
_lock = threading.Lock()   # serialise concurrent writes from multiple workers


def log_analysis(
    *,
    ip: str,
    company_number: str,
    profile: dict,
    risk: dict,
    guardrail: dict,
    cached: bool,
    cache_age_s: int = 0,
    elapsed_s: float | None = None,
) -> str:
    """Write one audit entry. Returns the request_id for cross-referencing."""
    request_id = str(uuid.uuid4())
    entry = {
        "ts":             datetime.now(timezone.utc).isoformat(),
        "request_id":     request_id,
        "ip":             ip,
        "company_number": company_number,
        "company_name":   profile.get("company_name", ""),
        "company_status": profile.get("company_status", ""),
        "sic_codes":      profile.get("sic_codes", []),
        "score":          risk.get("credit_score"),
        "risk_level":     risk.get("risk_level", ""),
        "score_drivers":  risk.get("reasons", []),
        "guardrail":      guardrail.get("overall_grade", "?"),
        "guardrail_flags": guardrail.get("flags", []),
        "cached":         cached,
        "cache_age_s":    cache_age_s if cached else 0,
        "elapsed_s":      elapsed_s if not cached else None,
    }
    if _STDOUT_MODE:
        # Cloud Logging structured log format — severity + jsonPayload
        cloud_entry = {
            "severity": "INFO",
            "message": f"audit.analysis company={entry['company_number']} score={entry['score']} risk={entry['risk_level']}",
            "jsonPayload": entry,
        }
        line = json.dumps(cloud_entry, default=str)
        with _lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
    else:
        line = json.dumps(entry, default=str)
        with _lock:
            with _LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    return request_id


def recent_entries(n: int = 50) -> list[dict]:
    """Return the last n entries from the audit log (most recent last)."""
    if _STDOUT_MODE or not _LOG_PATH or not _LOG_PATH.exists():
        return []
    lines = []
    try:
        with _LOG_PATH.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    entries = []
    for line in lines[-n:]:
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries


def summary_stats() -> dict:
    """Aggregate stats over the full audit log."""
    if _STDOUT_MODE or not _LOG_PATH or not _LOG_PATH.exists():
        return {"total_requests": 0, "note": "audit log streamed to Cloud Logging"}
    counts: dict[str, int] = {}
    risk_counts: dict[str, int] = {}
    grade_counts: dict[str, int] = {}
    total = cached = 0
    scores = []
    try:
        with _LOG_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                total += 1
                cn = e.get("company_number", "")
                counts[cn] = counts.get(cn, 0) + 1
                if e.get("cached"):
                    cached += 1
                rl = e.get("risk_level", "unknown")
                risk_counts[rl] = risk_counts.get(rl, 0) + 1
                g = e.get("guardrail", "?")
                grade_counts[g] = grade_counts.get(g, 0) + 1
                if e.get("score") is not None:
                    scores.append(e["score"])
    except OSError:
        return {"total_requests": 0}

    top = sorted(counts.items(), key=lambda x: -x[1])[:10]
    return {
        "total_requests":    total,
        "cache_hits":        cached,
        "cache_hit_rate":    round(cached / total * 100, 1) if total else 0,
        "unique_companies":  len(counts),
        "avg_score":         round(sum(scores) / len(scores), 1) if scores else None,
        "risk_distribution": risk_counts,
        "guardrail_grades":  grade_counts,
        "top_queried":       [{"company_number": cn, "queries": n} for cn, n in top],
    }
