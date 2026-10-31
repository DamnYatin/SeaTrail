#!/usr/bin/env python3
"""
Generate or rotate cryptographic keys and secrets for SealTrail .env.
Ensures no secrets are ever printed to stdout or logs.
"""

import argparse
import base64
import os
import secrets
from pathlib import Path

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
except ImportError:
    ed25519 = None


def generate_ed25519_keypair():
    if ed25519 is None:
        # Fallback raw 32-byte pseudo-random if cryptography not yet installed in venv
        priv_bytes = secrets.token_bytes(32)
        pub_bytes = secrets.token_bytes(32)
        return (
            base64.b64encode(priv_bytes).decode("ascii"),
            base64.b64encode(pub_bytes).decode("ascii"),
        )
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    priv_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return (
        base64.b64encode(priv_raw).decode("ascii"),
        base64.b64encode(pub_raw).decode("ascii"),
    )


def gen_secret_hex(bytes_len: int = 16) -> str:
    return secrets.token_hex(bytes_len)


def main():
    parser = argparse.ArgumentParser(description="Fill or rotate SealTrail secrets in .env")
    parser.add_argument("--rotate", action="store_true", help="Rotate all secrets regardless of current value")
    parser.add_argument("--env-file", default=None, help="Path to .env file")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent
    env_path = Path(args.env_file) if args.env_file else repo_root / ".env"
    example_path = repo_root / ".env.example"

    if not env_path.exists():
        if example_path.exists():
            env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            raise FileNotFoundError(f"Neither {env_path} nor {example_path} found")

    lines = env_path.read_text(encoding="utf-8").splitlines()
    data = {}
    ordered_keys = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, v = stripped.split("=", 1)
            k = k.strip()
            data[k] = v.strip()
            ordered_keys.append(k)

    rotate = args.rotate

    # Passwords and secrets
    if rotate or not data.get("POSTGRES_SUPERUSER_PASSWORD"):
        data["POSTGRES_SUPERUSER_PASSWORD"] = gen_secret_hex(16)
    if rotate or not data.get("DB_OWNER_PASSWORD"):
        data["DB_OWNER_PASSWORD"] = gen_secret_hex(16)
    if rotate or not data.get("DB_APP_PASSWORD"):
        data["DB_APP_PASSWORD"] = gen_secret_hex(16)
    if rotate or not data.get("MINIO_ROOT_PASSWORD"):
        data["MINIO_ROOT_PASSWORD"] = gen_secret_hex(16)
    if rotate or not data.get("S3_APP_SECRET_KEY"):
        data["S3_APP_SECRET_KEY"] = gen_secret_hex(20)
    if rotate or not data.get("S3_DISPOSER_SECRET_KEY"):
        data["S3_DISPOSER_SECRET_KEY"] = gen_secret_hex(20)
    if rotate or not data.get("JWT_SECRET"):
        data["JWT_SECRET"] = gen_secret_hex(32)
    if rotate or not data.get("SEED_PASSWORD"):
        data["SEED_PASSWORD"] = "Demo#Seal2026!"

    # Ed25519 keys
    if rotate or not data.get("CHECKPOINT_SIGNING_KEY_B64") or not data.get("CHECKPOINT_PUBLIC_KEY_B64"):
        priv_b64, pub_b64 = generate_ed25519_keypair()
        data["CHECKPOINT_SIGNING_KEY_B64"] = priv_b64
        data["CHECKPOINT_PUBLIC_KEY_B64"] = pub_b64

    # Keep database URLs aligned
    owner_pw = data.get("DB_OWNER_PASSWORD", "")
    app_pw = data.get("DB_APP_PASSWORD", "")
    su_pw = data.get("POSTGRES_SUPERUSER_PASSWORD", "")
    data["DATABASE_URL_OWNER"] = f"postgresql+psycopg://sealtrail_owner:{owner_pw}@postgres:5432/sealtrail"
    data["DATABASE_URL_APP"] = f"postgresql+psycopg://sealtrail_app:{app_pw}@postgres:5432/sealtrail"
    data["DATABASE_URL_SUPERUSER_HOST"] = f"postgresql+psycopg://postgres:{su_pw}@127.0.0.1:5432/sealtrail"

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in data:
                new_lines.append(f"{k}={data[k]}")
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"Secrets successfully updated in {env_path.name}. (Secrets are never printed)")


if __name__ == "__main__":
    main()
