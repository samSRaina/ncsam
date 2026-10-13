# CHANGES.md: Implementation Summary & Audit Record

This document records all modifications, new modules, database migrations, configuration variables, and design decisions made to implement the NFSU Placement Management Backend Completion Brief.

In accordance with strict project instructions:
1. The original backend (`src/backend`) has been left completely intact and untouched.
2. The entire updated backend implementation resides in `src/backend2`.
3. All original behaviors, status codes, schemas, and security invariants from Section 2 are strictly preserved.
4. Contact masking for Course Coordinators (Section 3) is implemented via a unified helper.

---

## 1. Files Added and Modified in `src/backend2`

### Core Application Files Modified
- **`app/config.py`**:
  - Added new configuration options with default values matching previous runtime behaviors: `export_max_rows` (10,000), `mfa_encryption_key`, `enable_hsts` (False), `max_import_size_bytes` (5MB), and `max_import_rows` (5,000).
- **`app/enums.py`**:
  - Added additive Enums: `DriveStatus` (`planned`, `ongoing`, `completed`, `cancelled`), `ParticipantStatus` (`invited`, `registered`, `attended`, `absent`, `selected`, `rejected`), `ReviewStatus` (`open`, `approved`, `rejected`, `dismissed`), `ReviewKind` (`switching_conflict`, `offer_type_conflict`, `absenteeism`, `off_campus_unreported`, `deadline_breach`, `other`).
- **`app/models.py`**:
  - `Company`: Added `is_active: bool = True`.
  - `Student`: Added `academic_score: float | None = None`.
  - `Attendance`: Added `drive_id: int | None` foreign key referencing `drives.id`.
  - `User`: Added `mfa_enabled: bool = False`, `mfa_secret: EncryptedString | None`, `mfa_recovery_codes: Text | None`.
  - Added new tables: `PolicySetting`, `Drive`, `DriveParticipant`, `CompanyCriteria`, `PolicyReview`, `OfferEvent`.
- **`app/policy/rules.py`**:
  - Added `absence_exclusion_window` to `PolicyConfig`.
  - Updated `StudentState` with `course`, `batch`, `academic_score`.
  - Updated `Opportunity` with `CompanyCriteriaRule`.
  - Added evaluation checks for company allowed courses, batches, academic scores, and registration requirements.
- **`app/policy/__init__.py`**:
  - Exported `CompanyCriteriaRule`.
- **`app/services.py`**:
  - Added `mask_mobile()` helper (e.g. `98******21`) for Course Coordinator views.
  - Added `latest_audit_ref()` to attach `audit_ref` to Student and Offer serialization.
  - Implemented dynamic policy config lookup `get_current_policy_config()` from `policy_settings`.
  - Extended `student_out()` to include `academic_score` (admin/officer only), `audit_ref`, and masked `mobile` for Course Coordinators.
  - Extended `offer_out()` to include `audit_ref`.
- **`app/audit.py`**:
  - Updated `log()` to return the persisted `AuditLog` row instance for reference linking.
- **`app/schemas.py`**:
  - Added optional `academic_score` to `StudentCreate` and `StudentUpdate`.
  - Added optional `drive_id` to `AttendanceIn`.
  - Added schemas for Drives, Criteria, Policy Settings, Policy Reviews, Offer Corrections, User Administration, and MFA.
- **`app/routers/students.py`**:
  - Added confidential read audit log on listing students with contact data.
  - Added `X-Total-Count` header on list.
  - Added `GET /api/students/duplicates` for detecting suspected duplicate records.
  - Added `GET /api/students/{id}/attendance` and `GET /api/students/{id}/restrictions`.
- **`app/routers/offers.py`**:
  - Added `PATCH /api/companies/{id}` and `POST /api/companies/{id}/deactivate`.
  - Added `GET /api/companies/{id}/eligibility-rules` and `PUT /api/companies/{id}/eligibility-rules`.
  - Added validation refusing acceptance of expired offers.
  - Added `GET /api/offers/pending-deadlines` and `POST /api/offers/expire-overdue`.
  - Added `GET /api/offers/{id}` (single-offer read).
  - Added `GET /api/offers/{id}/history`, `POST /api/offers/{id}/correct`, `POST /api/offers/{id}/withdraw`, and `POST /api/offers/{id}/reinstate`.
  - Integrated append-only logging to `offer_events` table.
- **`app/routers/attendance.py`**:
  - Added `drive_id` support and company drive validation.
  - Added filters for `GET /api/attendance` and created `GET /api/attendance/flags`.
  - Applied dynamic absence exclusion window based on active policy settings.
