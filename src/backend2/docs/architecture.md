# Architecture & Design Overview

## 1. System Architecture
The NFSU Placement Management API is a layered, high-security FastAPI application designed around:
1. **Pure Policy Engine (`app.policy.rules`)**:
   - Zero side-effects, database-independent dataclass architecture.
   - Evaluates placement guidelines (A+, A, B, C switching, package multipliers, unexcused absence exclusions, single offer rules, and company specific criteria).
2. **Service & Glue Layer (`app.services`)**:
   - Maps database entities to policy models and enforces field-level visibility controls.
   - Centralizes contact masking for Course Coordinators (`mask_mobile`).
   - Computes placement status dynamically without direct client writes.
3. **Database & Persistence (`app.models`, `app.db`, `app.migrations`)**:
   - SQLite WAL mode with foreign key integrity.
   - Idempotent startup migrations that safely add tables and columns without data conversion.
   - Field-level encryption for mobile numbers and MFA secrets.
4. **Append-Only History & Chained Audit (`app.audit`, `app.models.OfferEvent`)**:
   - Cryptographic SHA-256 hash-chaining (`prev_hash`, `row_hash`).
   - Every mutation and confidential read generates an immutable audit record.
5. **Security Controls & Middleware (`app.security`, `app.main`)**:
   - Brute-force lockout and timing attack mitigation via dummy password hashing.
   - Anti-CSRF protection via mandatory `X-Requested-With: placement-ui` header on unsafe methods.
   - HttpOnly, SameSite=Strict cookies with configurable idle timeout and absolute session duration.
   - TOTP MFA support with encrypted secrets and single-use recovery codes.
