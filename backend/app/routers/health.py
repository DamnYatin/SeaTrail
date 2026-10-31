"""
Health check endpoints for container readiness and operational liveness.
"""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.config import settings

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"


class ReadyCheckDetail(BaseModel):
    ok: bool
    message: str


class ReadyResponse(BaseModel):
    status: str
    database: ReadyCheckDetail
    storage: ReadyCheckDetail
    chain: ReadyCheckDetail


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    """Liveness probe returning 200 when Uvicorn is active."""
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=ReadyResponse)
def readyz(response: Response) -> ReadyResponse:
    """Readiness probe checking PostgreSQL connection, S3 storage, and chain head."""
    db_ok = True
    db_msg = "Database connected"
    try:
        from sqlalchemy import text

        from app.db import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_msg = f"Database error: {str(e)}"

    storage_ok = True
    storage_msg = "Storage reachable"
    try:
        from app.services.storage import get_s3_client

        s3 = get_s3_client()
        s3.head_bucket(Bucket=settings.S3_BUCKET_EVIDENCE)
    except Exception as e:
        storage_ok = False
        storage_msg = f"Storage error: {str(e)}"

    chain_ok = True
    chain_msg = "Chain intact"
    try:
        from app.db import get_db_session
        from app.models.integrity import IntegrityState

        with get_db_session() as session:
            state = session.query(IntegrityState).first()
            if state and not state.chain_ok:
                chain_ok = False
                chain_msg = f"Chain broken at seq {state.broken_seq}: {state.broken_reason}"
    except Exception as e:
        # Before tables are migrated, degrade gracefully
        chain_msg = f"Chain state uninitialized: {str(e)}"

    all_ready = db_ok and storage_ok and chain_ok
    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadyResponse(
        status="ready" if all_ready else "degraded",
        database=ReadyCheckDetail(ok=db_ok, message=db_msg),
        storage=ReadyCheckDetail(ok=storage_ok, message=storage_msg),
        chain=ReadyCheckDetail(ok=chain_ok, message=chain_msg),
    )
