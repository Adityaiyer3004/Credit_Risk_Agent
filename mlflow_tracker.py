"""
MLflow tracking for every credit risk analysis.

Logs each analysis as a run in the "credit-risk-agent" experiment.
Metrics and tags are chosen for quality monitoring:

Metrics  — numeric, time-series-able in MLflow UI:
  credit_score        0-100 composite score
  guardrail_passed    0-4 criteria the eval LLM passed
  report_tokens       tokens for primary LLM call
  guardrail_tokens    tokens for guardrail eval call
  total_tokens        combined
  total_cost_usd      USD spend for the pair of calls

Tags — searchable / filterable in MLflow UI:
  company_name
  company_number
  risk_level          Low Risk | Medium Risk | High Risk
  guardrail_grade     A | B | C | D | ?
  prompt_version      from prompts.yaml
  cached              true | false

Tracking URI:
  Default → file-based mlruns/ (local dev, no extra infra).
  Set MLFLOW_TRACKING_URI env var to override:
    GCS backend:    gs://your-bucket/mlflow
    Hosted server:  https://mlflow.your-domain.com
"""

import os
import logging

logger = logging.getLogger("credit_risk")

_EXPERIMENT = "credit-risk-agent"
_GRADE_TO_NUM = {"A": 4, "B": 3, "C": 2, "D": 1}


def log_analysis_run(
    *,
    company_name: str,
    company_number: str,
    risk: dict,
    guardrail: dict,
    llm_usage: dict,
    cached: bool,
    elapsed_s: float | None = None,
) -> None:
    """Fire-and-forget: log one analysis to MLflow. Swallows all errors."""
    try:
        import mlflow

        mlflow.set_experiment(_EXPERIMENT)
        grade = guardrail.get("overall_grade", "?")

        metrics: dict[str, float] = {
            "credit_score":     float(risk.get("credit_score", 0)),
            "guardrail_passed": float(guardrail.get("passed", 0)),
            "guardrail_grade_num": float(_GRADE_TO_NUM.get(grade, 0)),
            "report_tokens":    float(llm_usage.get("report", {}).get("total", 0)),
            "guardrail_tokens": float(llm_usage.get("guardrail", {}).get("total", 0)),
            "total_tokens":     float(llm_usage.get("total_tokens", 0)),
            "total_cost_usd":   float(llm_usage.get("total_cost_usd", 0.0)),
        }
        if elapsed_s is not None:
            metrics["analysis_time_s"] = float(elapsed_s)

        tags: dict[str, str] = {
            "company_name":    company_name,
            "company_number":  company_number,
            "risk_level":      risk.get("risk_level", ""),
            "guardrail_grade": grade,
            "prompt_version":  llm_usage.get("prompt_version", ""),
            "cached":          str(cached).lower(),
        }

        with mlflow.start_run():
            mlflow.log_metrics(metrics)
            mlflow.set_tags(tags)

    except Exception:
        logger.debug("MLflow logging skipped (mlflow not available or tracking URI unreachable)")
