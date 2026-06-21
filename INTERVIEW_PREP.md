# Credit Risk Intelligence — Interview Preparation

Everything built in this project, explained at the depth an interviewer would probe.

---

## 1. Project summary (30-second pitch)

> "I built a production AI system that takes a UK company number and returns a full institutional-grade credit risk assessment in under 10 seconds. It pulls live data from five public APIs in parallel — Companies House, GLEIF, The Gazette, Tavily news, and filed iXBRL accounts — runs a 15-factor scoring engine, generates a structured credit report using Llama 3.3 70B, and validates that report with a second LLM acting as a guardrail judge. The whole system is deployed on Google Cloud Run with Redis caching, CI/CD, monitoring, and a full LLMOps stack including prompt versioning, token/cost tracking, MLflow quality monitoring, and a user feedback loop."

---

## 2. System design

### Why FastAPI over Flask or Django?
- Async-native — critical for parallel external API calls in Phase 1
- Pydantic validation built in — request bodies are typed and validated automatically
- OpenAPI docs generated automatically — useful for the `/api/analyze` endpoint
- `slowapi` integrates cleanly for rate limiting

### Why two LLM calls (reporter + guardrail)?
Single-model self-evaluation has a well-documented failure mode: the model that generated an answer tends to agree with itself when asked to evaluate it. Using a second, smaller model as judge avoids this. Llama 3.1 8B is fast and cheap (~£0.00005 per evaluation), so adding it costs less than a penny per thousand analyses.

### Why is Phase 1 parallel but Phase 2 sequential?
- Phase 1 (5 external APIs): independent fetches, no data dependency between them. ThreadPoolExecutor gives ~4× speedup vs sequential.
- Phase 2 (report → guardrail): the guardrail evaluator needs the full report text as input. Can't parallelise a dependency chain.

### Caching design
- Redis (Memorystore) with 1-hour TTL
- Key: normalised company number
- Why Redis over in-memory: Cloud Run scales horizontally — each instance has its own memory. A shared Redis store means a cache hit on instance B for data fetched by instance A. Without it, the cache hit rate approaches zero under load.
- `?refresh=true` query parameter bypasses cache for fresh data

### Why Memorystore (managed Redis) instead of self-hosted?
- Automatic failover and replication
- Private IP only — not exposed to the internet
- Requires a VPC connector for Cloud Run to reach a private IP, which was explicitly configured (`credit-risk-connector`, range `10.8.0.0/28`)

---

## 3. Risk scoring engine

### Design philosophy
Rule-based rather than ML model for three reasons:
1. **Interpretability** — every score driver is a human-readable string returned in `reasons[]`. A bank needs to explain a credit decision; a black-box model can't.
2. **Auditability** — the scoring logic is in `risk_engine.py`, version-controlled, testable with 32 unit tests
3. **Data sparsity** — UK SMEs often have minimal filed data. A trained classifier would constantly hit sparse feature vectors.

### The 15 factors
```
Company status:     dissolved → -40
Filing compliance:  accounts > 2yr stale → -10; 4+ late → -5; 5+ paper → -3
Company age:        < 2yr → -20; 2-5yr → -8
Directors:          none active → -20
Charges:            outstanding → -10
Insolvency:         formal record → -25
Gazette:            winding-up notices → -15
Director network:   5+ dissolved associations → -8; 30%+ career → -5
Balance sheet:      negative net assets → -15; current ratio <0.8 → -10
Altman Z':          distress zone (<1.23) → -12; grey zone → -5
Sector:             high-risk SIC → -2; low-risk → +3
```

### Altman Z' Score
Modified Z' for private firms (Altman 1993):
```
Z' = 0.717×X1 + 0.847×X2 + 3.107×X3 + 0.420×X4 + 0.998×X5
X1 = Working Capital / Total Assets
X2 = Retained Earnings / Total Assets
X3 = EBIT / Total Assets
X4 = Book Value of Equity / Total Liabilities
X5 = Revenue / Total Assets

Z' < 1.23  → Distress Zone
1.23–2.9   → Grey Zone
> 2.9      → Safe Zone
```
Extracted from iXBRL-tagged filed accounts. Only available when a company files structured digital accounts (not all do).

---

## 4. LLM architecture

### Model selection rationale
| Model | Role | Why |
|---|---|---|
| `llama-3.3-70b-versatile` | Report generation | Best instruction-following in Groq's fleet; temperature 0.15 for consistent structure |
| `llama-3.1-8b-instant` | Guardrail judge | Fast, cheap, temperature 0 for deterministic JSON output |

Both served via Groq's inference API — sub-second latency compared to OpenAI's ~3–5s for 70B class models. Critical for a system promising results in under 10 seconds.

