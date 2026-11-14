# Atlas API image — Python 3.11 slim, runs as a non-root user.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # uvicorn worker processes per container. Each holds its own models in memory,
    # so scale replicas (behind the load balancer) before raising this.
    WEB_CONCURRENCY=1

WORKDIR /app

# Build tooling needed by some scientific wheels (sentence-transformers deps).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest first for better layer caching, then install.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

# Now copy the application source.
COPY . .

# Least privilege: a compromised process can't modify the image or the system.
RUN useradd --create-home --uid 10001 atlas && chown -R atlas /app
USER atlas

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# --proxy-headers: trust X-Forwarded-For from the load balancer so per-IP limits and
# audit logs see the real client. --timeout-graceful-shutdown: on a deploy, give
# in-flight streams time to finish (paused runs are checkpointed regardless).
CMD ["sh", "-c", "exec uvicorn atlas.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips='*' --timeout-graceful-shutdown 30"]
