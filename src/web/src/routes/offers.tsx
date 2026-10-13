import * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { NfsuShell } from "../components/layout/nfsu-shell";
import { api } from "../lib/api-client";
import { useAuth } from "../lib/auth-context";
import type {
	Acceptance,
	CompanyRecord,
	Joining,
	OfferRecord,
	OfferType,
	OfferUpdate,
	PPOStatus,
	StipendPeriodType,
	StudentRecord,
} from "../lib/api-types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { SearchableSelect } from "../components/ui/searchable-select";
import {
	BanknotesIcon,
	ClockIcon,
	DocumentCheckIcon,
	PencilSquareIcon,
	PlusIcon,
	ShieldCheckIcon,
	XMarkIcon,
} from "@heroicons/react/24/outline";

export const Route = createFileRoute("/offers")({
	component: OffersLedger,
});

const offerTypeOptions = [
	{ value: "F", label: "Full-Time Employment (FTE)", description: "Requires Annual CTC in LPA" },
	{ value: "I", label: "Internship Only (I)", description: "Requires Monthly/Weekly Stipend" },
	{ value: "I+F", label: "Internship + FTE (I+F)", description: "Requires both Stipend and CTC" },
];

const stipendPeriodOptions = [
	{ value: "monthly", label: "Monthly" },
	{ value: "weekly", label: "Weekly" },
	{ value: "total", label: "Total Lump Sum" },
];

const acceptanceOptions = [
	{ value: "pending", label: "Pending" },
	{ value: "accepted", label: "Accepted" },
	{ value: "declined", label: "Declined" },
	{ value: "expired", label: "Expired" },
];

const joiningOptions = [
	{ value: "pending", label: "Pending" },
	{ value: "joined", label: "Joined" },
	{ value: "not_joined", label: "Not Joined" },
];

const ppoOptions = [
	{ value: "not_applicable", label: "Not Applicable" },
	{ value: "pending", label: "Pending" },
	{ value: "offered", label: "Offered" },
	{ value: "accepted", label: "Accepted" },
	{ value: "declined", label: "Declined" },
];

