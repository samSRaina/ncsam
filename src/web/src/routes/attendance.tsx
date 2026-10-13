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
import { Button } from "../components/ui/button";
import { SearchableSelect } from "../components/ui/searchable-select";
import {
	CheckCircleIcon,
	ClipboardDocumentCheckIcon,
	ExclamationTriangleIcon,
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

function AttendanceModule() {
	const { role } = useAuth();
	const [students, setStudents] = React.useState<StudentRecord[]>([]);
	const [companies, setCompanies] = React.useState<CompanyRecord[]>([]);
	const [studentId, setStudentId] = React.useState<number | "">("");
	const [companyId, setCompanyId] = React.useState<number | "">("");
	const [event, setEvent] = React.useState<DriveEventType>("ppt");
	const [attended, setAttended] = React.useState(true);
	const [emergencyException, setEmergencyException] = React.useState(false);
	const [statusMessage, setStatusMessage] = React.useState<{ text: string; isError?: boolean } | null>(null);
	const [isSubmitting, setIsSubmitting] = React.useState(false);

	React.useEffect(() => {
		Promise.all([
			api.listStudents({ limit: 100 }),
			api.listCompanies(),
		])
			.then(([stuRes, compRes]) => {
				setStudents(stuRes);
				setCompanies(compRes);
			})
			.catch(() => {});
	}, []);

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
			await api.recordAttendance({
				student_id: Number(studentId),
				company_id: Number(companyId),
				event,
				attended,
				emergency_exception: emergencyException,
			});
			setStatusMessage({
				text: `Attendance record saved successfully! ${
					!attended && !emergencyException
						? "Student flagged for 3-drive absenteeism debarment rule."
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
												Absent (Debarment Check)
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
										{isSubmitting ? "Logging Event..." : "Record & Audit"}
									</Button>
								</form>
							</CardContent>
						</Card>
					</div>

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
										Flagged absences can be reviewed by the Placement Officer or Administrator via `/api/attendance/&#123;id&#125;/review` to approve or reject emergency appeals.
									</p>
								</div>
							</CardContent>
						</Card>
					</div>
				</div>
			</div>
		</NfsuShell>
	);
}
