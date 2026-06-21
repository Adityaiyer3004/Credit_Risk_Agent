# Credit Risk Intelligence

Real-time UK company credit assessment — Companies House + GLEIF + Gazette + AI, deployed on Google Cloud Run.

---

## What it does

Enter a UK Companies House number. In under 10 seconds the system:

1. Fetches live data from five public sources in parallel
2. Scores the company 1–100 across 15+ risk factors
3. Generates an institutional-grade credit report using Llama 3.3 70B
4. Evaluates the report with an LLM-as-judge guardrail (Llama 3.1 8B)
5. Returns everything — score, report, guardrail grade, cost, tokens — in a single JSON response
6. Logs every analysis to MLflow for output quality monitoring

---

## Architecture

```
Browser / API client
        │
        ▼
 FastAPI (Cloud Run)
        │
        ├── Redis (Memorystore)     ← cache, TTL 1h
        │
        ├── Phase 1: parallel data fetch
        │      ├── Companies House API     company profile, officers, filings, charges, insolvency
        │      ├── Tavily Search           recent news (5 articles)
        │      ├── The Gazette             winding-up petitions
        │      ├── GLEIF / OpenCorporates  LEI verification
        │      └── iXBRL accounts parser  filed financial statements → ratios + Altman Z'
        │
        ├── Risk Engine                   15-factor score → 1–100, risk_level, reasons[]
        │
        ├── Phase 2: sequential LLM calls
        │      ├── Groq llama-3.3-70b-versatile   5-section credit report
        │      └── Groq llama-3.1-8b-instant       LLM-as-judge guardrail evaluation
        │
        ├── MLflow Tracker               metrics + tags logged per run
        └── Audit Logger                 JSONL / Cloud Logging (prod)
```

---

## Data sources

| Source | What it provides |
|---|---|
| Companies House API | Company profile, directors, filing history, charges, insolvency, PSC |
| Companies House iXBRL | Filed accounts → balance sheet, P&L, cash, ratios, Altman Z' score |
| The Gazette | Winding-up petitions and compulsory strike-off notices |
| GLEIF / OpenCorporates | LEI status (issued / lapsed / not found) |
| Tavily Search | Recent news articles with negative signal detection |

---

## Risk scoring model

15 factors across 8 categories. Each company starts at 70 and adjusts:

| Factor | Adjustment |
|---|---|
| Dissolved / liquidated | −40 |
| No accounts ever filed | −15 |
| Accounts > 2 years stale | −10 |
| 4+ significantly late filings | −5 |
| 5+ paper filings (governance signal) | −3 |
| Company age < 2 years | −20 |
| Company age < 5 years | −8 |
| No active directors | −20 |
| Outstanding registered charges | −10 |
| Formal insolvency record | −25 |
| Gazette winding-up notices | −15 |
| Director with 5+ dissolved company associations | −8 |
| 30%+ career appointments ended in dissolution | −5 |
| Negative net assets (from filed accounts) | −15 |
| Current ratio < 0.8 (liquidity stress) | −10 |
| Altman Z' < 1.23 (distress zone) | −12 |
| High-risk SIC sector | −2 |
| Low-risk SIC sector | +3 |

Score → **Low Risk** (≥68) · **Medium Risk** (45–67) · **High Risk** (<45)

---

## LLM pipeline

### Report generation — `llm_reporter.py`
- Model: `llama-3.3-70b-versatile` (via Groq)
- Temperature: 0.15, max_tokens: 1200
- Prompt: 5-section structure (Executive Summary → Credit Opinion)
- Input context: ~1,200 tokens including financials, news, director network, Gazette notices
- Output: ~450 tokens of structured narrative

### Guardrail evaluation — `guardrail_evaluator.py`
- Model: `llama-3.1-8b-instant` (fast, cheap judge)
- Temperature: 0, max_tokens: 400
- 4 criteria evaluated per report:
  1. **Factual grounding** — no hallucinated claims
  2. **Tone calibration** — matches numerical risk level
  3. **Solvency vs governance** — correctly separates financial and compliance risk
  4. **Format compliance** — all 5 required sections present
- Grade: A (4/4) → D (0–1/4)

### Prompt versioning — `prompts.yaml`
All system prompts, model names, temperatures, and cost rates live in one YAML file versioned in Git. Bump the `version:` field when prompts change — Git history gives full diff of every prompt evolution.

---

## LLMOps features

| Capability | Implementation |
|---|---|
| Prompt versioning | `prompts.yaml` — model config + system prompts in Git |
| Token tracking | `usage_metadata` extracted from every LLM response |
| Cost tracking | USD cost calculated per call using `cost_per_1m_*` rates from config |
| Output quality monitoring | MLflow — `credit_score`, `guardrail_passed`, `guardrail_grade_num`, `total_cost_usd` logged per run |
| LLM-as-judge evaluation | 4-criterion guardrail eval on every report before returning to client |
| Feedback loop | `POST /api/feedback` — thumbs up/down stored in `feedback.log`, stats at `/api/feedback/stats` |
| Audit logging | Append-only JSONL (local) / structured Cloud Logging (prod) |

