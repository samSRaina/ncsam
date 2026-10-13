# Role and Permission Matrix

| Endpoint | Method | Admin | Officer | Coordinator | Recruiter | Student | Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `/api/auth/login` | POST | Yes | Yes | Yes | Yes | Yes | Returns pending status if MFA active |
| `/api/auth/logout` | POST | Yes | Yes | Yes | Yes | Yes | Destroys current session cookie |
| `/api/auth/me` | GET | Yes | Yes | Yes | Yes | Yes | Returns authenticated identity & role |
| `/api/auth/change-password`| POST | Yes | Yes | Yes | Yes | Yes | Requires current password, revokes sessions |
| `/api/auth/mfa/enroll` | POST | Yes | Yes | Yes | Yes | Yes | Generates TOTP secret & QR URI |
| `/api/auth/mfa/activate` | POST | Yes | Yes | Yes | Yes | Yes | Verifies TOTP & issues recovery codes |
| `/api/auth/mfa/disable` | POST | Yes | Yes | Yes | Yes | Yes | Disables MFA with valid TOTP code |
| `/api/auth/mfa/verify` | POST | Yes | Yes | Yes | Yes | Yes | Verifies TOTP or recovery code |
| `/api/students` | GET | Yes | Yes | Own Course (Masked) | No | No | X-Total-Count, audited confidential read |
| `/api/students` | POST | Yes | Yes | No | No | No | Validated student creation |
| `/api/students/me` | GET | No | No | No | No | Yes | Own record only |
| `/api/students/duplicates`| GET | Yes | Yes | No | No | No | Lists suspected duplicates |
| `/api/students/{id}` | GET | Yes | Yes | Own Course (Masked) | No | Own Only | Detail view; audited for staff |
| `/api/students/{id}` | PATCH | Yes | Yes | No | No | No | Updates student fields |
| `/api/students/{id}` | DELETE | Yes | No | No | No | No | Soft archive |
| `/api/students/{id}/offers`| GET | Yes | Yes | Own Course | Own Co | Own Only | Compensation scoped |
| `/api/students/{id}/eligibility` | GET | Yes | Yes | Own Course | No | No | Dry-run rule evaluation |
| `/api/students/{id}/attendance` | GET | Yes | Yes | Own Course | No | Own Only | Attendance records |
| `/api/students/{id}/restrictions` | GET | Yes | Yes | Own Course | No | Own Only | Active drive exclusions |
| `/api/companies` | GET | Yes | Yes | Yes | Own Only | No | Active companies list |
| `/api/companies` | POST | Yes | Yes | No | No | No | Create company |
| `/api/companies/{id}` | PATCH | Yes | Yes | No | No | No | Update company category/name |
| `/api/companies/{id}/deactivate` | POST | Yes | Yes | No | No | No | Soft deactivate |
| `/api/companies/{id}/eligibility-rules` | GET/PUT | Yes | Yes | Read Only | Own Co Read | No | Manage criteria |
| `/api/offers` | GET | Yes | Yes | Own Course (No Comp) | Own Co Only | No | Offer list |
| `/api/offers` | POST | Yes | Yes | No | No | No | Policy-checked creation |
| `/api/offers/pending-deadlines` | GET | Yes | Yes | Own Course | Own Co | No | Pending offers by deadline |
| `/api/offers/expire-overdue` | POST | Yes | No | No | No | No | Background/manual expiry batch |
| `/api/offers/{id}` | GET | Yes | Yes | Own Course (No Comp) | Own Co Only | Own Only | Single-offer read |
| `/api/offers/{id}` | PATCH | Yes | Yes | No | No | No | Status update |
| `/api/offers/{id}/history` | GET | Yes | Yes | Own Course | Own Co | Own Only | Append-only event history |
| `/api/offers/{id}/correct` | POST | Yes | No | No | No | No | Correct compensation/type/deadline |
| `/api/offers/{id}/withdraw`| POST | Yes | Yes | No | No | No | Withdraw offer with reason |
| `/api/offers/{id}/reinstate`| POST | Yes | No | No | No | No | Reinstate expired offer |
| `/api/drives` | GET | Yes | Yes | Yes | Own Co Only | No | List drives |
| `/api/drives` | POST | Yes | Yes | No | No | No | Create drive |
| `/api/drives/{id}` | GET/PATCH | Yes | Yes | Read Only | Own Co Read | No | Drive details |
| `/api/drives/{id}/cancel` | POST | Yes | Yes | No | No | No | Cancel drive |
| `/api/drives/{id}/participants` | GET | Yes | Yes | Own Course (Masked) | Own Co (Names) | No | Participants list |
| `/api/drives/{id}/participants` | POST | Yes | Yes | No | No | No | Add participant (checks rules) |
| `/api/drives/{id}/participants/{sid}` | DELETE | Yes | Yes | No | No | No | Remove participant |
| `/api/drives/{id}/eligibility-rules` | GET/PUT | Yes | Yes | Read Only | Own Co Read | No | Drive-level criteria overrides |
| `/api/policy/rules` | GET | Yes | Yes | No | No | No | Current settings |
| `/api/policy/rules` | PUT | Yes | No | No | No | No | Update settings |
| `/api/policy/rules/history` | GET | Yes | Yes | No | No | No | Settings versions |
| `/api/policy/reviews` | GET | Yes | Yes | Own Course | No | No | Review queue |
| `/api/policy/reviews` | POST | Yes | Yes | No | No | No | Raise review flag |
| `/api/policy/reviews/{id}` | GET | Yes | Yes | Own Course | No | No | Review detail |
| `/api/policy/reviews/{id}/decision` | POST | Yes | No | No | No | No | Decide review |
| `/api/attendance` | GET | Yes | Yes | Own Course | No | No | Attendance history |
| `/api/attendance/flags` | GET | Yes | Yes | Own Course | No | No | Unexcused absences |
| `/api/attendance` | POST | Yes | Yes | No | No | No | Record attendance |
| `/api/attendance/{id}/review` | POST | Yes | Yes | No | No | No | Review absence |
| `/api/import/students/template` | GET | Yes | Yes | No | No | No | Template CSV |
| `/api/import/students` | POST | Yes | Yes | No | No | No | Multipart bulk import |
| `/api/reports/summary` | GET | Yes | Yes | Own Course (No Comp) | No | No | Placement summary |
| `/api/reports/placements` | GET | Yes | Yes | Own Course | No | No | Course x batch breakdown |
| `/api/reports/packages` | GET | Yes | Yes | No | No | No | Compensation statistics |
| `/api/reports/companies` | GET | Yes | Yes | Own Course (No Comp) | No | No | Company performance |
| `/api/reports/switching-eligible` | GET | Yes | Yes | Own Course (No Comp) | No | No | Switching eligibility |
| `/api/reports/pending` | GET | Yes | Yes | Own Course | No | No | Pending acceptance/joining/NOC |
| `/api/reports/compliance` | GET | Yes | Yes | Own Course | No | No | Compliance flags & reviews |
| `/api/reports/audit/verify` | GET | Yes | No | No | No | No | Cryptographic chain verification |
| `/api/audit` | GET | Yes | No | No | No | No | Audit log entries & hashes |
| `/api/export/*` | GET | Yes | Yes | No | No | No | CSV and XLSX exports |
| `/api/admin/*` | GET/POST | Yes | No | No | No | No | User/session admin, retention |