### Prompt engineering
System prompt for the reporter is ~400 tokens covering:
- Role framing (senior credit analyst, Tier 1 bank, 20 years experience)
- Output format requirements (exactly 5 named sections)
- Tone guidelines per risk band
- Guardrails against catastrophising or dismissing genuine signals

The guardrail system prompt specifies:
- Return ONLY valid JSON — no markdown, no commentary
- Exactly 4 boolean criteria + flags array
- Explicit definitions for each criterion to reduce ambiguity

### Why prompts.yaml instead of hardcoded strings?
```
prompts.yaml
  version: "1.1"
  report:
    model: llama-3.3-70b-versatile
    temperature: 0.15
    system: |
      You are a senior credit risk analyst...
  guardrail:
    model: llama-3.1-8b-instant
    temperature: 0
    system: |
      You are a report quality auditor...
```

Three benefits:
1. **Versioning** — bump `version:` on any prompt change. Git diff shows exactly what changed between v1.0 and v1.1.
2. **Single source of truth** — model name, temperature, max_tokens, cost rates all in one file. Change the model in one place.
3. **MLflow tagging** — `prompt_version` logged as a tag on every MLflow run, so you can filter "show me all grade-D reports on prompt v1.0 vs v1.1" and measure improvement.

### Token tracking implementation
```python
def _extract_tokens(resp) -> dict:
    meta = getattr(resp, "usage_metadata", None) or {}
    fallback = getattr(resp, "response_metadata", {}).get("token_usage", {})
    inp = meta.get("input_tokens") or fallback.get("prompt_tokens", 0)
    out = meta.get("output_tokens") or fallback.get("completion_tokens", 0)
    ...
```
Dual-path fallback: `usage_metadata` is the standard LangChain interface; `response_metadata.token_usage` is the older Groq-specific path. Both checked for resilience across LangChain versions.

---

## 5. LLMOps lifecycle

LLMOps = MLOps applied to systems where the "model" is a prompt + LLM call. Four gaps were identified and closed:

### Gap 1: Prompt versioning
**Problem:** System prompts were hardcoded strings in Python files. No way to know what prompt generated a given report.
**Solution:** `prompts.yaml` — prompts, model config, and cost rates in one file. `prompt_version` returned in every API response and logged to MLflow.

### Gap 2: Cost/token tracking
**Problem:** No visibility into LLM spend per request.
**Solution:** Every `ChatGroq.invoke()` call extracts token counts and calculates USD cost. `llm_usage` dict in every API response:
```json
{
  "report":   { "input": 1240, "output": 459, "total": 1699, "cost_usd": 0.001094 },
  "guardrail":{ "input": 846,  "output": 144, "total": 990,  "cost_usd": 0.000054 },
  "total_cost_usd": 0.001148
}
```
Each analysis costs ~$0.001. 10,000 analyses/month ≈ $10.

### Gap 3: Output quality monitoring
**Problem:** No systematic tracking of whether report quality degrades after prompt changes.
**Solution:** MLflow experiment `credit-risk-agent`. Every analysis logs:
- Metrics: `credit_score`, `guardrail_passed` (0–4), `guardrail_grade_num` (A=4, B=3, C=2, D=1), `total_tokens`, `total_cost_usd`
- Tags: `company_name`, `risk_level`, `guardrail_grade`, `prompt_version`

With this you can: filter by `prompt_version=1.1` vs `1.0`, compare guardrail pass rates, detect cost regressions after model changes.

### Gap 4: Feedback loop
**Problem:** No signal from actual users on report quality.
**Solution:** `POST /api/feedback` — thumbs up/down stored in `feedback.log`, `GET /api/feedback/stats` returns satisfaction rate. Frontend shows thumbs buttons after every result.

This closes the loop: model generates → guardrail evaluates → user rates → data informs next prompt revision.

---

## 6. Cloud architecture

### Cloud Run
- Serverless containers — scales to zero when idle, scales out under load
- `--max-instances=5` to cap cost
- Region: `europe-west2` (London) — GDPR-aligned, latency-optimal for UK data sources
- Secrets mounted via Secret Manager at runtime (not baked into the image)

### CI/CD — Cloud Build
`cloudbuild.yaml` defines 4 steps triggered on every push to `main`:
```yaml
1. test   → pip install + pytest (82 tests must pass)
2. build  → docker build
3. push   → push to Artifact Registry
4. deploy → gcloud run deploy with VPC connector + secrets
```
Build only reaches deploy if tests pass. Zero-downtime deployment — Cloud Run does blue/green automatically.

### Secret Manager
5 secrets: `COMPANIES_HOUSE_API_KEY`, `GROQ_API_KEY`, `TAVILY_API_KEY`, `CREDIT_RISK_API_KEY`, `REDIS_URL`.
Mounted as environment variables at Cloud Run startup. The Compute Engine service account has `roles/secretmanager.secretAccessor`.

