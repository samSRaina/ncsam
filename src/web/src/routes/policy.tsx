import * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { NfsuShell } from "../components/layout/nfsu-shell";
import { api } from "../lib/api-client";
import type {
	Category,
	CompanyRecord,
	EligibilityResult,
	OfferType,
	StudentRecord,
} from "../lib/api-types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { SearchableSelect } from "../components/ui/searchable-select";
import {
	CheckCircleIcon,
	ExclamationCircleIcon,
	ScaleIcon,
	ShieldExclamationIcon,
} from "@heroicons/react/24/outline";

export const Route = createFileRoute("/policy")({
	component: PolicyEngineSimulator,
});

const offerTypeOptions = [
	{ value: "F", label: "Full-Time Employment (FTE)" },
	{ value: "I", label: "Internship Only (I)" },
	{ value: "I+F", label: "Internship + FTE (I+F)" },
];

function PolicyEngineSimulator() {
	const [students, setStudents] = React.useState<StudentRecord[]>([]);
	const [companies, setCompanies] = React.useState<CompanyRecord[]>([]);
	const [studentId, setStudentId] = React.useState<number | "">("");
	const [companyId, setCompanyId] = React.useState<number | "">("");
	const [offerType, setOfferType] = React.useState<OfferType>("F");
	const [targetCtc, setTargetCtc] = React.useState<number | "">("");
	const [result, setResult] = React.useState<EligibilityResult | null>(null);
	const [isLoading, setIsLoading] = React.useState(false);
	const [error, setError] = React.useState<string | null>(null);

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

	const handleCheckEligibility = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!studentId || !companyId) {
			setError("Please select both a student and an organization.");
			return;
		}

		setError(null);
		setResult(null);
		setIsLoading(true);

		try {
			const res = await api.checkEligibility({
				student_id: Number(studentId),
				company_id: Number(companyId),
				offer_type: offerType,
				ctc_lpa: targetCtc === "" ? undefined : Number(targetCtc),
			});
			setResult(res);
		} catch (err: unknown) {
			setError(
				err instanceof Error ? err.message : "Unable to simulate eligibility check.",
			);
		} finally {
			setIsLoading(false);
		}
	};

	// Robust resolution of verdict / allowed state from backend response
	const normalizedVerdict = React.useMemo(() => {
		if (!result) return null;
		const v = String(result.verdict || result.status || "").toUpperCase();
		if (v === "ALLOW" || v === "ALLOWED" || result.allowed === true) {
			return "ALLOW";
		}
		if (v === "REVIEW") {
			return "REVIEW";
		}
		return "BLOCK";
	}, [result]);

	const explanationMessage = React.useMemo(() => {
		if (!result) return "";
		if (result.reasons && result.reasons.length > 0) {
			return result.reasons.map((r) => r.message || r.code).filter(Boolean).join(" • ");
		}
		return (
			result.explanation ||
			result.reason ||
			(normalizedVerdict === "ALLOW"
				? "Opportunity cleared under NFSU placement guidelines."
				: "Policy rule blocks this opportunity.")
		);
	}, [result, normalizedVerdict]);

	return (
		<NfsuShell>
			<div className="space-y-6">
				<div>
					<h1 className="text-xl font-bold text-slate-900 tracking-tight">
						Placement Policy Engine &amp; Eligibility Simulator
					</h1>
					<p className="text-xs text-slate-500 mt-0.5">
						Automated verification of NFSU switching rules, category boundaries (A+, A, B, C), and offer limits.
					</p>
				</div>

				<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
					{/* Simulator Input Form */}
					<div className="lg:col-span-1">
						<Card className="bg-white border-slate-200/80 shadow-xs">
							<CardHeader className="pb-3 border-b border-slate-100">
								<CardTitle className="text-sm font-semibold text-slate-900 flex items-center gap-2">
									<ScaleIcon className="w-4 h-4 text-indigo-600" />
									Opportunity Simulator
								</CardTitle>
								<p className="text-xs text-slate-500">
									Dry-run policy evaluation for a student and target opportunity.
								</p>
							</CardHeader>
							<CardContent className="pt-4">
								{error && (
									<div className="p-3 mb-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs">
										{error}
									</div>
								)}

								<form onSubmit={handleCheckEligibility} className="space-y-3.5">
									<SearchableSelect
										id="sim-student-select"
										label="Select Student"
										required
										placeholder="Search student by name or ID..."
										options={studentOptions}
										value={studentId}
										onChange={(val) => setStudentId(Number(val))}
									/>

									<SearchableSelect
										id="sim-company-select"
										label="Target Organization"
										required
										placeholder="Search organization..."
										options={companyOptions}
										value={companyId}
										onChange={(val) => setCompanyId(Number(val))}
									/>

									<SearchableSelect
										id="sim-offer-type-select"
										label="Role Type"
										required
										options={offerTypeOptions}
										value={offerType}
										onChange={(val) => setOfferType(val as OfferType)}
									/>

									<div className="space-y-1">
										<label htmlFor="sim-ctc-lpa" className="text-xs font-medium text-slate-700 block">
											Target CTC in LPA (Optional for check)
										</label>
										<Input
											id="sim-ctc-lpa"
											type="number"
											step="0.01"
											value={targetCtc}
											onChange={(e) =>
												setTargetCtc(e.target.value ? Number(e.target.value) : "")
											}
											placeholder="e.g. 15.0"
											className="text-xs"
										/>
									</div>

									<Button
										type="submit"
										disabled={isLoading}
										className="w-full bg-slate-900 hover:bg-slate-800 text-white text-xs cursor-pointer"
									>
										{isLoading ? "Evaluating Policy..." : "Run Policy Simulation"}
									</Button>
								</form>
							</CardContent>
						</Card>
					</div>

					{/* Policy Explanation Result Display */}
					<div className="lg:col-span-2 space-y-4">
						{result ? (
							<Card
								className={`border shadow-xs ${
									normalizedVerdict === "ALLOW"
										? "bg-emerald-50/50 border-emerald-200"
										: normalizedVerdict === "REVIEW"
										? "bg-amber-50/50 border-amber-200"
										: "bg-red-50/50 border-red-200"
								}`}
							>
								<CardHeader className="pb-3 border-b border-slate-200/50">
									<div className="flex items-center justify-between">
										<div className="flex items-center gap-2">
											{normalizedVerdict === "ALLOW" ? (
												<CheckCircleIcon className="w-5 h-5 text-emerald-600" />
											) : normalizedVerdict === "REVIEW" ? (
												<ShieldExclamationIcon className="w-5 h-5 text-amber-600" />
											) : (
												<ExclamationCircleIcon className="w-5 h-5 text-red-600" />
											)}
											<CardTitle className="text-sm font-bold uppercase tracking-wider text-slate-900">
												Policy Determination: {normalizedVerdict}
											</CardTitle>
										</div>
										<Badge
											variant="outline"
											className={`text-xs font-mono font-bold capitalize ${
												normalizedVerdict === "ALLOW"
													? "bg-emerald-100 text-emerald-800 border-emerald-300"
													: normalizedVerdict === "REVIEW"
													? "bg-amber-100 text-amber-800 border-amber-300"
													: "bg-red-100 text-red-800 border-red-300"
											}`}
										>
											{normalizedVerdict === "ALLOW" ? "Allowed" : normalizedVerdict === "REVIEW" ? "Review Required" : "Blocked"}
										</Badge>
									</div>
								</CardHeader>
								<CardContent className="pt-4 space-y-3">
									<div>
										<span className="text-xs font-semibold text-slate-700 block">
											Rule Explanation:
										</span>
										<p className="text-sm text-slate-800 mt-1 font-medium leading-relaxed">
											{explanationMessage}
										</p>
									</div>

									{result.reasons && result.reasons.length > 0 && (
										<div className="space-y-1.5 pt-1">
											<span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
												Evaluated Rule Codes:
											</span>
											<div className="space-y-1">
												{result.reasons.map((r, idx) => (
													<div
														key={idx}
														className="text-xs text-slate-700 bg-white/80 p-2 rounded border border-slate-200 flex items-center justify-between font-mono"
													>
														<span>{r.message || r.code}</span>
														<Badge variant="outline" className="text-[10px]">
															{r.code || r.verdict}
														</Badge>
													</div>
												))}
											</div>
										</div>
									)}
								</CardContent>
							</Card>
						) : (
							<Card className="bg-white border-slate-200/80 shadow-xs">
								<CardContent className="p-8 text-center text-slate-500">
									<ScaleIcon className="w-10 h-10 text-slate-300 mx-auto mb-2" />
									<p className="text-sm font-medium text-slate-700">
										Awaiting Simulation Parameters
									</p>
									<p className="text-xs text-slate-400 mt-0.5">
										Select a student and target company from the search dropdowns to dry-run policy evaluation.
									</p>
								</CardContent>
							</Card>
						)}

						{/* Policy Rules Quick Reference */}
						<Card className="bg-white border-slate-200/80 shadow-xs">
							<CardHeader className="pb-2">
								<CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-500">
									NFSU Company Categories &amp; Switching Rules Reference
								</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
									<div className="p-3 rounded-lg bg-slate-50 border border-slate-200/60">
										<div className="font-semibold text-slate-900">Category A+ (≥ ₹16 LPA)</div>
										<p className="text-slate-500 mt-0.5">
											No switching permitted. Students selected in A+ are considered fully placed.
										</p>
									</div>
									<div className="p-3 rounded-lg bg-slate-50 border border-slate-200/60">
										<div className="font-semibold text-slate-900">Category A (₹10–16 LPA)</div>
										<p className="text-slate-500 mt-0.5">
											Switching permitted only to Category A+ opportunities.
										</p>
									</div>
									<div className="p-3 rounded-lg bg-slate-50 border border-slate-200/60">
										<div className="font-semibold text-slate-900">Category B (₹6–10 LPA)</div>
										<p className="text-slate-500 mt-0.5">
											Switching allowed where the new package is at least 1.5× the existing package.
										</p>
									</div>
									<div className="p-3 rounded-lg bg-slate-50 border border-slate-200/60">
										<div className="font-semibold text-slate-900">Category C (&lt; ₹6 LPA)</div>
										<p className="text-slate-500 mt-0.5">
											Eligible for higher-category recruitment drives as per guidelines.
										</p>
									</div>
								</div>
							</CardContent>
						</Card>
					</div>
				</div>
			</div>
		</NfsuShell>
	);
}
