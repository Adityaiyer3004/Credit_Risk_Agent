"""
Cache layer for company analysis results.

Backend selection (in priority order):
  1. Redis  — if REDIS_URL is set and the server is reachable
  2. In-process TTLCache — fallback for dev / environments without Redis

The public interface (get / set / invalidate / stats) is identical for both
backends. Swapping is automatic at startup — no changes needed in callers.

Environment variables:
  REDIS_URL          redis://localhost:6379/0   (or rediss:// for TLS)
  CACHE_TTL_SECONDS  3600   (1 hour default)
  CACHE_MAX_SIZE     500    (in-memory fallback only)
"""

import json
import os
import time
import threading
import logging
from cachetools import TTLCache

logger = logging.getLogger("credit_risk.cache")

_TTL        = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
_MAX_SIZE   = int(os.getenv("CACHE_MAX_SIZE",    "500"))
_REDIS_URL  = os.getenv("REDIS_URL", "")
_KEY_PREFIX = "cr:"   # short namespace prefix for all Redis keys

_hits   = 0
_misses = 0
_lock   = threading.Lock()   # only used for in-memory fallback + counters


# ── Backend init ──────────────────────────────────────────────────────────────

_redis: "redis.Redis | None" = None   # type: ignore[name-defined]

if _REDIS_URL:
    try:
        import redis as _redis_lib
        _redis = _redis_lib.from_url(
            _REDIS_URL,
            decode_responses=True,      # always get str back, not bytes
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        _redis.ping()
        logger.info("Cache backend: Redis  url=%s  ttl=%ds", _REDIS_URL, _TTL)
    except Exception as exc:
        logger.warning("Cache: Redis unavailable (%s) — falling back to in-memory TTLCache", exc)
        _redis = None

_mem: TTLCache | None = None
if _redis is None:
    _mem = TTLCache(maxsize=_MAX_SIZE, ttl=_TTL)
    logger.info("Cache backend: in-memory TTLCache  ttl=%ds  maxsize=%d", _TTL, _MAX_SIZE)


# ── Public interface ──────────────────────────────────────────────────────────

def get(key: str) -> dict | None:
    global _hits, _misses
    entry = _redis_get(key) if _redis else _mem_get(key)
    with _lock:
        if entry is not None:
            _hits += 1
            age = int(time.time() - entry.get("_cached_at", time.time()))
            logger.info("CACHE HIT  | key=%s  age=%ds", key, age)
        else:
            _misses += 1
            logger.info("CACHE MISS | key=%s", key)
    return entry


def set(key: str, value: dict) -> None:
    payload = {**value, "_cached_at": time.time()}
    if _redis:
        _redis_set(key, payload)
    else:
        _mem_set(key, payload)
    logger.info("CACHE SET  | key=%s  ttl=%ds", key, _TTL)


def invalidate(key: str) -> bool:
    existed = _redis_del(key) if _redis else _mem_del(key)
    if existed:
        logger.info("CACHE DEL  | key=%s", key)
    return existed


def stats() -> dict:
    with _lock:
        total = _hits + _misses
        hit_rate = round(_hits / total * 100, 1) if total else 0.0
        base = {"hits": _hits, "misses": _misses, "hit_rate": hit_rate, "ttl_seconds": _TTL}

    if _redis:
        try:
            info    = _redis.info("memory")
            keyspace = _redis.info("keyspace")
            entries = 0
            for db_info in keyspace.values():
                entries += db_info.get("keys", 0)
            return {
                **base,
                "backend":        "redis",
                "redis_url":      _REDIS_URL,
                "entries":        entries,
                "used_memory_mb": round(info.get("used_memory", 0) / 1_048_576, 2),
            }
        except Exception as exc:
            return {**base, "backend": "redis", "error": str(exc)}
    else:
        with _lock:
            size = len(_mem)
        return {**base, "backend": "memory", "entries": size, "max_size": _MAX_SIZE}


# ── Redis helpers ─────────────────────────────────────────────────────────────

def _rkey(key: str) -> str:
    return f"{_KEY_PREFIX}{key}"


def _redis_get(key: str) -> dict | None:
    try:
        raw = _redis.get(_rkey(key))
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("Redis GET error: %s", exc)
        return None


def _redis_set(key: str, value: dict) -> None:
    try:
        _redis.setex(_rkey(key), _TTL, json.dumps(value, default=str))
    except Exception as exc:
        logger.warning("Redis SET error: %s", exc)


def _redis_del(key: str) -> bool:
    try:
        return bool(_redis.delete(_rkey(key)))
    except Exception as exc:
        logger.warning("Redis DEL error: %s", exc)
        return False


# ── In-memory helpers ─────────────────────────────────────────────────────────

def _mem_get(key: str) -> dict | None:
    with _lock:
        return _mem.get(key)


def _mem_set(key: str, value: dict) -> None:
    with _lock:
        _mem[key] = value


def _mem_del(key: str) -> bool:
    with _lock:
        existed = key in _mem
        _mem.pop(key, None)
        return existed
