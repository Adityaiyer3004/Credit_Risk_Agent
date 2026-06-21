import os
import re
import time
import json
import threading
import logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Query, Request, HTTPException, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from comp_house_ingestor import fetch_company_data
from orchestrator import generate_full_company_risk_report
from cache import get as cache_get, set as cache_set, invalidate as cache_invalidate, stats as cache_stats
from audit_logger import log_analysis, recent_entries, summary_stats
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("credit_risk")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── UK company number validation ──────────────────────────────────────────────
_CH_NUMBER_RE = re.compile(
    r"^(SC|NI|OC|LP|OE|SE|SF|SG|SL|SO|SP|NL|R|IP|IC|FC|GE|GS|GN|NP|NV|NR|NO)?\d{6,8}$",
    re.IGNORECASE,
)

def _validate_company_number(raw: str) -> str:
    cn = raw.strip().upper()
    if cn.isdigit():
        if len(cn) < 6:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid UK company number: '{raw}'. Must be at least 6 digits.",
            )
        cn = cn.zfill(8)
    if not _CH_NUMBER_RE.match(cn):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid UK company number: '{raw}'. Expected 8 digits or prefix (SC/NI/OC…) + 6 digits.",
        )
    return cn


# ── API key auth ──────────────────────────────────────────────────────────────
_API_KEY       = os.getenv("CREDIT_RISK_API_KEY", "")
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def _require_api_key(key: str = Depends(_api_key_header)):
    if not _API_KEY:
        return  # dev mode — no key configured
    if key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header.")


limiter = Limiter(key_func=get_remote_address)
router  = APIRouter(prefix="/api", tags=["Analyze"])

_FB_PATH = Path(os.getenv("FEEDBACK_LOG_PATH", "feedback.log"))
_fb_lock = threading.Lock()

class FeedbackPayload(BaseModel):
    request_id: str
    rating: int        # 1 = thumbs up, -1 = thumbs down
    comment: str = ""


# ── Main analysis endpoint ────────────────────────────────────────────────────
_RATE_LIMIT = "1000/minute" if os.getenv("TESTING") else "8/minute;30/hour"

@router.get("/analyze")
@limiter.limit(_RATE_LIMIT)
def analyze_company(
    request: Request,
    company_number: str = Query(..., description="UK Companies House number"),
    refresh: bool = Query(False, description="Force bypass cache"),
    _auth: None = Depends(_require_api_key),
):
    cn = _validate_company_number(company_number)
    logger.info("ANALYSE | ip=%s company=%s refresh=%s", request.client.host, cn, refresh)

    # ── Cache lookup ──────────────────────────────────────────────────────────
    if not refresh:
        cached = cache_get(cn)
        if cached:
            age = int(time.time() - cached.pop("_cached_at", time.time()))
            payload = {**cached, "cached": True, "cache_age_seconds": age}
            log_analysis(
                ip=request.client.host,
                company_number=cn,
                profile=cached.get("profile", {}),
                risk=cached.get("risk", {}),
                guardrail=cached.get("guardrail", {}),
                cached=True,
                cache_age_s=age,
            )
            return payload

    # ── Fresh analysis ────────────────────────────────────────────────────────
    t0 = time.time()
    try:
        profile = fetch_company_data(cn)
        if not profile or not isinstance(profile, dict):
            raise HTTPException(status_code=404, detail=f"No data found for company {cn}")
        if "error" in profile:
            raise HTTPException(status_code=404, detail=profile.get("message", profile["error"]))

        result = generate_full_company_risk_report(profile)

        elapsed = round(time.time() - t0, 1)
        logger.info(
            "ANALYSE OK | company=%s score=%s risk=%s grade=%s elapsed=%ss",
            profile.get("company_name", cn),
            result["risk"].get("credit_score"),
            result["risk"].get("risk_level"),
            result.get("guardrail", {}).get("overall_grade", "?"),
            elapsed,
        )

        payload = {
            "company_number":        cn,
            "company_name":          profile.get("company_name"),
            "profile":               profile,
            "risk":                  result["risk"],
            "baseline_report":       result["baseline_report"],
            "llm_report":            result["llm_report"],
            "guardrail":             result["guardrail"],
            "llm_usage":             result.get("llm_usage", {}),
            "cached":                False,
            "cache_age_seconds":     0,
            "analysis_time_seconds": elapsed,
        }
        cache_set(cn, payload)

        request_id = log_analysis(
            ip=request.client.host,
            company_number=cn,
            profile=profile,
            risk=result["risk"],
            guardrail=result["guardrail"],
            cached=False,
            elapsed_s=elapsed,
            llm_usage=result.get("llm_usage"),
        )
        payload["request_id"] = request_id
        return payload

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ANALYSE ERROR | company=%s", cn)
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ── Cache management endpoints ────────────────────────────────────────────────
@router.delete("/cache/{company_number}")
def invalidate_cache(
    company_number: str,
    _auth: None = Depends(_require_api_key),
):
    """Force-expire a cached result so the next request fetches fresh data."""
    cn = _validate_company_number(company_number)
    removed = cache_invalidate(cn)
    return {"company_number": cn, "invalidated": removed}


@router.get("/cache/stats")
def get_cache_stats(_auth: None = Depends(_require_api_key)):
    """Cache hit/miss statistics."""
    return cache_stats()


# ── Audit log endpoints ───────────────────────────────────────────────────────
@router.get("/audit/recent")
def get_audit_recent(
    n: int = Query(50, ge=1, le=500, description="Number of recent entries to return"),
    _auth: None = Depends(_require_api_key),
):
    """Return the n most recent audit log entries."""
    return {"entries": recent_entries(n), "count": n}


@router.get("/audit/stats")
def get_audit_stats(_auth: None = Depends(_require_api_key)):
    """Aggregate statistics over the full audit log."""
    return summary_stats()


# ── Feedback endpoints ────────────────────────────────────────────────────────
@router.post("/feedback")
def submit_feedback(payload: FeedbackPayload, request: Request):
    """Record a thumbs up/down rating for an analysis."""
    if payload.rating not in (1, -1):
        raise HTTPException(status_code=422, detail="rating must be 1 or -1")
    entry = {
        "ts":         datetime.now(timezone.utc).isoformat(),
        "request_id": payload.request_id,
        "rating":     payload.rating,
        "comment":    payload.comment.strip()[:500],
        "ip":         request.client.host,
    }
    line = json.dumps(entry) + "\n"
    with _fb_lock:
        with _FB_PATH.open("a", encoding="utf-8") as f:
            f.write(line)
    logger.info("FEEDBACK | request_id=%s rating=%s", payload.request_id, payload.rating)
    return {"ok": True}


@router.get("/feedback/stats")
def get_feedback_stats(_auth: None = Depends(_require_api_key)):
    """Aggregate feedback stats."""
    if not _FB_PATH.exists():
        return {"total": 0, "thumbs_up": 0, "thumbs_down": 0, "satisfaction_pct": None}
    up = down = 0
    try:
        with _FB_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    if e.get("rating") == 1:
                        up += 1
                    elif e.get("rating") == -1:
                        down += 1
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    total = up + down
    return {
        "total":            total,
        "thumbs_up":        up,
        "thumbs_down":      down,
        "satisfaction_pct": round(up / total * 100, 1) if total else None,
    }
