FROM python:3.12-slim

# Install OS-level deps needed by lxml / requests
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy deps first — Docker caches this layer unless requirements change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run as non-root (security best practice for Cloud Run)
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app
USER appuser

# Cloud Run injects $PORT; fall back to 8000 for local docker run
ENV PORT=8000

EXPOSE $PORT

# Health check — Cloud Run uses this to confirm the container is ready
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

CMD uvicorn main:app \
    --host 0.0.0.0 \
    --port ${PORT} \
    --workers 1 \
    --access-log \
    --log-level info
