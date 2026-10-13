/**
 * API Type Definitions aligned directly with live backend: http://172.18.45.24:8000
 * NFSU Placement Cell Management System
 */

export type Course =
  | "M.Tech CS"
  | "M.Tech AIDS"
  | "B.Tech-M.Tech CS"
  | "M.Sc CS"
  | "M.Sc DFIS";

export type Category = "A+" | "A" | "B" | "C";

export type OfferType = "I" | "F" | "I+F";

export type RegistrationStatus = "registered" | "deregistered" | "not_registered";

export type EligibilityStatus = "eligible" | "ineligible" | "pending_verification";

export type Acceptance = "pending" | "accepted" | "declined" | "expired";

export type Joining = "pending" | "joined" | "not_joined";

export type PPOStatus =
  | "not_applicable"
  | "pending"
  | "offered"
  | "accepted"
  | "declined";

export type AbsenceReviewOutcome = "confirmed" | "excused";

export type DriveEventType = "ppt" | "test" | "interview" | "other";

export type StipendPeriodType = "monthly" | "weekly" | "total";

export interface StudentCreate {
  placement_id: string;
  name: string;
  mobile?: string | null;
  email: string;
  course: Course;
  batch: string; // pattern: ^\d{4}-\d{2}$
  registration_status?: RegistrationStatus;
  eligibility_status?: EligibilityStatus;
  remarks?: string | null;
}

export interface StudentUpdate {
  name?: string | null;
  mobile?: string | null;
  email?: string | null;
  course?: Course | null;
  batch?: string | null;
  registration_status?: RegistrationStatus | null;
  eligibility_status?: EligibilityStatus | null;
  remarks?: string | null;
}

export interface StudentRecord {
  id: number;
  placement_id: string;
  name: string;
  mobile?: string | null;
  email: string;
  course: Course;
  batch: string;
  registration_status: RegistrationStatus;
  eligibility_status: EligibilityStatus;
  remarks?: string | null;
  is_archived?: boolean;
  exclusion_countdown?: number;
  active_offer_count?: number;
  created_at?: string;
  updated_at?: string;
}

export interface CompanyIn {
  name: string;
  category: Category;
}

export interface CompanyRecord {
  id: number;
  name: string;
  category: Category;
  created_at?: string;
}

export interface OfferCreate {
  student_id: number;
  company_id: number;
  offer_type: OfferType;
  ctc_lpa?: number | null;
  stipend_amount?: number | null;
  stipend_period?: StipendPeriodType | null;
  offer_date: string;
  company_deadline_hours?: number | null;
  off_campus?: boolean;
  noc_status?: string | null;
  remarks?: string | null;
  override_reason?: string | null;
}

export interface OfferUpdate {
  acceptance_status?: Acceptance | null;
  joining_status?: Joining | null;
  ppo_status?: PPOStatus | null;
  noc_status?: string | null;
  remarks?: string | null;
}

export interface OfferRecord {
  id: number;
  student_id: number;
  company_id: number;
  company_name?: string;
  company_category?: Category;
  offer_type: OfferType;
  ctc_lpa?: number | null;
  stipend_amount?: number | null;
  stipend_period?: StipendPeriodType | null;
  offer_date: string;
  company_deadline_hours?: number | null;
  acceptance_deadline?: string | null;
  off_campus: boolean;
  acceptance_status: Acceptance;
  joining_status: Joining;
  ppo_status: PPOStatus;
  noc_status?: string | null;
  remarks?: string | null;
  override_reason?: string | null;
  created_at?: string;
}

export interface AttendanceIn {
  student_id: number;
  company_id: number;
  event: DriveEventType;
  attended: boolean;
  emergency_exception?: boolean;
}

export interface AbsenceReview {
  outcome: AbsenceReviewOutcome;
}

export interface AttendanceRecord {
  id: number;
  student_id: number;
  student_name?: string;
  company_id: number;
  company_name?: string;
  event: DriveEventType;
  attended: boolean;
  emergency_exception: boolean;
  review_status?: "pending" | "confirmed" | "excused";
  created_at?: string;
}

export interface LoginIn {
  username: string;
  password: string;
}

export interface UserMe {
  id: number | string;
  username: string;
  email?: string;
  role: UserRole;
  course?: Course | null;
  company_id?: number | null;
}

export type UserRole =
  | "placement_administrator"
  | "placement_officer"
  | "course_coordinator"
  | "recruiter";

export interface EligibilityReasonItem {
  code?: string;
  verdict?: "ALLOW" | "BLOCK" | "REVIEW" | string;
  message?: string;
}

export interface EligibilityResult {
  allowed?: boolean;
  verdict?: "ALLOW" | "BLOCK" | "REVIEW" | "ALLOWED" | "BLOCKED" | string;
  status?: "allowed" | "blocked" | "review" | string;
  reasons?: EligibilityReasonItem[];
  rule_triggered?: string;
  reason?: string;
  decision?: string;
  explanation?: string;
  current_category?: Category | null;
  target_category?: Category | null;
  details?: Record<string, unknown>;
}

export interface CourseSummaryStats {
  students?: number;
  registered?: number;
  placed_unique?: number;
  offers_total?: number;
}

export interface ReportSummary {
  students?: {
    total?: number;
    registered?: number;
    eligible?: number;
    ineligible?: number;
    placed_unique?: number;
    unplaced?: number;
  };
  offers_total?: number;
  placement_status_counts?: Record<string, number>;
  by_course?: Record<string, CourseSummaryStats>;
  pending?: {
    offer_acceptance?: number;
    joining?: number;
    policy_review_cases?: number;
  };
  fte_ctc_lpa?: {
    count?: number;
    highest?: number | null;
    average?: number | null;
    median?: number | null;
  };
  internship_stipend?: {
    count?: number;
    highest?: number | null;
    average?: number | null;
    median?: number | null;
  };
  company_wise?: Record<string, unknown>;
}

export interface AuditVerification {
  tamper_evident?: boolean;
  chain_verified?: boolean;
  total_records?: number;
  last_hash?: string;
  verified_at?: string;
  status?: string;
}

export interface AuditEntry {
  id: number;
  ts: string;
  actor_id?: number | string | null;
  actor_role?: string | null;
  action: string;
  entity: string;
  entity_id?: string | number | null;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
  ip?: string | null;
}
