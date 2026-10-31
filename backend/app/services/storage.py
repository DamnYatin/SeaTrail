"""
S3-compatible object storage client wrapper (MinIO).
Supports stream uploading, pinned version retrieval, and test-mock fallbacks.
"""

import io
import os
import uuid
from typing import BinaryIO, Dict, List, Optional, Tuple

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import settings
from app.logging import logger

_s3_client = None
_in_memory_storage: Dict[str, List[Dict[str, bytes]]] = {}
_force_mock_storage = False


def set_mock_storage(enabled: bool = True):
    global _force_mock_storage
    _force_mock_storage = enabled


def get_s3_client(use_disposer: bool = False):
    global _s3_client
    if _force_mock_storage:
        return None

    access_key = settings.S3_DISPOSER_ACCESS_KEY if use_disposer else settings.S3_APP_ACCESS_KEY
    secret_key = settings.S3_DISPOSER_SECRET_KEY if use_disposer else settings.S3_APP_SECRET_KEY

    try:
        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL_HOST if "127.0.0.1" in settings.S3_ENDPOINT_URL_HOST else settings.S3_ENDPOINT_URL,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=settings.S3_REGION,
            config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
        )
        return client
    except Exception as e:
        logger.warning("s3_client_initialization_failed", error=str(e))
        return None


def put_stream(
    bucket: str,
    key: str,
    stream: BinaryIO,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload stream to S3 and return assigned version ID."""
    client = get_s3_client()
    if client is not None:
        try:
            resp = client.put_object(
                Bucket=bucket,
                Key=key,
                Body=stream,
                ContentType=content_type,
            )
            return resp.get("VersionId") or "v1"
        except Exception as e:
            logger.warning("s3_put_object_fallback", error=str(e))

    # Mock in-memory storage fallback
    full_key = f"{bucket}/{key}"
    data = stream.read()
    version_id = str(uuid.uuid4())
    if full_key not in _in_memory_storage:
        _in_memory_storage[full_key] = []
    _in_memory_storage[full_key].append({"version_id": version_id, "data": data, "content_type": content_type})
    return version_id


def get_stream(
    bucket: str,
    key: str,
    version_id: Optional[str] = None,
) -> Tuple[BinaryIO, str]:
    """Retrieve object stream and content type, optionally pinned to a version ID."""
    client = get_s3_client()
    if client is not None:
        try:
            params = {"Bucket": bucket, "Key": key}
            if version_id:
                params["VersionId"] = version_id
            resp = client.get_object(**params)
            return resp["Body"], resp.get("ContentType", "application/octet-stream")
        except Exception as e:
            logger.warning("s3_get_object_fallback", error=str(e))

    # Mock fallback
    full_key = f"{bucket}/{key}"
    versions = _in_memory_storage.get(full_key, [])
    if not versions:
        raise FileNotFoundError(f"Storage key {key} not found in {bucket}")

    target = versions[-1]
    if version_id:
        found = next((v for v in versions if v["version_id"] == version_id), None)
        if found:
            target = found

    return io.BytesIO(target["data"]), target.get("content_type", "application/octet-stream")


def head(
    bucket: str,
    key: str,
    version_id: Optional[str] = None,
) -> Dict[str, str]:
    """Get metadata and latest version id for an object."""
    client = get_s3_client()
    if client is not None:
        try:
            params = {"Bucket": bucket, "Key": key}
            if version_id:
                params["VersionId"] = version_id
            resp = client.head_object(**params)
            return {
                "version_id": resp.get("VersionId") or "v1",
                "content_type": resp.get("ContentType", "application/octet-stream"),
                "size": str(resp.get("ContentLength", 0)),
            }
        except Exception as e:
            logger.warning("s3_head_object_fallback", error=str(e))

    full_key = f"{bucket}/{key}"
    versions = _in_memory_storage.get(full_key, [])
    if not versions:
        raise FileNotFoundError(f"Storage key {key} not found in {bucket}")

    target = versions[-1]
    if version_id:
        found = next((v for v in versions if v["version_id"] == version_id), None)
        if found:
            target = found

    return {
        "version_id": target["version_id"],
        "content_type": target.get("content_type", "application/octet-stream"),
        "size": str(len(target["data"])),
    }


def latest_version_id(bucket: str, key: str) -> Optional[str]:
    """Get latest assigned version ID for key."""
    try:
        info = head(bucket, key)
        return info.get("version_id")
    except Exception:
        return None


def delete_all_versions(bucket: str, key: str) -> None:
    """Delete all versions of an object (using disposer credentials)."""
    client = get_s3_client(use_disposer=True)
    if client is not None:
        try:
            versions = client.list_object_versions(Bucket=bucket, Prefix=key)
            delete_objects = []
            for v in versions.get("Versions", []):
                if v["Key"] == key:
                    delete_objects.append({"Key": key, "VersionId": v["VersionId"]})
            for dm in versions.get("DeleteMarkers", []):
                if dm["Key"] == key:
                    delete_objects.append({"Key": key, "VersionId": dm["VersionId"]})
            if delete_objects:
                client.delete_objects(Bucket=bucket, Delete={"Objects": delete_objects})
        except Exception as e:
            logger.warning("s3_delete_versions_failed", error=str(e))

    full_key = f"{bucket}/{key}"
    _in_memory_storage.pop(full_key, None)
