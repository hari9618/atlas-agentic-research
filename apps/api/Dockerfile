# Atlas API image — Python 3.11 slim, installed as an editable package.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build tooling needed by some scientific wheels (sentence-transformers deps).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest first for better layer caching, then install.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

# Now copy the application source.
COPY . .

EXPOSE 8000

CMD ["uvicorn", "atlas.main:app", "--host", "0.0.0.0", "--port", "8000"]