function OffersLedger() {
	const { role } = useAuth();
	const [offers, setOffers] = React.useState<OfferRecord[]>([]);
	const [companies, setCompanies] = React.useState<CompanyRecord[]>([]);
	const [students, setStudents] = React.useState<StudentRecord[]>([]);
	const [isLoading, setIsLoading] = React.useState(true);
	const [showCreateModal, setShowCreateModal] = React.useState(false);

	// New Offer Form State
	const [studentId, setStudentId] = React.useState<number | "">("");
	const [companyId, setCompanyId] = React.useState<number | "">("");
	const [offerType, setOfferType] = React.useState<OfferType>("F");
	const [ctcLpa, setCtcLpa] = React.useState<number | "">("");
	const [stipendAmount, setStipendAmount] = React.useState<number | "">("");
	const [stipendPeriod, setStipendPeriod] = React.useState<StipendPeriodType>("monthly");
	const [offerDate, setOfferDate] = React.useState(new Date().toISOString());
	const [offCampus, setOffCampus] = React.useState(false);
	const [remarks, setRemarks] = React.useState("");
	const [overrideReason, setOverrideReason] = React.useState("");
	const [isSubmitting, setIsSubmitting] = React.useState(false);
	const [formError, setFormError] = React.useState<string | null>(null);

	// Edit Offer State
	const [editingOffer, setEditingOffer] = React.useState<OfferRecord | null>(null);
	const [editAcceptance, setEditAcceptance] = React.useState<Acceptance>("pending");
	const [editJoining, setEditJoining] = React.useState<Joining>("pending");
	const [editPpo, setEditPpo] = React.useState<PPOStatus>("not_applicable");
	const [editRemarks, setEditRemarks] = React.useState("");

	const loadData = React.useCallback(() => {
		setIsLoading(true);
		Promise.all([
			api.listOffers(),
			api.listCompanies(),
			api.listStudents({ limit: 100 }),
		])
			.then(([offersRes, companiesRes, studentsRes]) => {
				setOffers(offersRes);
				setCompanies(companiesRes);
				setStudents(studentsRes);
			})
			.catch(() => {
				setOffers([]);
				setCompanies([]);
				setStudents([]);
			})
			.finally(() => {
				setIsLoading(false);
			});
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

	const handleCreateOffer = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!studentId || !companyId) {
			setFormError("Please select both a student and an organization.");
			return;
		}

		setFormError(null);
		setIsSubmitting(true);

		try {
			await api.createOffer({
				student_id: Number(studentId),
				company_id: Number(companyId),
				offer_type: offerType,
				ctc_lpa: ctcLpa === "" ? null : Number(ctcLpa),
				stipend_amount: stipendAmount === "" ? null : Number(stipendAmount),
				stipend_period: (offerType === "I" || offerType === "I+F") ? stipendPeriod : null,
				offer_date: new Date().toISOString(),
				off_campus: offCampus,
				remarks: remarks.trim() ? remarks.trim() : null,
				override_reason: overrideReason.trim() ? overrideReason.trim() : null,
			});
			setShowCreateModal(false);
			setStudentId("");
			setCompanyId("");
			setCtcLpa("");
			setStipendAmount("");
			setRemarks("");
			setOverrideReason("");
			loadData();
		} catch (err: unknown) {
			setFormError(
				err instanceof Error ? err.message : "Failed to record offer. Policy check blocked.",
			);
		} finally {
			setIsSubmitting(false);
		}
	};

	const handleOpenEdit = (offer: OfferRecord) => {
		setEditingOffer(offer);
		setEditAcceptance(offer.acceptance_status);
		setEditJoining(offer.joining_status);
		setEditPpo(offer.ppo_status);
		setEditRemarks(offer.remarks || "");
	};

	const handleUpdateOffer = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!editingOffer) return;
		setIsSubmitting(true);
		try {
			await api.updateOffer(editingOffer.id, {
				acceptance_status: editAcceptance,
				joining_status: editJoining,
				ppo_status: editPpo,
				remarks: editRemarks.trim() ? editRemarks.trim() : null,
			});
			setEditingOffer(null);
			loadData();
		} catch (err: unknown) {
			alert(err instanceof Error ? err.message : "Failed to update offer status.");
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<NfsuShell>
			<div className="space-y-6">
				<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
					<div>
						<h1 className="text-xl font-bold text-slate-900 tracking-tight">
							Offers & Pre-Placement Offers (PPOs)
						</h1>
						<p className="text-xs text-slate-500 mt-0.5">
							Maintain placement ledger, compensation breakdowns, and deadline compliance.
						</p>
					</div>

					{(role === "placement_administrator" || role === "placement_officer") && (
						<Button
							size="sm"
							onClick={() => setShowCreateModal(true)}
							className="bg-slate-900 text-white hover:bg-slate-800 gap-1.5 text-xs cursor-pointer"
						>
							<PlusIcon className="w-4 h-4" />
							Record Offer
						</Button>
					)}
				</div>

				{/* Create Offer Modal */}
				{showCreateModal && (
					<div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
						<Card className="max-w-lg w-full bg-white border-slate-200 shadow-2xl max-h-[90vh] flex flex-col">
							<CardHeader className="pb-3 border-b border-slate-100 flex flex-row items-center justify-between">
								<div>
									<CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
										<DocumentCheckIcon className="w-5 h-5 text-indigo-600" />
										Record Placement Offer
									</CardTitle>
									<p className="text-xs text-slate-500 mt-0.5">
										Dynamic validation checks NFSU switching rules and tier limits.
									</p>
								</div>
								<button
									type="button"
									onClick={() => setShowCreateModal(false)}
									className="text-slate-400 hover:text-slate-600 p-1"
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
								<form onSubmit={handleCreateOffer} className="space-y-3.5">
									<SearchableSelect
										id="select-offer-student"
										label="Select Candidate Student"
										required
										placeholder="Search student by name or placement ID..."
										options={studentOptions}
										value={studentId}
										onChange={(val) => setStudentId(Number(val))}
									/>

									<SearchableSelect
										id="select-offer-company"
										label="Recruiting Organization"
										required
										placeholder="Search company or category..."
										options={companyOptions}
										value={companyId}
										onChange={(val) => setCompanyId(Number(val))}
									/>

									<SearchableSelect
										id="select-offer-type"
										label="Offer Classification"
										required
										options={offerTypeOptions}
										value={offerType}
										onChange={(val) => setOfferType(val as OfferType)}
									/>

									{/* Render Stipend if I or I+F */}
									{(offerType === "I" || offerType === "I+F") && (
										<div className="grid grid-cols-2 gap-3 p-3 bg-purple-50/60 rounded-lg border border-purple-100">
											<div className="space-y-1">
												<label htmlFor="offer-stipend-val" className="text-xs font-medium text-purple-900 block">
													Internship Stipend (₹) *
												</label>
												<Input
													id="offer-stipend-val"
													type="number"
													required
													value={stipendAmount}
													onChange={(e) =>
														setStipendAmount(
															e.target.value ? Number(e.target.value) : "",
														)
													}
													placeholder="e.g. 40000"
													className="text-xs bg-white"
												/>
											</div>
											<SearchableSelect
												id="offer-stipend-period"
												label="Stipend Period"
												options={stipendPeriodOptions}
												value={stipendPeriod}
												onChange={(val) => setStipendPeriod(val as StipendPeriodType)}
											/>
										</div>
									)}

									{/* Render CTC if F or I+F */}
									{(offerType === "F" || offerType === "I+F") && (
										<div className="p-3 bg-blue-50/60 rounded-lg border border-blue-100 space-y-1">
											<label htmlFor="offer-ctc-val" className="text-xs font-medium text-blue-900 block">
												Annual FTE CTC (LPA) *
											</label>
											<Input
												id="offer-ctc-val"
												type="number"
												step="0.01"
												required
												value={ctcLpa}
												onChange={(e) =>
													setCtcLpa(e.target.value ? Number(e.target.value) : "")
												}
												placeholder="e.g. 18.50"
												className="text-xs bg-white"
											/>
											<span className="text-[10px] text-blue-700">
												Annual fixed + variable package strictly in LPA
											</span>
										</div>
									)}

									<div className="flex items-center gap-2 pt-1">
										<input
											id="offCampus"
											type="checkbox"
											checked={offCampus}
											onChange={(e) => setOffCampus(e.target.checked)}
											className="rounded border-slate-300 text-indigo-600"
										/>
										<label htmlFor="offCampus" className="text-xs text-slate-700 cursor-pointer">
											Off-campus placement offer
										</label>
									</div>

									<div className="space-y-1">
										<label htmlFor="offer-remarks-field" className="text-xs font-medium text-slate-700 block">Remarks</label>
										<Input
											id="offer-remarks-field"
											type="text"
											value={remarks}
											onChange={(e) => setRemarks(e.target.value)}
											placeholder="Optional notes or offer designation"
											className="text-xs"
										/>
									</div>

									<div className="space-y-1">
										<label htmlFor="offer-override-field" className="text-xs font-medium text-slate-700 block">
											Policy Override Reason (If Flagged)
										</label>
										<Input
											id="offer-override-field"
											type="text"
											value={overrideReason}
											onChange={(e) => setOverrideReason(e.target.value)}
											placeholder="Required only if policy requires exceptional clearance"
											className="text-xs"
										/>
									</div>

									<div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
										<Button
											type="button"
											variant="outline"
											size="sm"
											onClick={() => setShowCreateModal(false)}
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
											{isSubmitting ? "Validating Policy..." : "Confirm & Record"}
										</Button>
									</div>
								</form>
							</CardContent>
						</Card>
					</div>
				)}

				{/* Edit Offer Modal */}
				{editingOffer && (
					<div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
						<Card className="max-w-md w-full bg-white border-slate-200 shadow-2xl">
							<CardHeader className="pb-3 border-b border-slate-100 flex flex-row items-center justify-between">
								<CardTitle className="text-base font-bold text-slate-900">
									Update Offer Status
								</CardTitle>
								<button
									type="button"
									onClick={() => setEditingOffer(null)}
									className="text-slate-400 hover:text-slate-600 p-1"
								>
									<XMarkIcon className="w-5 h-5" />
								</button>
							</CardHeader>
							<CardContent className="pt-4">
								<form onSubmit={handleUpdateOffer} className="space-y-3.5">
									<SearchableSelect
										id="edit-offer-acceptance"
										label="Acceptance Status"
										options={acceptanceOptions}
										value={editAcceptance}
										onChange={(val) => setEditAcceptance(val as Acceptance)}
									/>

									<SearchableSelect
										id="edit-offer-joining"
										label="Joining Status"
										options={joiningOptions}
										value={editJoining}
										onChange={(val) => setEditJoining(val as Joining)}
									/>

									<SearchableSelect
										id="edit-offer-ppo"
										label="Pre-Placement Offer (PPO) Status"
										options={ppoOptions}
										value={editPpo}
										onChange={(val) => setEditPpo(val as PPOStatus)}
									/>

									<div className="space-y-1">
										<label htmlFor="edit-offer-remarks" className="text-xs font-medium text-slate-700 block">Remarks</label>
										<Input
											id="edit-offer-remarks"
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
											onClick={() => setEditingOffer(null)}
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
											Save Update
										</Button>
									</div>
								</form>
							</CardContent>
						</Card>
					</div>
				)}

				{/* Offers Ledger Table */}
				<Card className="bg-white border-slate-200/80 shadow-xs">
					<CardContent className="p-0">
						<div className="overflow-x-auto">
							<table className="w-full text-left text-xs">
								<thead className="bg-slate-50 border-b border-slate-200/80 text-slate-600 font-medium">
									<tr>
										<th className="px-4 py-3">Student ID</th>
										<th className="px-4 py-3">Company</th>
										<th className="px-4 py-3">Type</th>
										<th className="px-4 py-3">FTE CTC (Annual)</th>
										<th className="px-4 py-3">Stipend</th>
										<th className="px-4 py-3">Offer Date</th>
										<th className="px-4 py-3">Acceptance</th>
										<th className="px-4 py-3">Joining</th>
										<th className="px-4 py-3">PPO Status</th>
										<th className="px-4 py-3 text-right">Actions</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-slate-100">
									{isLoading ? (
										<tr>
											<td colSpan={10} className="px-4 py-8 text-center text-slate-400">
												Loading offers ledger...
											</td>
										</tr>
									) : offers.length === 0 ? (
										<tr>
											<td colSpan={10} className="px-4 py-12 text-center text-slate-500">
												<DocumentCheckIcon className="w-10 h-10 text-slate-300 mx-auto mb-2" />
												<p className="text-sm font-medium text-slate-700">No offers recorded yet</p>
												<p className="text-xs text-slate-400 mt-0.5">
													Recorded offers and PPO conversions will appear in this ledger.
												</p>
												{(role === "placement_administrator" || role === "placement_officer") && (
													<Button
														size="sm"
														onClick={() => setShowCreateModal(true)}
														className="mt-3 bg-slate-900 text-white hover:bg-slate-800 text-xs gap-1.5 cursor-pointer"
													>
														<PlusIcon className="w-3.5 h-3.5" />
														Record First Offer
													</Button>
												)}
											</td>
										</tr>
									) : (
										offers.map((offer) => (
											<tr key={offer.id} className="hover:bg-slate-50/80 transition">
												<td className="px-4 py-3 font-mono font-medium text-slate-900">
													#{offer.student_id}
												</td>
												<td className="px-4 py-3 font-medium text-slate-800">
													{offer.company_name || `Company #${offer.company_id}`}
												</td>
												<td className="px-4 py-3">
													<Badge variant="outline" className="text-[10px] font-mono">
														{offer.offer_type}
													</Badge>
												</td>
												<td className="px-4 py-3 font-mono text-blue-700 font-semibold">
													{offer.ctc_lpa ? `₹${offer.ctc_lpa} LPA` : "—"}
												</td>
												<td className="px-4 py-3 font-mono text-purple-700">
													{offer.stipend_amount
														? `₹${offer.stipend_amount} / ${offer.stipend_period || "mo"}`
														: "—"}
												</td>
												<td className="px-4 py-3 font-mono text-slate-600">
													{offer.offer_date?.slice(0, 10) || "—"}
												</td>
												<td className="px-4 py-3 capitalize">
													<Badge
														variant="outline"
														className={`text-[10px] ${
															offer.acceptance_status === "accepted"
																? "bg-emerald-50 text-emerald-700 border-emerald-200"
																: offer.acceptance_status === "expired"
																? "bg-red-50 text-red-700 border-red-200"
																: "bg-amber-50 text-amber-700 border-amber-200"
														}`}
													>
														{offer.acceptance_status}
													</Badge>
												</td>
												<td className="px-4 py-3 capitalize text-slate-600">
													{offer.joining_status}
												</td>
												<td className="px-4 py-3 capitalize text-slate-600">
													{offer.ppo_status.replace("_", " ")}
												</td>
												<td className="px-4 py-3 text-right">
													{(role === "placement_administrator" || role === "placement_officer") && (
														<button
															type="button"
															onClick={() => handleOpenEdit(offer)}
															className="text-xs text-indigo-600 hover:text-indigo-800 font-medium cursor-pointer"
														>
															Edit &rarr;
														</button>
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
