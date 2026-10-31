"""
Chunked cryptographic hashing helpers (SHA-256).
"""

import hashlib
from typing import BinaryIO


def hash_stream(stream: BinaryIO, chunk_size: int = 1024 * 1024) -> str:
    """Calculate SHA-256 hex digest of a binary stream in chunks."""
    hasher = hashlib.sha256()
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        hasher.update(chunk)
    return hasher.hexdigest()


def hash_bytes(data: bytes) -> str:
    """Calculate SHA-256 hex digest of bytes."""
    return hashlib.sha256(data).hexdigest()
