# Data Retention & Anonymisation Procedures

## 1. Overview
Under data protection standards, archived student personal identifying information (PII) must be purged or anonymised once the retention period has lapsed. Aggregate statistics, course placement counts, and cryptographic audit log trails must remain intact.

---

## 2. Retention Policy Configuration
The retention window is configurable per policy version in the `policy_settings` table (default: `retention_period_days = 1825`, representing 5 years).
Admins can update this value via:
`PUT /api/policy/rules`

---

## 3. Two-Step Execution Workflow

### Step 1: Previewing Retention Candidates
Before performing anonymisation, administrators can inspect the candidates:
`POST /api/admin/retention/preview`

**Request**: Empty body (authenticated as Administrator).
**Response**:
```json
{
  "retention_period_days": 1825,
  "cutoff_date": "2021-10-15T00:00:00",
  "eligible_count": 5,
  "students": [
    {
      "id": 101,
      "placement_id": "NFSU2020-001",
      "name": "John Doe",
      "archived": true,
      "updated_at": "2021-08-01T12:00:00"
    }
  ]
}
```

### Step 2: Applying Anonymisation
To prevent accidental anonymisation, the apply action requires an explicit confirmation payload:
`POST /api/admin/retention/apply`

**Request**:
```json
{
  "confirm": true
}
```

**Behaviour**:
1. Locates students where `archived = true` and `updated_at < cutoff_date`.
2. Overwrites `name` with `Anonymised Student {id}`.
3. Overwrites `email` with `anonymised_{id}@retention.local`.
4. Sets `mobile` to `null`.
5. Updates `remarks` with `"Personal data anonymised per data retention policy"`.
6. Generates an atomic `student_retention_anonymise` audit log record for each affected record.
7. Preserves `placement_id`, `course`, `batch`, `offers`, and all historical aggregate placement counts.
