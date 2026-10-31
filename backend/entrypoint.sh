#!/bin/sh
set -e

echo "Applying database migrations as owner..."
DATABASE_URL="${DATABASE_URL_OWNER}" alembic upgrade head

if [ "${SEED_ON_START}" = "true" ]; then
    echo "Running synthetic database seeder..."
    python scripts/seed.py || echo "Seeder skipped or already initialized."
fi

echo "Starting SealTrail API server with 1 worker..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
