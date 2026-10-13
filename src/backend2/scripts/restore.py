#!/usr/bin/env python3
"""Restore script for NFSU Placement Management database.
Restores an encrypted backup archive, verifies database structure, and runs
the audit-chain verification (Row hash chain validation) after restore.
"""

import argparse
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Add backend directory to sys.path so app modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.audit import verify_chain


def restore(backup_path: str, db_output_path: str, key: str | None = None):
    backup_file = Path(backup_path)
    if not backup_file.exists():
        print(f"Error: Backup file not found: {backup_path}", file=sys.stderr)
        sys.exit(1)

    if not key:
        key = os.environ.get("BACKUP_ENCRYPTION_KEY") or os.environ.get("FIELD_ENCRYPTION_KEY")
    if not key:
        print("Error: Encryption key required (via --key or BACKUP_ENCRYPTION_KEY / FIELD_ENCRYPTION_KEY)", file=sys.stderr)
        sys.exit(1)

    fernet = Fernet(key.encode() if isinstance(key, str) else key)

    encrypted_data = backup_file.read_bytes()
    try:
        decrypted_data = fernet.decrypt(encrypted_data)
    except Exception as e:
        print(f"Error: Failed to decrypt backup (invalid key or corrupted data): {e}", file=sys.stderr)
        sys.exit(1)

    out_file = Path(db_output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(decrypted_data)
    print(f"Restored database to: {db_output_path}")

    # Verify audit chain integrity on the restored database
    engine = create_engine(f"sqlite:///{out_file.resolve()}")
    with Session(engine) as db:
        res = verify_chain(db)
        if not res["ok"]:
            print(f"FAILED: Audit chain verification failed! Bad row ID: {res.get('first_bad_id')}", file=sys.stderr)
            sys.exit(1)
        else:
            print("SUCCESS: Restored database integrity verified. Audit hash chain is valid!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore and verify encrypted database backup")
    parser.add_argument("--backup", default="./backup_encrypted.bin", help="Path to encrypted backup file")
    parser.add_argument("--out", default="./placement_restored.db", help="Path to write restored sqlite db")
    parser.add_argument("--key", help="Fernet encryption key")
    args = parser.parse_args()
    restore(args.backup, args.out, args.key)
