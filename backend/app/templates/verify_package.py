#!/usr/bin/env python3
"""
SealTrail Standalone Export Package Verifier.
Verifies file hashes, audit chain linkage, and cryptographic signatures completely offline.
Requires Python 3.8+ (standard library only for checksums and chain checks).
"""

import base64
import hashlib
import json
import os
import sys
from pathlib import Path


def canonicalize(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    package_dir = Path(__file__).resolve().parent
    print("=== SEALTRAIL EXPORT VERIFICATION ===")
    print(f"Package root: {package_dir}\n")

    failures = []
    passes = []

    # 1. Verify SHA256SUMS.txt
    sums_file = package_dir / "SHA256SUMS.txt"
    if not sums_file.exists():
        print("[FAIL] SHA256SUMS.txt missing from package")
        sys.exit(1)

    print("[*] Verifying file checksums from SHA256SUMS.txt...")
    with open(sums_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            expected_hash, rel_path = parts[0], parts[1].lstrip("*").strip()
            # Normalize path separators
            rel_path_normalized = rel_path.replace("/", os.sep).replace("\\", os.sep)
            file_path = package_dir / rel_path_normalized

            if not file_path.exists():
                failures.append(f"File missing: {rel_path}")
                print(f"  [FAIL] {rel_path}: File missing")
                continue

            actual_hash = hash_file(file_path)
            if actual_hash == expected_hash:
                passes.append(f"Checksum: {rel_path}")
                print(f"  [PASS] {rel_path}")
            else:
                failures.append(
                    f"Checksum mismatch: {rel_path} (expected {expected_hash}, got {actual_hash})"
                )
                print(f"  [FAIL] {rel_path}: HASH MISMATCH")

    # 2. Verify Manifest and Audit Chain Linkage
    manifest_file = package_dir / "manifest.json"
    if not manifest_file.exists():
        failures.append("manifest.json missing")
        print("[FAIL] manifest.json missing")
    else:
        print("\n[*] Verifying audit log chain linkage in manifest.json...")
        try:
            with open(manifest_file, encoding="utf-8") as f:
                manifest_data = json.load(f)

            audit_entries = manifest_data.get("audit_trail", [])
            chain_ok = True
            for i, entry in enumerate(audit_entries):
                seq = entry.get("seq")
                prev_hash = entry.get("prev_hash")
                entry_hash = entry.get("entry_hash")

                canonical_dict = {
                    "action": entry.get("action"),
                    "actor_id": entry.get("actor_id"),
                    "actor_role": entry.get("actor_role"),
                    "case_id": entry.get("case_id"),
                    "evidence_id": entry.get("evidence_id"),
                    "ip": entry.get("ip"),
                    "payload": entry.get("payload") or {},
                    "seq": seq,
                    "ts": entry.get("ts"),
                }
                c_bytes = canonicalize(canonical_dict)
                prev_bytes = bytes.fromhex(prev_hash)
                computed_hash = hashlib.sha256(prev_bytes + c_bytes).hexdigest()

                if computed_hash != entry_hash:
                    chain_ok = False
                    failures.append(
                        f"Audit chain broken at seq #{seq}: computed {computed_hash} != stored {entry_hash}"
                    )
                    print(f"  [FAIL] Audit seq #{seq}: ENTRY HASH MISMATCH")
                    break

                if i > 0:
                    prev_entry = audit_entries[i - 1]
                    if entry["prev_hash"] != prev_entry["entry_hash"]:
                        chain_ok = False
                        failures.append(
                            f"Audit chain broken linkage between #{prev_entry['seq']} and #{seq}"
                        )
                        print(f"  [FAIL] Audit seq #{seq}: PREV HASH LINKAGE BROKEN")
                        break

            if chain_ok and audit_entries:
                passes.append(f"Audit chain linkage ({len(audit_entries)} entries)")
                print(f"  [PASS] All {len(audit_entries)} audit entries cryptographically linked")
            elif not audit_entries:
                print("  [WARN] Audit trail empty")
        except Exception as e:
            failures.append(f"Error parsing manifest.json: {e}")
            print(f"  [FAIL] manifest.json error: {e}")

    # 3. Verify Ed25519 Signature
    sig_file = package_dir / "manifest.sig"
    pub_file = package_dir / "PUBLIC_KEY.pem"
    if sig_file.exists() and manifest_file.exists():
        print("\n[*] Verifying cryptographic Ed25519 digital signature...")
        try:
            from cryptography.hazmat.primitives import serialization

            with open(manifest_file, "rb") as f:
                raw_manifest = json.load(f)
            manifest_bytes = canonicalize(raw_manifest)

            with open(sig_file, "rb") as f:
                sig_b64 = f.read().strip()
            sig_bytes = base64.b64decode(sig_b64)

            if pub_file.exists():
                with open(pub_file, "rb") as f:
                    pub_key = serialization.load_pem_public_key(f.read())
            else:
                pub_key = None

            if pub_key:
                pub_key.verify(sig_bytes, manifest_bytes)
                passes.append("Ed25519 manifest signature")
                print("  [PASS] Digital signature valid and verified")
            else:
                print("  [WARN] PUBLIC_KEY.pem not found; skipping signature verification")
        except ImportError:
            print("  [INFO] 'cryptography' library not installed; skipping digital signature check")
        except Exception as e:
            failures.append(f"Digital signature invalid: {e}")
            print(f"  [FAIL] Signature verification failed: {e}")

    # Summary
    print("\n" + "=" * 40)
    print(f"Verification Summary: {len(passes)} PASSED, {len(failures)} FAILED")
    print("=" * 40)

    if failures:
        print("\nFAILURES DETECTED:")
        for fail in failures:
            print(f" - {fail}")
        sys.exit(1)
    else:
        print("\nALL VERIFICATIONS PASSED: Package integrity defensible.")
        sys.exit(0)


if __name__ == "__main__":
    main()
