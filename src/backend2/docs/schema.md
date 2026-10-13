# NFSU Placement System: Database Schema & Entity-Relationship Documentation

## 1. Overview
The database is hosted on SQLite (with WAL mode and foreign key constraints enabled).
All table schemas use non-destructive, additive migrations with idempotent initialization. Sensitive contact data (mobile number) and MFA secrets are encrypted at rest using symmetric Fernet key derivation.

---

## 2. Entity-Relationship Diagram

```mermaid
erDiagram
    COMPANIES ||--o{ DRIVES : hosts
    COMPANIES ||--o{ OFFERS : issues
    COMPANIES ||--o{ COMPANY_CRITERIA : defines
    COMPANIES ||--o{ ATTENDANCE : conducts

    STUDENTS ||--o{ OFFERS : receives
    STUDENTS ||--o{ DRIVE_PARTICIPANTS : participates
    STUDENTS ||--o{ ATTENDANCE : attends
    STUDENTS ||--o{ POLICY_REVIEWS : flagged_in

    DRIVES ||--o{ DRIVE_PARTICIPANTS : contains
    DRIVES ||--o{ ATTENDANCE : schedules
    DRIVES ||--o{ COMPANY_CRITERIA : overrides

    OFFERS ||--o{ OFFER_EVENTS : logs_history
    OFFERS ||--o{ POLICY_REVIEWS : references

    USERS ||--o{ OFFERS : creates
    USERS ||--o{ SESSIONS : establishes
    USERS ||--o{ OFFER_EVENTS : actors
    USERS ||--o{ POLICY_REVIEWS : raises_or_decides

    COMPANIES {
        int id PK
        string name UK
        string category
        bool is_active
    }

    STUDENTS {
        int id PK
        string placement_id UK
        string name
        string mobile "Encrypted"
        string email UK
        string course
        string batch
        string registration_status
        string eligibility_status
        int exclusion_drives_remaining
        float academic_score
        text remarks
        bool archived
        datetime created_at
        datetime updated_at
    }

    DRIVES {
        int id PK
        int company_id FK
        string name
        datetime drive_date
        string status
        json stages
        text notes
        datetime created_at
    }

    DRIVE_PARTICIPANTS {
        int id PK
        int drive_id FK
        int student_id FK
        string status
        text override_reason
        datetime created_at
        datetime updated_at
    }

    COMPANY_CRITERIA {
        int id PK
        int company_id FK
        int drive_id FK
        json allowed_courses
        json allowed_batches
        float min_academic_score
        bool requires_registration
        text notes
        datetime created_at
        datetime updated_at
    }

    OFFERS {
        int id PK
        int student_id FK
        int company_id FK
        string offer_type
        float ctc_lpa
        float stipend_amount
        string stipend_period
        string ppo_status
        string acceptance_status
        string joining_status
        datetime offer_date
        datetime acceptance_deadline
        int company_deadline_hours
        bool off_campus
        string noc_status
        string policy_verdict
        json policy_reasons
        text override_reason
        text remarks
        int created_by FK
        datetime created_at
    }

    OFFER_EVENTS {
        int id PK
        int offer_id FK
        string event_type
        int actor_id FK
        text reason
        json before
        json after
        datetime created_at
    }

    POLICY_SETTINGS {
        int id PK
        int version UK
        float a_plus_min
        float a_min
        float b_min
        float b_switch_multiplier
        int absence_exclusion_window
        int default_acceptance_window_hours
        int retention_period_days
        json mfa_required_roles
        int created_by FK
        datetime created_at
    }

    POLICY_REVIEWS {
        int id PK
        int student_id FK
        int offer_id FK
        int drive_id FK
        string kind
        text reason
        string status
        int raised_by FK
        int decided_by FK
        text decision_reason
        datetime created_at
        datetime updated_at
    }

    ATTENDANCE {
        int id PK
        int student_id FK
        int company_id FK
        int drive_id FK
        string event
        bool attended
        bool emergency_exception
        string review_status
        int recorded_by FK
        datetime created_at
    }

    USERS {
        int id PK
        string username UK
        string password_hash
        string role
        string course
        int company_id FK
        int student_id FK
        bool is_active
        int failed_logins
        datetime locked_until
        bool mfa_enabled
        string mfa_secret "Encrypted"
        text mfa_recovery_codes
    }

    SESSIONS {
        int id PK
        string token_hash UK
        int user_id FK
        datetime created_at
        datetime last_seen
        datetime expires_at
    }

    AUDIT_LOG {
        int id PK
        datetime ts
        int actor_id
        string actor_role
        string action
        string entity
        string entity_id
        json before
        json after
        string ip
        string prev_hash
        string row_hash
    }
```
