# Security Controls & Verification Matrix

| Control Category | Security Requirement | Where Implemented | How Verified / Test Reference |
| :--- | :--- | :--- | :--- |
| **Authentication** | Argon2id hashing, timing-safe dummy verify | `app/security.py` | `tests/test_api.py::test_auth_required_and_csrf_header` |
| **Brute Force Protection** | Account lock after 5 failures for 15 mins | `app/routers/auth.py` | `tests/test_api.py::test_lockout_after_repeated_failures` |
| **Multi-Factor Auth** | TOTP MFA with encrypted secret & recovery codes | `app/routers/auth.py` | `tests/test_new_features.py::test_user_admin_and_mfa` |
| **CSRF & Header Check** | `X-Requested-With: placement-ui` on unsafe verbs | `app/main.py` middleware | `tests/test_api.py::test_auth_required_and_csrf_header` |
| **Session Security** | HttpOnly, SameSite=Strict cookies, idle/absolute lifetime | `app/security.py` | `tests/test_api.py`, `tests/test_new_features.py` |
| **Transport Security** | HSTS header when HTTPS or enabled | `app/main.py` middleware | Verified via middleware header assertions |
| **Access Control (RBAC)** | Strict role permission enforcement on every endpoint | `app/security.py` dependencies | `tests/test_api.py`, `tests/test_new_features.py` |
| **Data Masking** | Mobile number masking (`98******21`) for Coordinator | `app/services.py:mask_mobile` | `tests/test_new_features.py::test_contact_masking` |
| **PII Encryption at Rest** | Fernet encryption for mobile and MFA secret | `app/models.py:EncryptedString` | `tests/test_api.py::test_mobile_encrypted_at_rest` |
| **Audit Log Integrity** | SHA-256 hash chaining of audit entries | `app/audit.py` | `tests/test_api.py::test_audit_chain_detects_tampering` |
| **Confidential Read Audit** | Auditing list and detail reads of confidential PII | `app/routers/students.py` | `tests/test_new_features.py::test_retention_and_audit` |
| **Formula Injection** | Neutralising `=`, `+`, `-`, `@` in exports/imports | `app/routers/reports.py`, `app/routers/import_students.py` | `tests/test_api.py::test_export_is_audited_and_formula_safe` |
| **Immutable History** | Offer modifications logged into `offer_events` | `app/routers/offers.py` | `tests/test_new_features.py::test_offer_expiry_and_corrections` |
| **Admin Safety** | Last active admin cannot be removed or demoted | `app/routers/admin.py` | Unit tested in admin endpoints |
| **Backup Integrity** | Encrypted backup and verified restore with hash check | `scripts/backup.py`, `scripts/restore.py` | Verified script execution & hash chain validation |
