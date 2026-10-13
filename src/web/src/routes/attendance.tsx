import * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { NfsuShell } from "../components/layout/nfsu-shell";
import { api } from "../lib/api-client";
import { useAuth } from "../lib/auth-context";
import type {
	CompanyRecord,
	DriveEventType,
	StudentRecord,
} from "../lib/api-types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { SearchableSelect } from "../components/ui/searchable-select";
import {
	CheckCircleIcon,
	ClipboardDocumentCheckIcon,
	ExclamationTriangleIcon,
	ShieldExclamationIcon,
	XCircleIcon,
	XMarkIcon,
} from "@heroicons/react/24/outline";

export const Route = createFileRoute("/attendance")({
	component: AttendanceModule,
});

const eventOptions = [
	{ value: "ppt", label: "Pre-Placement Talk (PPT)" },
	{ value: "test", label: "Online Assessment / Written Test" },
	{ value: "interview", label: "Technical / HR Interview" },
	{ value: "other", label: "Other Recruitment Activity" },
];

export interface LocalAttendanceItem {
	id: number;
	studentId: number;
	studentName: string;
	placementId: string;
	course: string;
	companyId: number;
	companyName: string;
	event: DriveEventType;
	attended: boolean;
	emergencyException: boolean;
	reviewStatus: string; // "open" | "confirmed" | "excused" | "none"
	recordedAt: string;
}

const ATTENDANCE_STORAGE_KEY = "nfsu_attendance_ledger_records";

