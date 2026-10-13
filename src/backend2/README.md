# NFSU Placement Backend 2 (Primary Production Backend)

FastAPI + SQLite (WAL mode) + SQLAlchemy 2. Managed with uv.

This is the primary backend implementing the complete NFSU Placement Management System (including all Section 4 features from the implementation brief, idempotent migrations, cryptographic audit chaining, data masking, TOTP MFA, recruitment drives, company criteria, bulk import, advanced reports, and export tools).

---

## 1. Quick Start

Run everything independently inside `src/backend2`:

```bash
cd src/backend2

# 1. Install & sync all dependencies
uv sync

# 2. Configure environment
cp .env.example .env

# 3. Seed initial development accounts and default version 1 policy rules
uv run python -m app.seed

# 4. Start the server (runs on http://localhost:8000)
uv run uvicorn app.main:app --reload

# 5. Run full test suite (all 42 automated tests)
uv run python -m pytest -vv
```

Every state-changing request (`POST`, `PUT`, `PATCH`, `DELETE`) requires the anti-CSRF header:
`X-Requested-With: placement-ui`

Authentication uses HttpOnly, SameSite=Strict session cookies, so frontend clients must specify `credentials: "include"`.

---

## 2. Directory Structure

```
src/backend2/
├── app/
│   ├── main.py                 # FastAPI application, CORS, CSRF & security headers, lifespan migrations
│   ├── config.py               # Application settings (session timeouts, HSTS, upload caps)
│   ├── db.py                   # SQLAlchemy engine (WAL mode, foreign keys enabled)
│   ├── enums.py                # System enums (Roles, Categories, Drives, Reviews, Offers)
│   ├── models.py               # ORM tables with field-level Fernet encryption & hash-chained audit table
│   ├── schemas.py              # Pydantic v2 schemas with extra="forbid"
│   ├── security.py             # Argon2id password hashing, RBAC dependencies, session cookies
│   ├── services.py             # Business glue, coordinator contact masking (mask_mobile), audit linking
│   ├── audit.py                # SHA-256 hash-chained audit logging and verification
│   ├── migrations.py           # Idempotent non-destructive startup migrations & policy seeding
│   ├── seed.py                 # Dev seed script
│   ├── policy/
│   │   ├── __init__.py         # Exported policy engine symbols
│   │   └── rules.py            # Pure rule engine (A+, A, B, C switches, criteria, absence window)
│   └── routers/
│       ├── auth.py             # Login, logout, /me, change-password, and TOTP MFA flows
│       ├── students.py         # Student CRUD, /duplicates, /attendance, /restrictions, eligibility dry-run
│       ├── offers.py           # Companies, offers CRUD, deadlines, expiry, correction, history
│       ├── drives.py           # Recruitment drives, participant eligibility filtering, criteria overrides
│       ├── attendance.py       # Attendance recording, absence review, flags list
│       ├── policy.py           # Dynamic policy settings (/rules) and review queue (/reviews)
│       ├── reports.py          # Summary, placements, packages, companies, switching, pending, exports
│       ├── import_students.py  # Multipart CSV/XLSX bulk student importer with dry-run
│       └── admin.py            # User management, session revocation, retention preview/apply
├── docs/                       # Complete architectural and security documentation
│   ├── schema.md               # Database schema with Mermaid ER diagram
│   ├── architecture.md         # Layered architectural design
│   ├── security_controls.md    # Security controls & verification matrix
│   ├── roles_matrix.md         # Full endpoint permissions matrix
│   ├── backup_restore.md       # Encrypted backup & restore procedures
│   ├── retention.md            # Data retention and anonymisation workflows
│   └── testing_and_limitations.md # Testing instructions and operational notes
├── scripts/
│   ├── backup.py               # Produces Fernet-encrypted database backup
│   └── restore.py              # Restores encrypted backup and verifies SHA-256 audit chain
├── tests/
│   ├── test_api.py             # Section 2 regression tests (unchanged baseline surface)
│   ├── test_policy.py          # Policy engine matrix tests
│   └── test_new_features.py    # Automated test suite for all Section 4 features
├── openapi.json                # Regenerated OpenAPI v3.1 specification (67 endpoints)
├── CHANGES.md                  # Detailed changelog, migrations, and assumptions
└── pyproject.toml              # Dependencies managed via uv
```

---

## 3. Implemented Capabilities & Security Invariants

- **Isolated & Independent**: Operates completely out of `src/backend2` with its own environment, virtualenv, dependencies, migrations, and test suite.
- **Section 2 Baseline Preserved**: All original endpoints, status codes, and permissions are preserved without alteration.
- **Course Coordinator Contact Masking (Section 3)**: Unified `mask_mobile` ensures Coordinators see masked mobile numbers (`98******21`) everywhere.
- **Recruitment Drives & Eligibility (Section 4.1 & 4.2)**: Ordered drives, participant eligibility checks against policy + company criteria + exclusions, and drive criteria overrides.
- **Configurable Policy Settings (Section 4.3)**: Dynamic versioned settings table governing category bands, multipliers, and windows without hardcoding.
- **Manual Review Queue (Section 4.4)**: Audited violation flags and decision workflow for conflicts, unexcused absences, and exceptions.
- **Attendance & Exclusions (Section 4.5)**: Confirmed unexcused absences exclude students from subsequent drives with clear reporting in restrictions endpoints.
- **Offer Expiry & Corrections (Section 4.6 & 4.12)**: Automated expiration for overdue offers, immutable `offer_events` append-only audit trail, admin corrections, and withdrawals.
- **Bulk Import (Section 4.7)**: Multipart CSV/XLSX importer with dry-run preview, duplicate detection, and formula-injection neutralization (`=`, `+`, `-`, `@`).
- **Advanced Reports & Exports (Section 4.8 & 4.9)**: Placement breakdown tables, package distributions, company performance, switching eligibility, and CSV/XLSX export endpoints.
- **User Admin & TOTP MFA (Section 4.10 & 4.11)**: Password changes with session revocation, brute force lockout, TOTP enrollment/activation, and recovery codes.
- **Retention & Audit Hardening (Section 4.13 & 4.14)**: Anonymisation preview/apply for archived records older than retention period; SHA-256 chained audit trail with `entry_hash` and `prev_hash`.
- **Encrypted Backup & Verified Restore (Section 4.15)**: Standalone backup and restore utilities that decrypt and verify audit chain integrity.
