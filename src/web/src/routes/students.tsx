import * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { NfsuShell } from "../components/layout/nfsu-shell";
import { api } from "../lib/api-client";
import { useAuth } from "../lib/auth-context";
import type {
	Course,
	EligibilityStatus,
	RegistrationStatus,
	StudentCreate,
	StudentRecord,
	StudentUpdate,
} from "../lib/api-types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { SearchableSelect } from "../components/ui/searchable-select";
import {
	AcademicCapIcon,
	ArchiveBoxIcon,
	ArrowDownTrayIcon,
	EyeIcon,
	EyeSlashIcon,
	MagnifyingGlassIcon,
	PencilSquareIcon,
	PlusIcon,
	UserGroupIcon,
	XMarkIcon,
} from "@heroicons/react/24/outline";

export const Route = createFileRoute("/students")({
	component: StudentsDirectory,
});

const COURSES: Course[] = [
	"M.Tech CS",
	"M.Tech AIDS",
	"B.Tech-M.Tech CS",
	"M.Sc CS",
	"M.Sc DFIS",
];

const courseOptions = COURSES.map((c) => ({
	value: c,
	label: c,
}));

const regStatusOptions = [
	{ value: "registered", label: "Registered" },
	{ value: "not_registered", label: "Not Registered" },
	{ value: "deregistered", label: "Deregistered" },
];

const eligStatusOptions = [
	{ value: "eligible", label: "Eligible" },
	{ value: "ineligible", label: "Ineligible" },
	{ value: "pending_verification", label: "Pending Verification" },
];