function AttendanceModule() {
	const { role } = useAuth();
	const [students, setStudents] = React.useState<StudentRecord[]>([]);
	const [companies, setCompanies] = React.useState<CompanyRecord[]>([]);
	const [auditLogs, setAuditLogs] = React.useState<any[]>([]);
	const [attendanceRecords, setAttendanceRecords] = React.useState<LocalAttendanceItem[]>([]);
	const [isLoading, setIsLoading] = React.useState(true);

	// Form State
	const [studentId, setStudentId] = React.useState<number | "">("");
	const [companyId, setCompanyId] = React.useState<number | "">("");
	const [event, setEvent] = React.useState<DriveEventType>("ppt");
	const [attended, setAttended] = React.useState(true);
	const [emergencyException, setEmergencyException] = React.useState(false);
	const [statusMessage, setStatusMessage] = React.useState<{ text: string; isError?: boolean } | null>(null);
	const [isSubmitting, setIsSubmitting] = React.useState(false);

	// Review Modal State
	const [reviewingItem, setReviewingItem] = React.useState<LocalAttendanceItem | null>(null);
	const [reviewOutcome, setReviewOutcome] = React.useState<"confirmed" | "excused">("excused");
	const [isReviewing, setIsReviewing] = React.useState(false);

	// Load students, companies, and historical attendance ledger
	const loadData = React.useCallback(async () => {
		setIsLoading(true);
		try {
			const [stuRes, compRes] = await Promise.all([
				api.listStudents({ limit: 100 }),
				api.listCompanies(),
			]);
			setStudents(stuRes);
			setCompanies(compRes);

			// Reconstruct ledger from saved state and audit logs
			const saved = localStorage.getItem(ATTENDANCE_STORAGE_KEY);
			let localList: LocalAttendanceItem[] = [];
			if (saved) {
				try {
					localList = JSON.parse(saved);
				} catch {
					localList = [];
				}
			}

			// Try to supplement from audit trail if admin
			try {
				const logs = await api.getAuditLogs(100, 0);
				if (Array.isArray(logs)) {
					const attendanceLogs = logs.filter(
						(l: any) => l.action === "attendance_record" && l.after
					);
					const studentMap = new Map(stuRes.map((s) => [s.id, s]));
					const companyMap = new Map(compRes.map((c) => [c.id, c]));

					for (const l of attendanceLogs) {
						const logStuId = l.after?.student_id;
						const exists = localList.some((it) => it.id === l.entity_id || it.id === l.id);
						if (!exists && logStuId) {
							const st = studentMap.get(logStuId);
							localList.push({
								id: Number(l.entity_id ?? l.id),
								studentId: logStuId,
								studentName: st?.name || `Student #${logStuId}`,
								placementId: st?.placement_id || `ID #${logStuId}`,
								course: st?.course || "—",
								companyId: 0,
								companyName: "Recruitment Drive",
								event: "ppt",
								attended: l.after?.attended ?? false,
								emergencyException: false,
								reviewStatus: l.after?.review || (l.after?.attended ? "none" : "open"),
								recordedAt: l.ts ? l.ts.slice(0, 19).replace("T", " ") : "Recorded",
							});
						}
					}
				}
			} catch {
				// Audit fetch restricted for non-admin; fallback seamlessly to local store
			}

			setAttendanceRecords(localList);
		} catch {
			// ignore fetch err
		} finally {
			setIsLoading(false);
		}
	}, []);

	React.useEffect(() => {
		loadData();
	}, [loadData]);

	const studentOptions = React.useMemo(() => {
		return students.map((s) => ({
			value: s.id,
			label: `${s.name} (${s.placement_id})`,
			description: `${s.course} - Batch: ${s.batch}`,
		}));
	}, [students]);

	const companyOptions = React.useMemo(() => {
		return companies.map((c) => ({
			value: c.id,
			label: `${c.name} [Cat ${c.category}]`,
			description: `Category Tier: ${c.category}`,
		}));
	}, [companies]);

	const handleRecord = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!studentId || !companyId) {
			setStatusMessage({ text: "Please select both a student and an organization.", isError: true });
			return;
		}

		setStatusMessage(null);
		setIsSubmitting(true);

		try {
			const res = await api.recordAttendance({
				student_id: Number(studentId),
				company_id: Number(companyId),
				event,
				attended,
				emergency_exception: emergencyException,
			});

			const stu = students.find((s) => s.id === Number(studentId));
			const comp = companies.find((c) => c.id === Number(companyId));

			const newRecord: LocalAttendanceItem = {
				id: res?.id || Date.now(),
				studentId: Number(studentId),
				studentName: stu?.name || `Student #${studentId}`,
				placementId: stu?.placement_id || `ID #${studentId}`,
				course: stu?.course || "—",
				companyId: Number(companyId),
				companyName: comp?.name || `Company #${companyId}`,
				event,
				attended,
				emergencyException,
				reviewStatus: res?.review_status || (attended ? "none" : "open"),
				recordedAt: new Date().toISOString().slice(0, 19).replace("T", " "),
			};

			const updatedList = [newRecord, ...attendanceRecords];
			setAttendanceRecords(updatedList);
			localStorage.setItem(ATTENDANCE_STORAGE_KEY, JSON.stringify(updatedList));

			setStatusMessage({
				text: `Attendance recorded successfully! ${
					!attended && !emergencyException
						? "Flagged for 3-drive absenteeism debarment review."
						: ""
				}`,
			});
			setStudentId("");
		} catch (err: unknown) {
			setStatusMessage({
				text: err instanceof Error ? err.message : "Failed to record attendance.",
				isError: true,
			});
		} finally {
			setIsSubmitting(false);
		}
	};

	const handleReviewSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!reviewingItem) return;
		setIsReviewing(true);

		try {
			await api.reviewAttendance(reviewingItem.id, { outcome: reviewOutcome });

			const updated = attendanceRecords.map((it) =>
				it.id === reviewingItem.id ? { ...it, reviewStatus: reviewOutcome } : it
			);
			setAttendanceRecords(updated);
			localStorage.setItem(ATTENDANCE_STORAGE_KEY, JSON.stringify(updated));

			setReviewingItem(null);
			loadData();
		} catch (err: unknown) {
			alert(err instanceof Error ? err.message : "Failed to update review status.");
		} finally {
			setIsReviewing(false);
		}
	};

	return (
		<NfsuShell>
			<div className="space-y-6">
				<div>
					<h1 className="text-xl font-bold text-slate-900 tracking-tight">
						Recruitment Activity Attendance Ledger
					</h1>
					<p className="text-xs text-slate-500 mt-0.5">
						Track attendance for PPTs, assessments, and interviews. Absenteeism triggers automated policy debarment flags.
					</p>
				</div>

				<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
					{/* Input Form */}
					<div className="lg:col-span-1">
						<Card className="bg-white border-slate-200/80 shadow-xs">
							<CardHeader className="pb-3 border-b border-slate-100">
								<CardTitle className="text-sm font-semibold text-slate-900 flex items-center gap-2">
									<ClipboardDocumentCheckIcon className="w-4 h-4 text-indigo-600" />
									Record Drive Attendance
								</CardTitle>
							</CardHeader>
							<CardContent className="pt-4">
								{statusMessage && (
									<div
										className={`p-3 mb-4 rounded-lg border text-xs ${
											statusMessage.isError
												? "bg-red-50 border-red-200 text-red-700"
												: "bg-emerald-50 border-emerald-200 text-emerald-800"
										}`}
									>
										{statusMessage.text}
									</div>
								)}

								<form onSubmit={handleRecord} className="space-y-3.5">
									<SearchableSelect
										id="att-student-select"
										label="Select Student"
										required
										placeholder="Search student by name or placement ID..."
										options={studentOptions}
										value={studentId}
										onChange={(val) => setStudentId(Number(val))}
									/>

									<SearchableSelect
										id="att-company-select"
										label="Drive Organization"
										required
										placeholder="Search company..."
										options={companyOptions}
										value={companyId}
										onChange={(val) => setCompanyId(Number(val))}
									/>

									<SearchableSelect
										id="att-event-select"
										label="Drive Activity Event"
										required
										options={eventOptions}
										value={event}
										onChange={(val) => setEvent(val as DriveEventType)}
									/>

									<div className="space-y-1.5 pt-1">
										<span className="text-xs font-medium text-slate-700 block">Attendance Status</span>
										<div className="flex gap-4">
											<label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer">
												<input
													type="radio"
													name="attended"
													checked={attended}
													onChange={() => setAttended(true)}
												/>
												Present
											</label>
											<label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer">
												<input
													type="radio"
													name="attended"
													checked={!attended}
													onChange={() => setAttended(false)}
												/>
												Absent (Debarment Flag)
											</label>
										</div>
									</div>

									{!attended && (
										<div className="p-3 bg-amber-50 rounded-lg border border-amber-200 space-y-2">
											<label className="flex items-center gap-2 text-xs text-amber-900 font-medium cursor-pointer">
												<input
													type="checkbox"
													checked={emergencyException}
													onChange={(e) => setEmergencyException(e.target.checked)}
												/>
												Apply Emergency Exception
											</label>
											<p className="text-[11px] text-amber-700">
												Emergency exceptions require Placement Cell authorization to prevent the 3-drive exclusion penalty.
											</p>
										</div>
									)}

									<Button
										type="submit"
										disabled={isSubmitting}
										className="w-full bg-slate-900 hover:bg-slate-800 text-white text-xs cursor-pointer"
									>
										{isSubmitting ? "Logging Event..." : "Record Attendance"}
									</Button>
								</form>
							</CardContent>
						</Card>
					</div>

					{/* Policy Guidance */}
					<div className="lg:col-span-2 space-y-4">
						<Card className="bg-white border-slate-200/80 shadow-xs">
							<CardHeader className="pb-2">
								<CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-500">
									NFSU Absenteeism Policy Rule Reference
								</CardTitle>
							</CardHeader>
							<CardContent className="space-y-3 text-xs text-slate-600">
								<div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
									<div className="font-semibold text-slate-900">
										Rule: Three-Drive Exclusion Penalty
									</div>
									<p className="mt-1 leading-relaxed">
										Students who register for a company drive but fail to attend mandatory activities (PPT, written test, or interview) without approved emergency exceptions are flagged for exclusion from the next three upcoming recruitment drives.
									</p>
								</div>
								<div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
									<div className="font-semibold text-slate-900">
										Review &amp; Exception Determination
									</div>
									<p className="mt-1 leading-relaxed">
										Flagged absences can be reviewed by authorized Placement staff to confirm debarment or grant official emergency exceptions.
									</p>
								</div>
							</CardContent>
						</Card>
					</div>
				</div>

				{/* Review Modal */}
				{reviewingItem && (
					<div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
						<Card className="max-w-md w-full bg-white border-slate-200 shadow-2xl">
							<CardHeader className="pb-3 border-b border-slate-100 flex flex-row items-center justify-between">
								<div className="flex items-center gap-2">
									<ShieldExclamationIcon className="w-5 h-5 text-amber-600" />
									<CardTitle className="text-base font-bold text-slate-900">
										Review Absence Flag #{reviewingItem.id}
									</CardTitle>
								</div>
								<button
									type="button"
									onClick={() => setReviewingItem(null)}
									className="text-slate-400 hover:text-slate-600 p-1"
								>
									<XMarkIcon className="w-5 h-5" />
								</button>
							</CardHeader>
							<CardContent className="pt-4">
								<form onSubmit={handleReviewSubmit} className="space-y-4">
									<div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-1">
										<div><strong>Student:</strong> {reviewingItem.studentName} ({reviewingItem.placementId})</div>
										<div><strong>Activity:</strong> {reviewingItem.event.toUpperCase()} at {reviewingItem.companyName}</div>
									</div>

									<div className="space-y-1.5">
										<span className="text-xs font-medium text-slate-700 block">Absence Determination</span>
										<div className="space-y-2">
											<label className="flex items-start gap-2 text-xs text-slate-700 cursor-pointer">
												<input
													type="radio"
													name="outcome"
													value="excused"
													checked={reviewOutcome === "excused"}
													onChange={() => setReviewOutcome("excused")}
													className="mt-0.5"
												/>
												<div>
													<span className="font-semibold text-emerald-800">Excused (Approved Exception)</span>
													<p className="text-slate-500 text-[11px]">Valid emergency/medical exception. No debarment penalty applied.</p>
												</div>
											</label>

											<label className="flex items-start gap-2 text-xs text-slate-700 cursor-pointer">
												<input
													type="radio"
													name="outcome"
													value="confirmed"
													checked={reviewOutcome === "confirmed"}
													onChange={() => setReviewOutcome("confirmed")}
													className="mt-0.5"
												/>
												<div>
													<span className="font-semibold text-red-800">Confirmed (Apply 3-Drive Debarment)</span>
													<p className="text-slate-500 text-[11px]">Unexcused absenteeism. Applies 3-drive exclusion penalty to student.</p>
												</div>
											</label>
										</div>
									</div>

									<div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
										<Button
											type="button"
											variant="outline"
											size="sm"
											onClick={() => setReviewingItem(null)}
											className="text-xs cursor-pointer"
										>
											Cancel
										</Button>
										<Button
											type="submit"
											size="sm"
											disabled={isReviewing}
											className="bg-slate-900 text-white hover:bg-slate-800 text-xs cursor-pointer"
										>
											{isReviewing ? "Submitting..." : "Confirm Determination"}
										</Button>
									</div>
								</form>
							</CardContent>
						</Card>
					</div>
				)}

				{/* Student Attendance Ledger Display Table */}
				<Card className="bg-white border-slate-200/80 shadow-xs">
					<CardHeader className="pb-3 border-b border-slate-100 flex flex-row items-center justify-between">
						<div>
							<CardTitle className="text-sm font-semibold text-slate-900">
								Student Attendance Ledger
							</CardTitle>
							<p className="text-xs text-slate-500 mt-0.5">
								Chronological records of drive participations, absenteeism flags, and penalty states.
							</p>
						</div>
						<Badge variant="outline" className="text-xs font-mono">
							{attendanceRecords.length} Records
						</Badge>
					</CardHeader>
					<CardContent className="p-0">
						<div className="overflow-x-auto">
							<table className="w-full text-left text-xs">
								<thead className="bg-slate-50 border-b border-slate-200/80 text-slate-600 font-medium">
									<tr>
										<th className="px-4 py-3">Recorded At</th>
										<th className="px-4 py-3">Student Name</th>
										<th className="px-4 py-3">Placement ID</th>
										<th className="px-4 py-3">Programme</th>
										<th className="px-4 py-3">Organization</th>
										<th className="px-4 py-3">Event</th>
										<th className="px-4 py-3">Attendance</th>
										<th className="px-4 py-3">Review / Debarment Status</th>
										<th className="px-4 py-3 text-right">Actions</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-slate-100">
									{isLoading ? (
										<tr>
											<td colSpan={9} className="px-4 py-8 text-center text-slate-400">
												Loading attendance records...
											</td>
										</tr>
									) : attendanceRecords.length === 0 ? (
										<tr>
											<td colSpan={9} className="px-4 py-12 text-center text-slate-500">
												<ClipboardDocumentCheckIcon className="w-10 h-10 text-slate-300 mx-auto mb-2" />
												<p className="text-sm font-medium text-slate-700">No attendance entries recorded</p>
												<p className="text-xs text-slate-400 mt-0.5">
													Use the form above to record PPT, test, or interview attendance for students.
												</p>
											</td>
										</tr>
									) : (
										attendanceRecords.map((item) => (
											<tr key={item.id} className="hover:bg-slate-50/80 transition">
												<td className="px-4 py-3 font-mono text-slate-600">
													{item.recordedAt}
												</td>
												<td className="px-4 py-3 font-medium text-slate-900">
													{item.studentName}
												</td>
												<td className="px-4 py-3 font-mono text-slate-700">
													{item.placementId}
												</td>
												<td className="px-4 py-3 text-slate-600">
													{item.course}
												</td>
												<td className="px-4 py-3 text-slate-800">
													{item.companyName}
												</td>
												<td className="px-4 py-3 uppercase font-mono text-[11px]">
													{item.event}
												</td>
												<td className="px-4 py-3">
													{item.attended ? (
														<Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px] gap-1 py-0.5">
															<CheckCircleIcon className="w-3.5 h-3.5 text-emerald-600" />
															Present
														</Badge>
													) : (
														<Badge className="bg-red-50 text-red-700 border-red-200 text-[10px] gap-1 py-0.5">
															<XCircleIcon className="w-3.5 h-3.5 text-red-600" />
															Absent
														</Badge>
													)}
												</td>
												<td className="px-4 py-3">
													{item.reviewStatus === "open" ? (
														<Badge className="bg-amber-50 text-amber-800 border-amber-300 text-[10px]">
															Pending Review
														</Badge>
													) : item.reviewStatus === "confirmed" ? (
														<Badge className="bg-red-50 text-red-800 border-red-300 text-[10px]">
															Debarred (3 Drives)
														</Badge>
													) : item.reviewStatus === "excused" ? (
														<Badge className="bg-emerald-50 text-emerald-800 border-emerald-300 text-[10px]">
															Excused Exception
														</Badge>
													) : (
														<span className="text-slate-400 font-mono text-[11px]">—</span>
													)}
												</td>
												<td className="px-4 py-3 text-right">
													{item.reviewStatus === "open" && (role === "placement_administrator" || role === "placement_officer") ? (
														<button
															type="button"
															onClick={() => setReviewingItem(item)}
															className="text-xs text-indigo-600 hover:text-indigo-800 font-medium cursor-pointer"
														>
															Review &rarr;
														</button>
													) : (
														<span className="text-slate-400 text-[11px]">—</span>
													)}
												</td>
											</tr>
										))
									)}
								</tbody>
							</table>
						</div>
					</CardContent>
				</Card>
			</div>
		</NfsuShell>
	);
}
