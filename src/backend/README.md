# NFSU Placement Backend

FastAPI + SQLite + SQLAlchemy 2. Managed with uv.

```bash
uv sync
cp .env.example .env
uv run python -m app.seed                 # dev users; passwords printed once
uv run uvicorn app.main:app --reload      # http://localhost:8000/docs
uv run pytest -q
```

Every state-changing request needs the header `X-Requested-With: placement-ui`.
Auth is an HttpOnly, SameSite=Strict session cookie, so the frontend must send `credentials: "include"`.

## Layout

```
app/
  policy/rules.py   pure rule engine (no DB). Start here.
  models.py         schema, field-level encryption, hash-chained audit table
  security.py       argon2, DB-backed sessions, RBAC deps, field visibility sets
  services.py       ORM <-> engine glue, role-based serialisation
  routers/          auth, students, offers (+companies), attendance, reports (+audit, export)
tests/              policy matrix + attack-resistance tests
```

## Design decisions worth defending in the demo

- Placement status is derived from live offers, never stored. A student has no write path to it.
- Offers are append-only history. Declined/expired offers stop counting for policy, but stay in the table.
- BLOCK is enforced server-side in `POST /offers`, not just in the UI. REVIEW needs an officer `override_reason`, which is audited.
- `extra="forbid"` on every input schema blocks mass assignment.
- Non-owned records return 404, not 403 (no enumeration).
- Mobile is Fernet-encrypted at rest. Audit rows are SHA-256 chained; `GET /api/reports/audit/verify` detects edits.
- Exports are role-restricted, audited and CSV-formula-escaped. Coordinators get course-scoped data with no compensation fields.
- Reports count unique placed students separately from offers, and keep stipend and CTC stats apart.

## Policy assumptions (confirm against the guidelines PDF)

The PDF was not in the upload, so these are my readings of the problem statement:

1. F then F is allowed only if the switching table permits it (A to A+, B at 1.5x, C to higher). Otherwise "no second FTE-only" and the switching table contradict each other.
2. Category C may move only to a strictly higher category.
3. Switching rules apply to FTE-bearing offers (F, I+F). Internship-only offers are not categorised by stipend.
4. F then I+F goes to manual REVIEW (the statement is silent).
5. "Live" offer = acceptance pending or accepted. "Placed" in reports = at least one accepted offer.
6. Absenteeism: an absence opens a flag (REVIEW). Officer confirms, which sets a 3-drive exclusion (BLOCK). Excusing clears it. Decrementing the counter per drive is not implemented.
7. Offer category comes from the company record. `category_from_ctc` exists if you would rather derive it.

All thresholds are in `PolicyConfig`.

## Not done yet (cut for time)

- CSV import (`POST /students/import`): validate row by row, reuse `StudentCreate`, audit once per batch.
- TOTP MFA (pyotp), password change, user-management endpoints.
- Decrementing `exclusion_drives_remaining` per drive; auto-expiring offers past `acceptance_deadline`.
- Encrypted backup script (`sqlite3 .backup` + age/gpg) and restore test.
- Hard-delete / retention job. Archive is soft only.
- Rate limiting beyond per-account lockout. Put a reverse proxy in front for real deployments.
- Run behind HTTPS and set `COOKIE_SECURE=true`.
