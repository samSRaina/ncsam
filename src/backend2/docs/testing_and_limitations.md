# Testing Notes & Known Limitations

## 1. Automated Test Suite
The backend is verified using `pytest`. The test suite consists of:
- `tests/test_api.py`: Baseline tests confirming all original endpoints (Section 2) continue to function identically.
- `tests/test_policy.py`: Policy engine verification of guidelines (A+, A, B, C switches, 1.5x multiplier, I/F/I+F logic, deadlines).
- `tests/test_new_features.py`: Complete coverage for all Section 4 features:
  - Course Coordinator contact data masking (`mask_mobile`).
  - Recruitment drives, criteria matching, participant eligibility filtering, and overrides.
  - Dynamic policy rules configuration and versioning.
  - Absence history, review outcomes, and exclusion window enforcement.
  - Offer expiry, manual review queue, and append-only event history (`offer_events`).
  - Bulk import (dry-run and commit) with formula injection sanitisation.
  - Expanded reports and CSV/XLSX export downloads.
  - User and session administration, session revocation, and TOTP MFA flows.
  - Anonymisation retention preview/apply and audit hash chain verification.

### Running Tests
```bash
uv run python -m pytest -vv
```

---

## 2. Known Limitations & Operational Notes
1. **SQLite Concurrency**: SQLite with WAL mode is used as the default datastore. While optimal for read-heavy university workloads and single-instance deployments, high-throughput horizontal clustering requires switching `DATABASE_URL` to PostgreSQL (fully supported via SQLAlchemy models).
2. **Asynchronous Tasks**: Offer expiration is provided as a scheduled background task or callable endpoint (`POST /api/offers/expire-overdue`). In production environments without a continuous Celery/scheduler daemon, standard cron invocation of this endpoint using an admin API token is recommended.
3. **MFA Secret Provisioning**: When enabling MFA on air-gapped university servers without internet access to render third-party QR codes, the secret base32 string returned by `/api/auth/mfa/enroll` can be entered manually into authenticator apps (e.g. Google Authenticator).
