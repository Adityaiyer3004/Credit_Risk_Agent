#!/bin/bash
# Production server — 4 workers, access log, structured errors
exec uvicorn main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 4 \
  --access-log \
  --log-level info