function StudentsDirectory() {
	const { role, user } = useAuth();
	const [students, setStudents] = React.useState<StudentRecord[]>([]);
	const [isLoading, setIsLoading] = React.useState(true);
	const [selectedCourse, setSelectedCourse] = React.useState<Course | "ALL">("ALL");
	const [searchQuery, setSearchQuery] = React.useState("");
	const [revealedPhones, setRevealedPhones] = React.useState<Record<string | number, boolean>>({});

	// Add Student Modal State
	const [showAddModal, setShowAddModal] = React.useState(false);
	const [placementId, setPlacementId] = React.useState("");
	const [name, setName] = React.useState("");
	const [email, setEmail] = React.useState("");
	const [mobile, setMobile] = React.useState("");
	const [course, setCourse] = React.useState<Course>("M.Tech CS");
	const [batch, setBatch] = React.useState("2024-26");
	const [registrationStatus, setRegistrationStatus] = React.useState<RegistrationStatus>("registered");
	const [eligibilityStatus, setEligibilityStatus] = React.useState<EligibilityStatus>("eligible");
	const [remarks, setRemarks] = React.useState("");
	const [formError, setFormError] = React.useState<string | null>(null);
	const [isSubmitting, setIsSubmitting] = React.useState(false);

	// Detail / Edit Modal State
	const [selectedStudent, setSelectedStudent] = React.useState<StudentRecord | null>(null);
	const [isEditing, setIsEditing] = React.useState(false);
	const [editName, setEditName] = React.useState("");
	const [editEmail, setEditEmail] = React.useState("");
	const [editMobile, setEditMobile] = React.useState("");
	const [editCourse, setEditCourse] = React.useState<Course>("M.Tech CS");
	const [editBatch, setEditBatch] = React.useState("");
	const [editRemarks, setEditRemarks] = React.useState("");

	// Restrict coordinator scope
	React.useEffect(() => {
		if (role === "course_coordinator" && user?.course) {
			setSelectedCourse(user.course);
		}
	}, [role, user]);

	const loadStudents = React.useCallback(() => {
		setIsLoading(true);
		const params: { course?: Course; q?: string } = {};
		if (selectedCourse !== "ALL") params.course = selectedCourse;
		if (searchQuery.trim()) params.q = searchQuery.trim();

		api
			.listStudents(params)
			.then((data) => {
				setStudents(data);
			})
			.catch(() => {
				setStudents([]);
			})
			.finally(() => {
				setIsLoading(false);
			});
	}, [selectedCourse, searchQuery]);

	React.useEffect(() => {
		loadStudents();
	}, [loadStudents]);

	const handleCreateStudent = async (e: React.FormEvent) => {
		e.preventDefault();
		setFormError(null);
		setIsSubmitting(true);

		try {
			await api.createStudent({
				placement_id: placementId,
				name,
				email,
				mobile: mobile.trim() ? mobile.trim() : null,
				course,
				batch,
				registration_status: registrationStatus,
				eligibility_status: eligibilityStatus,
				remarks: remarks.trim() ? remarks.trim() : null,
			});
			setShowAddModal(false);
			// Reset form
			setPlacementId("");
			setName("");
			setEmail("");
			setMobile("");
			setRemarks("");
			loadStudents();
		} catch (err: unknown) {
			setFormError(
				err instanceof Error ? err.message : "Failed to register student record."
			);
		} finally {
			setIsSubmitting(false);
		}
	};

	const handleOpenDetail = (st: StudentRecord) => {
		setSelectedStudent(st);
		setEditName(st.name);
		setEditEmail(st.email);
		setEditMobile(st.mobile || "");
		setEditCourse(st.course);
		setEditBatch(st.batch);
		setEditRemarks(st.remarks || "");
		setIsEditing(false);
	};

	const handleUpdateStudent = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!selectedStudent) return;
		setIsSubmitting(true);
		try {
			await api.updateStudent(selectedStudent.id, {
				name: editName,
				email: editEmail,
				mobile: editMobile.trim() ? editMobile.trim() : null,
				course: editCourse,
				batch: editBatch,
				remarks: editRemarks.trim() ? editRemarks.trim() : null,
			});
			setSelectedStudent(null);
			loadStudents();
		} catch (err: unknown) {
			alert(err instanceof Error ? err.message : "Failed to update student.");
		} finally {
			setIsSubmitting(false);
		}
	};

	const handleArchiveStudent = async (studentId: string | number) => {
		if (!confirm("Are you sure you want to soft-archive this student? (Placement records will remain preserved)")) {
			return;
		}
		try {
			await api.archiveStudent(studentId);
			if (selectedStudent?.id === studentId) setSelectedStudent(null);
			loadStudents();
		} catch (err: unknown) {
			alert(err instanceof Error ? err.message : "Failed to archive student.");
		}
	};

	const toggleRevealPhone = (studentId: string | number) => {
		setRevealedPhones((prev) => ({
			...prev,
			[studentId]: !prev[studentId],
		}));
	};

	const maskPhone = (phone?: string | null) => {
		if (!phone) return "—";
		if (phone.length <= 4) return "••••";
		return `${phone.slice(0, 2)}••••••${phone.slice(-2)}`;
	};

	return (
		<NfsuShell>
			<div className="space-y-6">
				{/* Header & Controls */}
				<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
					<div>
						<h1 className="text-xl font-bold text-slate-900 tracking-tight">
							Student Placement Directory
						</h1>
						<p className="text-xs text-slate-500 mt-0.5">
							Maintain student profiles, eligibility verification, and placement records.
						</p>
					</div>

					<div className="flex items-center gap-2">
						<a
							href={api.getExportUrl()}
							download
							className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition shadow-xs cursor-pointer"
						>
							<ArrowDownTrayIcon className="w-4 h-4" />
							Export CSV
						</a>
						{(role === "placement_administrator" || role === "placement_officer") && (
							<Button
								size="sm"
								onClick={() => setShowAddModal(true)}
								className="bg-slate-900 text-white hover:bg-slate-800 gap-1.5 text-xs cursor-pointer"
							>
								<PlusIcon className="w-4 h-4" />
								Add Student
							</Button>
						)}
					</div>
				</div>

				{/* Add Student Modal */}
				{showAddModal && (
					<div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
						<Card className="max-w-lg w-full bg-white border-slate-200 shadow-2xl max-h-[90vh] flex flex-col">
							<CardHeader className="pb-3 border-b border-slate-100 flex flex-row items-center justify-between">
								<div>
									<CardTitle className="text-base font-bold text-slate-900">
										Register Student Record
									</CardTitle>
									<p className="text-xs text-slate-500 mt-0.5">
										Add candidate profile to the NFSU Placement Cell database.
									</p>
								</div>
								<button
									type="button"
									onClick={() => setShowAddModal(false)}
									className="text-slate-400 hover:text-slate-600 p-1 rounded-md"
								>
									<XMarkIcon className="w-5 h-5" />
								</button>
							</CardHeader>
							<CardContent className="pt-4 overflow-y-auto flex-1">
								{formError && (
									<div className="p-3 mb-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs">
										{formError}
									</div>
								)}
								<form onSubmit={handleCreateStudent} className="space-y-3.5">
									<div className="grid grid-cols-2 gap-3">
										<div className="space-y-1">
											<label htmlFor="student-placement-id" className="text-xs font-medium text-slate-700 block">
												Placement ID *
											</label>
											<Input
												id="student-placement-id"
												type="text"
												required
												value={placementId}
												onChange={(e) => setPlacementId(e.target.value)}
												placeholder="e.g. 2024-CS-001"
												className="text-xs"
											/>
										</div>

										<div className="space-y-1">
											<label htmlFor="student-full-name" className="text-xs font-medium text-slate-700 block">
												Full Name *
											</label>
											<Input
												id="student-full-name"
												type="text"
												required
												value={name}
												onChange={(e) => setName(e.target.value)}
												placeholder="Student full name"
												className="text-xs"
											/>
										</div>
									</div>

									<div className="grid grid-cols-2 gap-3">
										<div className="space-y-1">
											<label htmlFor="student-email-addr" className="text-xs font-medium text-slate-700 block">
												Email Address *
											</label>
											<Input
												id="student-email-addr"
												type="email"
												required
												value={email}
												onChange={(e) => setEmail(e.target.value)}
												placeholder="name@nfsu.ac.in"
												className="text-xs"
											/>
										</div>

										<div className="space-y-1">
											<label htmlFor="student-mobile-num" className="text-xs font-medium text-slate-700 block">
												Mobile Number
											</label>
											<Input
												id="student-mobile-num"
												type="tel"
												value={mobile}
												onChange={(e) => setMobile(e.target.value)}
												placeholder="+91 9876543210"
												className="text-xs"
											/>
										</div>
									</div>

									<div className="grid grid-cols-2 gap-3">
										<SearchableSelect
											id="student-prog-select"
											label="Academic Programme"
											required
											options={courseOptions}
											value={course}
											onChange={(v) => setCourse(v as Course)}
										/>

										<div className="space-y-1">
											<label htmlFor="student-batch-pattern" className="text-xs font-medium text-slate-700 block">
												Academic Batch *
											</label>
											<Input
												id="student-batch-pattern"
												type="text"
												required
												pattern="^\d{4}-\d{2}$"
												value={batch}
												onChange={(e) => setBatch(e.target.value)}
												placeholder="e.g. 2024-26"
												className="text-xs font-mono"
											/>
											<span className="text-[10px] text-slate-400">Format: YYYY-YY (e.g. 2024-26)</span>
										</div>
									</div>

									<div className="grid grid-cols-2 gap-3">
										<SearchableSelect
											id="student-reg-status"
											label="Registration Status"
											options={regStatusOptions}
											value={registrationStatus}
											onChange={(v) => setRegistrationStatus(v as RegistrationStatus)}
										/>

										<SearchableSelect
											id="student-elig-status"
											label="Eligibility Status"
											options={eligStatusOptions}
											value={eligibilityStatus}
											onChange={(v) => setEligibilityStatus(v as EligibilityStatus)}
										/>
									</div>

									<div className="space-y-1">
										<label htmlFor="student-admin-remarks" className="text-xs font-medium text-slate-700 block">
											Administrative Remarks
										</label>
										<Input
											id="student-admin-remarks"
											type="text"
											value={remarks}
											onChange={(e) => setRemarks(e.target.value)}
											placeholder="Optional notes or eligibility reference"
											className="text-xs"
										/>
									</div>

									<div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
										<Button
											type="button"
											variant="outline"
											size="sm"
											onClick={() => setShowAddModal(false)}
											className="text-xs cursor-pointer"
										>
											Cancel
										</Button>
										<Button
											type="submit"
											size="sm"
											disabled={isSubmitting}
											className="bg-slate-900 text-white hover:bg-slate-800 text-xs cursor-pointer"
										>
											{isSubmitting ? "Registering..." : "Confirm & Register"}
										</Button>
									</div>
								</form>
							</CardContent>
						</Card>
					</div>
				)}

				{/* Detail / Edit Student Modal */}
				{selectedStudent && (
					<div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
						<Card className="max-w-lg w-full bg-white border-slate-200 shadow-2xl">
							<CardHeader className="pb-3 border-b border-slate-100 flex flex-row items-center justify-between">
								<div className="flex items-center gap-2">
									<AcademicCapIcon className="w-5 h-5 text-indigo-600" />
									<CardTitle className="text-base font-bold text-slate-900">
										Student Profile: {selectedStudent.placement_id}
									</CardTitle>
								</div>
								<button
									type="button"
									onClick={() => setSelectedStudent(null)}
									className="text-slate-400 hover:text-slate-600 p-1 rounded-md"
								>
									<XMarkIcon className="w-5 h-5" />
								</button>
							</CardHeader>
							<CardContent className="pt-4">
								{isEditing ? (
									<form onSubmit={handleUpdateStudent} className="space-y-3.5">
										<div className="space-y-1">
											<label htmlFor="edit-student-name" className="text-xs font-medium text-slate-700 block">Full Name</label>
											<Input
												id="edit-student-name"
												type="text"
												required
												value={editName}
												onChange={(e) => setEditName(e.target.value)}
												className="text-xs"
											/>
										</div>

										<div className="grid grid-cols-2 gap-3">
											<div className="space-y-1">
												<label htmlFor="edit-student-email" className="text-xs font-medium text-slate-700 block">Email</label>
												<Input
													id="edit-student-email"
													type="email"
													required
													value={editEmail}
													onChange={(e) => setEditEmail(e.target.value)}
													className="text-xs"
												/>
											</div>
											<div className="space-y-1">
												<label htmlFor="edit-student-mobile" className="text-xs font-medium text-slate-700 block">Mobile</label>
												<Input
													id="edit-student-mobile"
													type="tel"
													value={editMobile}
													onChange={(e) => setEditMobile(e.target.value)}
													className="text-xs"
												/>
											</div>
										</div>

										<div className="grid grid-cols-2 gap-3">
											<SearchableSelect
												id="edit-student-course"
												label="Programme"
												options={courseOptions}
												value={editCourse}
												onChange={(v) => setEditCourse(v as Course)}
											/>
											<div className="space-y-1">
												<label htmlFor="edit-student-batch" className="text-xs font-medium text-slate-700 block">Batch</label>
												<Input
													id="edit-student-batch"
													type="text"
													required
													value={editBatch}
													onChange={(e) => setEditBatch(e.target.value)}
													className="text-xs font-mono"
												/>
											</div>
										</div>

										<div className="space-y-1">
											<label htmlFor="edit-student-remarks" className="text-xs font-medium text-slate-700 block">Remarks</label>
											<Input
												id="edit-student-remarks"
												type="text"
												value={editRemarks}
												onChange={(e) => setEditRemarks(e.target.value)}
												className="text-xs"
											/>
										</div>

										<div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
											<Button
												type="button"
												variant="outline"
												size="sm"
												onClick={() => setIsEditing(false)}
												className="text-xs cursor-pointer"
											>
												Cancel
											</Button>
											<Button
												type="submit"
												size="sm"
												disabled={isSubmitting}
												className="bg-slate-900 text-white hover:bg-slate-800 text-xs cursor-pointer"
											>
												Save Changes
											</Button>
										</div>
									</form>
								) : (
									<div className="space-y-3 text-xs">
										<div className="grid grid-cols-2 gap-3 pb-3 border-b border-slate-100">
											<div>
												<span className="text-slate-400 block">Full Name:</span>
												<span className="font-semibold text-slate-900">{selectedStudent.name}</span>
											</div>
											<div>
												<span className="text-slate-400 block">Placement ID:</span>
												<span className="font-mono text-slate-900">{selectedStudent.placement_id}</span>
											</div>
										</div>

										<div className="grid grid-cols-2 gap-3 pb-3 border-b border-slate-100">
											<div>
												<span className="text-slate-400 block">Programme:</span>
												<span className="text-slate-800">{selectedStudent.course}</span>
											</div>
											<div>
												<span className="text-slate-400 block">Batch:</span>
												<span className="font-mono text-slate-800">{selectedStudent.batch}</span>
											</div>
										</div>

										<div className="grid grid-cols-2 gap-3 pb-3 border-b border-slate-100">
											<div>
												<span className="text-slate-400 block">Email:</span>
												<span className="text-slate-800">{selectedStudent.email}</span>
											</div>
											<div>
												<span className="text-slate-400 block">Mobile:</span>
												<span className="font-mono text-slate-800">
													{selectedStudent.mobile || "—"}
												</span>
											</div>
										</div>

										<div className="grid grid-cols-2 gap-3 pb-3 border-b border-slate-100">
											<div>
												<span className="text-slate-400 block">Registration:</span>
												<Badge variant="outline" className="text-[10px] capitalize">
													{selectedStudent.registration_status}
												</Badge>
											</div>
											<div>
												<span className="text-slate-400 block">Eligibility:</span>
												<Badge variant="outline" className="text-[10px] capitalize">
													{selectedStudent.eligibility_status.replace("_", " ")}
												</Badge>
											</div>
										</div>

										{selectedStudent.remarks && (
											<div className="pb-3 border-b border-slate-100">
												<span className="text-slate-400 block">Administrative Remarks:</span>
												<p className="text-slate-700 mt-0.5">{selectedStudent.remarks}</p>
											</div>
										)}

										<div className="flex justify-between items-center pt-2">
											{(role === "placement_administrator" || role === "placement_officer") && (
												<Button
													type="button"
													variant="outline"
													size="sm"
													onClick={() => handleArchiveStudent(selectedStudent.id)}
													className="text-red-600 hover:text-red-700 hover:bg-red-50 text-xs gap-1 cursor-pointer"
												>
													<ArchiveBoxIcon className="w-3.5 h-3.5" />
													Archive
												</Button>
											)}

											<div className="flex gap-2">
												{(role === "placement_administrator" || role === "placement_officer") && (
													<Button
														type="button"
														size="sm"
														onClick={() => setIsEditing(true)}
														className="bg-slate-900 text-white hover:bg-slate-800 text-xs gap-1 cursor-pointer"
													>
														<PencilSquareIcon className="w-3.5 h-3.5" />
														Edit
													</Button>
												)}
												<Button
													type="button"
													variant="outline"
													size="sm"
													onClick={() => setSelectedStudent(null)}
													className="text-xs cursor-pointer"
												>
													Close
												</Button>
											</div>
										</div>
									</div>
								)}
							</CardContent>
						</Card>
					</div>
				)}

				{/* 5 Course Filter Tabs */}
				<div className="flex items-center gap-1.5 overflow-x-auto pb-1 border-b border-slate-200/80">
					<button
						type="button"
						disabled={role === "course_coordinator"}
						onClick={() => setSelectedCourse("ALL")}
						className={`px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer shrink-0 ${
							selectedCourse === "ALL"
								? "bg-slate-900 text-white"
								: "bg-slate-100 hover:bg-slate-200 text-slate-600"
						}`}
					>
						All Programmes
					</button>
					{COURSES.map((c) => {
						const isSelected = selectedCourse === c;
						const isLocked = role === "course_coordinator" && user?.course !== c;
						if (isLocked) return null;
						return (
							<button
								key={c}
								type="button"
								onClick={() => setSelectedCourse(c)}
								className={`px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer shrink-0 ${
									isSelected
										? "bg-slate-900 text-white"
										: "bg-slate-100 hover:bg-slate-200 text-slate-600"
								}`}
							>
								{c}
							</button>
						);
					})}
				</div>

				{/* Search Bar */}
				<div className="flex items-center gap-3">
					<div className="relative flex-1 max-w-md">
						<MagnifyingGlassIcon className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
						<Input
							type="text"
							value={searchQuery}
							onChange={(e) => setSearchQuery(e.target.value)}
							placeholder="Search by Placement ID, Name, or Email..."
							className="pl-9 bg-white border-slate-200 text-xs text-slate-900"
						/>
					</div>
				</div>

				{/* Student Table */}
				<Card className="bg-white border-slate-200/80 shadow-xs">
					<CardContent className="p-0">
						<div className="overflow-x-auto">
							<table className="w-full text-left text-xs">
								<thead className="bg-slate-50 border-b border-slate-200/80 text-slate-600 font-medium">
									<tr>
										<th className="px-4 py-3">Placement ID</th>
										<th className="px-4 py-3">Full Name</th>
										<th className="px-4 py-3">Programme</th>
										<th className="px-4 py-3">Batch</th>
										<th className="px-4 py-3">Registration</th>
										<th className="px-4 py-3">Eligibility</th>
										<th className="px-4 py-3">Mobile (Audited Mask)</th>
										<th className="px-4 py-3 text-right">Actions</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-slate-100">
									{isLoading ? (
										<tr>
											<td colSpan={8} className="px-4 py-8 text-center text-slate-400">
												Loading student records from server...
											</td>
										</tr>
									) : students.length === 0 ? (
										<tr>
											<td colSpan={8} className="px-4 py-12 text-center">
												<div className="flex flex-col items-center justify-center">
													<UserGroupIcon className="w-10 h-10 text-slate-300 mb-2" />
													<p className="text-sm font-medium text-slate-700">No student records found</p>
													<p className="text-xs text-slate-400 mt-0.5">
														{selectedCourse !== "ALL"
															? `No records matching filter for ${selectedCourse}`
															: "Backend has no student entries registered currently."}
													</p>
													{(role === "placement_administrator" || role === "placement_officer") && (
														<Button
															size="sm"
															onClick={() => setShowAddModal(true)}
															className="mt-3 bg-slate-900 text-white hover:bg-slate-800 text-xs gap-1.5 cursor-pointer"
														>
															<PlusIcon className="w-3.5 h-3.5" />
															Add First Student
														</Button>
													)}
												</div>
											</td>
										</tr>
									) : (
										students.map((student) => {
											const isPhoneRevealed = !!revealedPhones[student.id];
											return (
												<tr key={student.id} className="hover:bg-slate-50/80 transition">
													<td className="px-4 py-3 font-mono font-medium text-slate-900">
														{student.placement_id}
													</td>
													<td className="px-4 py-3 font-medium text-slate-800">
														{student.name}
													</td>
													<td className="px-4 py-3 text-slate-600">
														{student.course}
													</td>
													<td className="px-4 py-3 font-mono text-slate-600">
														{student.batch}
													</td>
													<td className="px-4 py-3">
														<Badge
															variant="outline"
															className={`text-[10px] font-mono capitalize ${
																student.registration_status === "registered"
																	? "bg-emerald-50 text-emerald-700 border-emerald-200"
																	: "bg-slate-100 text-slate-600 border-slate-200"
															}`}
														>
															{student.registration_status}
														</Badge>
													</td>
													<td className="px-4 py-3">
														<Badge
															variant="outline"
															className={`text-[10px] font-mono capitalize ${
																student.eligibility_status === "eligible"
																	? "bg-emerald-50 text-emerald-700 border-emerald-200"
																	: student.eligibility_status === "ineligible"
																	? "bg-red-50 text-red-700 border-red-200"
																	: "bg-amber-50 text-amber-700 border-amber-200"
															}`}
														>
															{student.eligibility_status.replace("_", " ")}
														</Badge>
													</td>
													<td className="px-4 py-3 font-mono">
														<div className="flex items-center gap-1.5">
															<span>
																{isPhoneRevealed ? student.mobile || "—" : maskPhone(student.mobile)}
															</span>
															{student.mobile && (
																<button
																	type="button"
																	title="Explicit Reveal (Audited)"
																	onClick={() => toggleRevealPhone(student.id)}
																	className="text-slate-400 hover:text-slate-700 cursor-pointer p-0.5"
																>
																	{isPhoneRevealed ? (
																		<EyeSlashIcon className="w-3.5 h-3.5" />
																	) : (
																		<EyeIcon className="w-3.5 h-3.5" />
																	)}
																</button>
															)}
														</div>
													</td>
													<td className="px-4 py-3 text-right">
														<button
															type="button"
															onClick={() => handleOpenDetail(student)}
															className="text-xs text-indigo-600 hover:text-indigo-800 font-medium cursor-pointer"
														>
															View Details &rarr;
														</button>
													</td>
												</tr>
											);
										})
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
