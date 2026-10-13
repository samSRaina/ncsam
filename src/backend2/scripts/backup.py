#!/usr/bin/env python3
"""Backup script for NFSU Placement Management database.
Produces an encrypted backup archive using Fernet symmetric encryption.
"""

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet


def backup(db_path: str, output_path: str, key: str | None = None):
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"Error: Database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    if not key:
        key = os.environ.get("BACKUP_ENCRYPTION_KEY") or os.environ.get("FIELD_ENCRYPTION_KEY")
    if not key:
        print("Error: Encryption key required (via --key or BACKUP_ENCRYPTION_KEY / FIELD_ENCRYPTION_KEY)", file=sys.stderr)
        sys.exit(1)

    fernet = Fernet(key.encode() if isinstance(key, str) else key)

    data = db_file.read_bytes()
    encrypted_data = fernet.encrypt(data)

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(encrypted_data)
    print(f"Backup successful: {output_path} (size: {len(encrypted_data)} bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup and encrypt database")
    parser.add_argument("--db", default="./placement.db", help="Path to sqlite db file")
    parser.add_argument("--out", default="./backup_encrypted.bin", help="Path to write encrypted backup")
    parser.add_argument("--key", help="Fernet encryption key")
    args = parser.parse_args()
    backup(args.db, args.out, args.key)