### VPC Connector
Redis (Memorystore) runs on a private VPC IP — not accessible from the public internet. Cloud Run is serverless and doesn't live in the VPC by default. A Serverless VPC Access Connector (`credit-risk-connector`, range `10.8.0.0/28`) bridges Cloud Run to the VPC so it can reach Redis at `10.129.206.43:6379`.

### Monitoring
- **Uptime check**: HTTP GET `/health` every 1 minute
- **Alert policy**: email notification if health check fails 2 consecutive times
- **Cloud Logging**: structured JSON logged to stdout in production, ingested automatically by Cloud Logging

---

## 7. Security

### API key authentication
`APIKeyHeader("X-API-Key")` checked on every protected endpoint. Dev bypass: if `CREDIT_RISK_API_KEY=""` (unset), auth is skipped — avoids test environment friction. Production always has the secret set.

### Rate limiting
`slowapi` (Redis-backed): `8/minute; 30/hour` per IP in production. `1000/minute` in test mode (`TESTING=true` env var). Rate limits prevent abuse and control LLM API cost.

### Secrets
- Never in code or Docker images
- `.env` is gitignored
- Production: Secret Manager only
- Rotation: update the secret version, redeploy

### Input validation
UK company numbers validated with a compiled regex covering all 20+ prefix formats (SC, NI, OC, LP, OE, SE...) before any API calls. Numeric-only numbers are zero-padded to 8 digits. Returns 422 before touching any backend.

---

## 8. Testing strategy

### What's tested (82 tests)
```
test_risk_engine.py       32 tests — every scoring factor, boundary values, score clamping to [1,100]
test_financials.py        17 tests — iXBRL parsing, Altman Z' zones, ratio edge cases
test_cache_and_guardrail.py 14 tests — Redis hit/miss, guardrail grade mapping, fallback behaviour
test_validation.py        19 tests — company number format, auth, rate limits, response schema
```

### What's mocked
- `generate_full_company_risk_report` — mocked in validation tests so real API calls don't run in CI
- `fetch_company_data` — mocked so Companies House API key not needed in CI
- Redis — real Redis tested in cache tests via `fakeredis`

### What's NOT mocked
- The risk engine itself — tested with constructed profile dicts, no mocking
- Financial ratio calculations — tested with real arithmetic
- Company number validation — tested with real regex against known valid/invalid numbers

### Why this split?
Unit tests for deterministic logic (risk engine, financials), integration-style tests for the API layer with mocked external dependencies. The risk engine having 32 dedicated tests reflects its criticality — a scoring bug directly affects credit decisions.

---

## 9. Data pipeline

### iXBRL accounts parsing (`accounts_analyzer.py`)
UK companies file accounts in iXBRL (inline XBRL) format. The parser:
1. Fetches the iXBRL document URL from Companies House filing history
2. Parses with `lxml` + `BeautifulSoup`
3. Extracts tagged financial values using XBRL namespace
4. Calculates current ratio, net asset ratio, gearing
5. Computes Altman Z' if sufficient fields present
6. Detects YoY trends across two periods

This is the hardest data engineering piece — iXBRL is complex, tagging is inconsistent across accounting software, and many SMEs file PDF-only accounts which can't be parsed.

### Director network analysis (`comp_house_ingestor.py`)
For each director, fetches their full appointments history from Companies House `/officers/{id}/appointments`. Calculates:
- Total appointments count
- Active vs dissolved/insolvent company associations
- `dissolved_count / total_count` ratio → "serial insolvency signal" if > 30%

This catches a specific fraud/distress pattern: directors who repeatedly appear at companies that fail.

### Gazette scraping (`gazette_winding_up.py`)
The Gazette (official UK government record) publishes winding-up petitions. Scraped via Tavily search targeting `site:thegazette.co.uk`. Returns petition date, type (compulsory / voluntary), and notice title. A winding-up notice is a severe distress signal — it means a creditor has gone to court.

---

## 10. Key decisions and trade-offs

### Groq over OpenAI
- Latency: Groq's LPU inference runs Llama 3.3 70B at ~200 tokens/s vs OpenAI's ~30 tokens/s for GPT-4
- Cost: $0.59/$0.79 per million tokens (input/output) vs ~$10/$30 for GPT-4
- Trade-off: less reliable uptime than OpenAI; no fine-tuning option; rate limits can be hit under high load

### LangChain over direct API calls
- `usage_metadata` extraction works consistently across providers
- Easy to swap models — just change `model_name` in config
- Trade-off: adds ~50ms overhead per call, larger dependency

### YAML config over environment variables for prompts
- Env vars for secrets (API keys, Redis URL) — they're deployment-specific
- YAML for model config and prompts — they're code-specific and should be in version control
- The distinction: secrets change per environment; prompts change per commit