- **`app/routers/auth.py`**:
  - Integrated TOTP MFA verification with rate-limiting and recovery code support.
  - Added `POST /api/auth/change-password`, `POST /api/auth/mfa/enroll`, `POST /api/auth/mfa/activate`, `POST /api/auth/mfa/disable`, and `POST /api/auth/mfa/verify`.
- **`app/routers/reports.py`**:
  - Added `by_batch` breakdown and placement type counts to `GET /api/reports/summary`.
  - Added `GET /api/reports/placements`, `GET /api/reports/packages`, `GET /api/reports/companies`, `GET /api/reports/switching-eligible`, `GET /api/reports/pending`, and `GET /api/reports/compliance`.
  - Added `entry_hash` and `prev_hash` to `GET /api/audit` response with filtering parameters.
  - Added CSV and XLSX exports: `/api/export/students.xlsx`, `/api/export/offers.csv`, `/api/export/offers.xlsx`, `/api/export/placements.csv`.
- **`app/main.py`**:
  - Registered all new routers: `drives`, `policy`, `policy_reviews`, `import_students`, `admin`.
  - Integrated automatic idempotent startup migrations.
  - Added Strict-Transport-Security (HSTS) header support.

### New Modules Created
- **`app/migrations.py`**: Idempotent startup migration module that adds missing tables and columns without destructive schema changes and seeds initial version 1 policy rules.
- **`app/routers/drives.py`**: Recruitment drives management, participant tracking, and drive-level criteria overrides.
- **`app/routers/policy.py`**: Policy settings versioning (`/api/policy/rules`) and manual review queue (`/api/policy/reviews`).
- **`app/routers/import_students.py`**: Multipart CSV/XLSX bulk student importer with dry-run and formula injection sanitization.
- **`app/routers/admin.py`**: User management, session termination, and data retention preview/apply.
- **`scripts/backup.py`**: Encrypted database backup generation using Fernet.
- **`scripts/restore.py`**: Encrypted database restore with automatic cryptographic audit chain integrity verification.
- **`tests/test_new_features.py`**: Automated test suite covering all 15 new feature areas.

### Documentation Files Created in `docs/`
- **`docs/schema.md`**: Complete database schema and Mermaid ER diagram.
- **`docs/architecture.md`**: Layered architecture and security design.
- **`docs/security_controls.md`**: Security controls and verification mapping table.
- **`docs/roles_matrix.md`**: Full role and permission matrix across all API endpoints.
- **`docs/backup_restore.md`**: Operational guide for backup, restore, and audit verification.
- **`docs/retention.md`**: Data retention and anonymisation procedure.
- **`docs/testing_and_limitations.md`**: Test instructions and known operational notes.
- **`openapi.json`**: Regenerated OpenAPI specification file containing all 67 routes.

---

## 2. Idempotent Migrations
Startup migrations are implemented in `app/migrations.py` and run automatically on application startup via `lifespan`:
- Adds table `policy_settings` and seeds version 1 if empty.
- Adds table `drives`.
- Adds table `drive_participants`.
- Adds table `company_criteria`.
- Adds table `policy_reviews`.
- Adds table `offer_events`.
- Adds nullable/defaulted columns:
  - `companies.is_active` (BOOLEAN DEFAULT 1)
  - `students.academic_score` (FLOAT)
  - `attendance.drive_id` (INTEGER REFERENCES drives(id))
  - `users.mfa_enabled` (BOOLEAN DEFAULT 0)
  - `users.mfa_secret` (VARCHAR(300))
  - `users.mfa_recovery_codes` (TEXT)

---

## 3. Environment Variables
All previous variables remain intact with identical defaults. New optional environment variables:
- `EXPORT_MAX_ROWS`: Maximum number of records included in export files (default: `10000`).
- `ENABLE_HSTS`: Enforce `Strict-Transport-Security` headers (default: `False`).
- `MAX_IMPORT_SIZE_BYTES`: Maximum upload size for student bulk import (default: `5242880` / 5MB).
- `MAX_IMPORT_ROWS`: Maximum rows allowed in bulk import file (default: `5000`).
- `BACKUP_ENCRYPTION_KEY`: Optional Fernet key for backup scripts (falls back to `FIELD_ENCRYPTION_KEY`).

---

## 4. Key Assumptions Made
1. **Existing Backend Preservation**: As mandated, `src/backend` was left completely untouched, and the completed code is deployed in `src/backend2`.
2. **Contact Masking**: The mask pattern `98******21` shows the first 2 and last 2 characters of the mobile number, masking any characters in between with `*`.
3. **Offer Events on Creation**: In addition to tracking corrections and status changes, initial offer creations also log an event in `offer_events` so the complete lifecycle has a verifiable starting event.
4. **All-or-Nothing Import Default**: `dry_run=true` and `partial=false` are the default parameters for student bulk imports. If any row fails validation in default mode, the entire batch is rejected with an itemized per-row error list.
