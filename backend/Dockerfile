FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

# Security hardening: run as non-root user
RUN useradd -m -u 1000 sealtrail && \
    chown -R sealtrail:sealtrail /app

USER sealtrail

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
