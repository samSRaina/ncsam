/**
 * API client with HTTP-only session credentials and CSRF protection
 */
import type {
  AbsenceReview,
  AttendanceIn,
  AttendanceRecord,
  AuditEntry,
  AuditVerification,
  CompanyIn,
  CompanyRecord,
  Course,
  EligibilityResult,
  EligibilityStatus,
  LoginIn,
  OfferCreate,
  OfferRecord,
  OfferType,
  OfferUpdate,
  RegistrationStatus,
  ReportSummary,
  StudentCreate,
  StudentRecord,
  StudentUpdate,
  UserMe,
} from "./api-types";

const API_BASE = ""; // Uses relative /api paths proxied by Vite

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  // CSRF Protection requirement:
  // Every POST, PATCH and DELETE needs X-Requested-With: placement-ui
  if (method === "POST" || method === "PATCH" || method === "DELETE") {
    headers.set("X-Requested-With", "placement-ui");
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    method,
    headers,
    credentials: "include", // Strictly HTTP-only cookie support
  });

  if (!response.ok) {
    let errorDetail = `Request failed: ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        errorDetail =
          typeof errJson.detail === "string"
            ? errJson.detail
            : JSON.stringify(errJson.detail);
      }
    } catch {
      // Ignore JSON parse failure on raw error
    }
    const err = new Error(errorDetail);
    (err as unknown as { status: number }).status = response.status;
    throw err;
  }

  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    return response.json();
  }
  return response.text() as unknown as T;
}

export const api = {
  // Auth
  login: (data: LoginIn) =>
    request<UserMe>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  logout: () =>
    request<{ message: string }>("/api/auth/logout", {
      method: "POST",
    }),
  getMe: () => request<UserMe>("/api/auth/me"),

  // Students
  listStudents: (params?: {
    course?: Course;
    batch?: string;
    q?: string;
    registration_status?: RegistrationStatus;
    eligibility_status?: EligibilityStatus;
    include_archived?: boolean;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params) {
      for (const [key, val] of Object.entries(params)) {
        if (val !== undefined && val !== null && val !== "") {
          query.append(key, String(val));
        }
      }
    }
    const qStr = query.toString();
    return request<StudentRecord[]>(`/api/students${qStr ? `?${qStr}` : ""}`);
  },
  createStudent: (data: StudentCreate) =>
    request<StudentRecord>("/api/students", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getMyRecord: () => request<StudentRecord>("/api/students/me"),
  getStudent: (studentId: string | number) =>
    request<StudentRecord>(`/api/students/${encodeURIComponent(studentId)}`),
  updateStudent: (studentId: string | number, data: StudentUpdate) =>
    request<StudentRecord>(`/api/students/${encodeURIComponent(studentId)}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  archiveStudent: (studentId: string | number) =>
    request<{ message: string }>(
      `/api/students/${encodeURIComponent(studentId)}`,
      {
        method: "DELETE",
      }
    ),
  getStudentOffers: (studentId: string | number) =>
    request<OfferRecord[]>(
      `/api/students/${encodeURIComponent(studentId)}/offers`
    ),
  checkEligibility: (params: {
    student_id: string | number;
    company_id: string | number;
    offer_type: OfferType;
    ctc_lpa?: number;
  }) => {
    const query = new URLSearchParams({
      company_id: String(params.company_id),
      offer_type: params.offer_type,
    });
    if (params.ctc_lpa !== undefined) {
      query.append("ctc_lpa", String(params.ctc_lpa));
    }
    return request<EligibilityResult>(
      `/api/students/${encodeURIComponent(params.student_id)}/eligibility?${query.toString()}`
    );
  },

  // Companies
  listCompanies: () => request<CompanyRecord[]>("/api/companies"),
  createCompany: (data: CompanyIn) =>
    request<CompanyRecord>("/api/companies", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Offers
  createOffer: (data: OfferCreate) =>
    request<OfferRecord>("/api/offers", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listOffers: (pendingOnly?: boolean) => {
    const q = pendingOnly ? "?pending_only=true" : "";
    return request<OfferRecord[]>(`/api/offers${q}`);
  },
  updateOffer: (offerId: string | number, data: OfferUpdate) =>
    request<OfferRecord>(`/api/offers/${encodeURIComponent(offerId)}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  // Attendance
  recordAttendance: (data: AttendanceIn) =>
    request<AttendanceRecord>("/api/attendance", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  reviewAttendance: (attendanceId: string | number, data: AbsenceReview) =>
    request<AttendanceRecord>(
      `/api/attendance/${encodeURIComponent(attendanceId)}/review`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    ),

  // Reports
  getSummaryReport: () => request<ReportSummary>("/api/reports/summary"),
  verifyAudit: () => request<AuditVerification>("/api/reports/audit/verify"),

  // Audit Logs
  getAuditLogs: (limit = 50, offset = 0) =>
    request<AuditEntry[]>(`/api/audit?limit=${limit}&offset=${offset}`),

  // Export
  getExportUrl: () => `${API_BASE}/api/export/students.csv`,

  // Health
  checkHealth: () => request<{ status: string }>("/api/health"),
};