### Rule-based scoring over ML model
- Interpretability requirement: regulators require explainable credit decisions
- No labelled dataset: would need historical credit outcomes (defaults, non-payments) to train a classifier — not publicly available for UK SMEs
- Auditability: every score driver is a string in `reasons[]`, inspectable by clients

### Append-only audit log
- JSONL, never modified after writing — each line is immutable
- In production (Cloud Run): log to stdout, Cloud Logging ingests it
- `request_id` (UUID4) in every entry enables cross-referencing with app logs and MLflow runs

---

## 11. What I'd do differently / scale-up path

| Current | At scale |
|---|---|
| Rule-based risk engine | Hybrid: rules + LightGBM trained on CH historical data |
| File-based feedback log | Firestore — queryable, real-time |
| MLflow local / GCS | Hosted MLflow on Cloud Run + Cloud SQL backend |
| Single-region Cloud Run | Multi-region with Cloud Load Balancing |
| Redis TTL cache only | Tiered: hot (Redis 1hr) + warm (GCS 24hr) + cold (BigQuery) |
| Prompt versioning in Git | LangSmith or Weights & Biases for tracked prompt experiments |
| Guardrail on every call | Guardrail on sample (e.g. 10%) to reduce cost at scale |

---

## 12. Metrics to know

| Metric | Value |
|---|---|
| End-to-end latency (fresh) | ~8–12 seconds |
| Cache hit latency | ~50ms |
| Cost per analysis | ~$0.001 (0.1p) |
| Report tokens (avg) | ~1,700 |
| Guardrail tokens (avg) | ~1,000 |
| Test coverage | 82 tests, 4 suites |
| Guardrail pass rate | ~A grade on well-formed companies |
| Redis TTL | 1 hour |
| Rate limit | 8/min, 30/hour per IP |

---

## 13. Common interview questions

**Q: How do you prevent hallucinations in the LLM report?**
Two layers. First, the prompt constrains the model to only reference data fields explicitly included in the user message — no external knowledge allowed. Second, the guardrail evaluator checks `factual_grounded` as an explicit criterion: does the report claim any fact not present in the source data? If it fails, the grade drops and the failure is flagged in the response.

**Q: How would you know if the system's credit scores are accurate?**
You'd need ground truth — actual credit outcomes (did this company default? miss payments?). That's proprietary lender data, not publicly available. The system produces _indicators_, not regulated credit scores. Accuracy validation would require a partnership with a lender who has historical outcome data and can back-test the scoring engine against it.

**Q: What happens if Groq is down?**
The LLM calls have try/except wrappers that return the error as the report string and an empty token dict. The API still returns a response with the rule-based `baseline_report` and the score — the value is degraded but not zero. The cached result (if available) would be returned instead.

**Q: How do you handle the VPC connectivity between Cloud Run and Redis?**
Cloud Run is serverless — it doesn't live in the VPC. Memorystore Redis has a private VPC IP. The Serverless VPC Access Connector acts as a bridge: it's a small managed VM cluster in a `/28` subnet (`10.8.0.0/28`) that Cloud Run routes VPC-destined traffic through. The Cloud Run deploy command includes `--vpc-connector` pointing to this connector.

**Q: Why store prompts in YAML rather than a database?**
Prompts are code, not data. They change alongside the system they drive, need review in pull requests, and should roll back atomically with the code when a deployment is reverted. A database decouples prompt versions from code versions — you get mismatches. YAML in Git means prompt version 1.1 is exactly the prompt that was live when commit `b24b34a` was deployed. Git is the audit trail.

**Q: Walk me through what happens when the rate limit is hit.**
`slowapi` tracks request counts per IP using Redis as the backend store. When a client exceeds `8/minute`, the decorator intercepts the request before it reaches the handler and returns HTTP 429. The frontend detects the 429 and shows "Rate limit reached — please wait a moment before retrying." The IP counter resets after the window expires. In testing mode (`TESTING=true`), the limit is `1000/minute` so tests don't trigger it.

**Q: How do you know the guardrail itself is reliable?**
The guardrail evaluator has 14 dedicated tests covering grade mapping, fallback on API failure, and the 4 individual criteria. Beyond tests, the guardrail uses temperature=0 which makes it deterministic for a given input — reducing variability. The MLflow `guardrail_grade` time series would reveal systematic drift if the evaluator started degrading (e.g. always returning grade A regardless of content).

**Q: What's the Altman Z' score and why include it?**
The Altman Z' score (Altman, 1993 modified for private firms) is the closest thing credit risk has to a validated bankruptcy predictor. It uses five accounting ratios extracted from filed balance sheets. `Z' < 1.23` = distress zone (historically ~75% of distress-zone companies fail within 2 years). It's more objective than the composite score because it's derived purely from audited financial statements, not from filing behaviour or director associations. When available, the LLM prompt is instructed to lead the CREDIT SCORE INTERPRETATION section with it.
