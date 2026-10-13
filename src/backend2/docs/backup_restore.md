# Backup and Restore Procedures

## 1. Overview
The database and its cryptographic audit hash chains are backed up using symmetric Fernet encryption. The backup script creates an encrypted snapshot of the SQLite database. The restore script decrypts the snapshot, reconstructs the database, and automatically validates the entire SHA-256 audit log hash chain to ensure no corruption or tampering has occurred.

---

## 2. Backup Procedure

### Command
```bash
python scripts/backup.py --db ./placement.db --out ./backups/placement_backup_$(date +%Y%m%d_%H%M%S).bin --key "$FIELD_ENCRYPTION_KEY"
```

### Parameters
- `--db`: Path to the source database file (default: `./placement.db`).
- `--out`: Target destination path for the encrypted binary file.
- `--key`: The 32-byte url-safe base64 Fernet encryption key. Alternatively provided via the environment variable `FIELD_ENCRYPTION_KEY` or `BACKUP_ENCRYPTION_KEY`.

### Verification
Ensure the output backup file exists and has non-zero size.

---

## 3. Restore Procedure

### Command
```bash
python scripts/restore.py --backup ./backups/placement_backup.bin --out ./placement.db --key "$FIELD_ENCRYPTION_KEY"
```

### Parameters
- `--backup`: Path to the encrypted backup file.
- `--out`: Destination path for the restored SQLite database.
- `--key`: The decryption key.

### Automated Integrity Verification
Upon decryption, `scripts/restore.py` connects to the restored database and executes `verify_chain(db)`.
1. It verifies that `prev_hash` of each row matches the `row_hash` of the preceding row.
2. It re-computes the canonical SHA-256 payload digest for every single row in `audit_log`.
3. If any discrepancy or bad hash is discovered, the restore script terminates with an error code and logs the first corrupted record ID.
4. If the chain is completely intact, it outputs:
   `SUCCESS: Restored database integrity verified. Audit hash chain is valid!`