---

## API endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/analyze?company_number=` | Required | Full analysis |
| `GET` | `/api/analyze?company_number=&refresh=true` | Required | Bypass cache |
| `POST` | `/api/feedback` | No | Submit thumbs up/down |
| `GET` | `/api/feedback/stats` | Required | Satisfaction rate |
| `DELETE` | `/api/cache/{company_number}` | Required | Invalidate cache entry |
| `GET` | `/api/cache/stats` | Required | Cache hit/miss stats |
| `GET` | `/api/audit/recent?n=50` | Required | Recent audit log entries |
| `GET` | `/api/audit/stats` | Required | Aggregate audit stats |
| `GET` | `/health` | No | Health check |

Auth: `X-API-Key` header. Key configured via `CREDIT_RISK_API_KEY` secret.

Rate limits: `8/minute; 30/hour` per IP in production.

---

## Response shape

```json
{
  "company_number": "04204028",
  "company_name": "REVOLUT LTD",
  "profile": { ... },
  "risk": {
    "credit_score": 62,
    "risk_level": "Medium Risk",
    "reasons": ["Last accounts older than 2 years", ...]
  },
  "baseline_report": "...",
  "llm_report": "1. EXECUTIVE SUMMARY\n...",
  "guardrail": {
    "overall_grade": "A",
    "passed": 4,
    "total": 4,
    "factual_grounded": true,
    "tone_calibrated": true,
    "solvency_vs_gov": true,
    "format_compliant": true,
    "flags": []
  },
  "llm_usage": {
    "report":   { "model": "llama-3.3-70b-versatile", "input": 1240, "output": 459, "total": 1699, "cost_usd": 0.001094 },
    "guardrail":{ "model": "llama-3.1-8b-instant",    "input": 846,  "output": 144, "total": 990,  "cost_usd": 0.000054 },
    "total_tokens": 2689,
    "total_cost_usd": 0.001148,
    "prompt_version": "1.1"
  },
  "cached": false,
  "analysis_time_seconds": 8.8,
  "request_id": "14893664-9932-487a-afbb-3e8f8a0164ba"
}
```

---

## Infrastructure (GCP)

| Component | Service |
|---|---|
| App runtime | Cloud Run (europe-west2) |
| Container registry | Artifact Registry |
| CI/CD | Cloud Build (triggered on push to `main`) |
| Redis cache | Memorystore for Redis (private IP, 1 GB) |
| VPC networking | Serverless VPC Access Connector |
| Secrets | Secret Manager (5 secrets) |
| Monitoring | Cloud Monitoring — uptime check + email alert policy |
| Logs | Cloud Logging (structured JSON via stdout) |
| MLflow | Local `mlruns/` (dev) · set `MLFLOW_TRACKING_URI=gs://...` for prod |

---

## Local setup

```bash
git clone https://github.com/Adityaiyer3004/Credit_Risk_Agent
cd Credit_Risk_Agent
pip install -r requirements.txt
```

Create `.env`:
```
COMPANIES_HOUSE_API_KEY=your_key
GROQ_API_KEY=your_key
TAVILY_API_KEY=your_key
CREDIT_RISK_API_KEY=your_chosen_key
REDIS_URL=redis://localhost:6379
```

Run:
```bash
uvicorn main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

Run tests:
```bash
pytest tests/ -v   # 82 tests
```

MLflow UI (after at least one analysis):
```bash
mlflow ui --port 5001   # port 5000 is taken by macOS AirPlay
```

---

## Test coverage

82 tests across 4 suites:

| Suite | What it covers |
|---|---|
| `test_risk_engine.py` | All 15 scoring factors, boundary conditions, score clamping |
| `test_financials.py` | iXBRL parsing, Altman Z' calculation, ratio computation |
| `test_cache_and_guardrail.py` | Redis cache TTL, guardrail grading A–D, LLM-as-judge |
| `test_validation.py` | Company number validation (UK prefixes), auth, rate limiting, response schema |

---

## Try it

```bash
# Revolut Ltd
curl "http://localhost:8000/api/analyze?company_number=04204028" \
  -H "X-API-Key: your_key"

# Tesco PLC
curl "http://localhost:8000/api/analyze?company_number=00445790" \
  -H "X-API-Key: your_key"

# Dissolved company (score: 1/100)
curl "http://localhost:8000/api/analyze?company_number=00000006" \
  -H "X-API-Key: your_key"
```
