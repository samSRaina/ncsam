import * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { NfsuShell } from "../components/layout/nfsu-shell";
import { api } from "../lib/api-client";
import { useAuth } from "../lib/auth-context";
import type { Category, CompanyIn, CompanyRecord } from "../lib/api-types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { SearchableSelect } from "../components/ui/searchable-select";
import {
	BriefcaseIcon,
	BuildingOffice2Icon,
	PlusIcon,
	XMarkIcon,
} from "@heroicons/react/24/outline";

export const Route = createFileRoute("/recruitment")({
	component: RecruitmentModule,
});

const categoryOptions = [
	{ value: "A+", label: "Category A+ (≥ ₹16 LPA)", description: "Terminal tier; no further switching permitted" },
	{ value: "A", label: "Category A (₹10–16 LPA)", description: "Switching allowed only to Category A+" },
	{ value: "B", label: "Category B (₹6–10 LPA)", description: "Switching allowed at ≥ 1.5× package multiplier" },
	{ value: "C", label: "Category C (< ₹6 LPA)", description: "Eligible for higher tiers per placement guidelines" },
];

function RecruitmentModule() {
	const { role } = useAuth();
	const [companies, setCompanies] = React.useState<CompanyRecord[]>([]);
	const [isLoading, setIsLoading] = React.useState(true);
	const [showAddModal, setShowAddModal] = React.useState(false);
	const [name, setName] = React.useState("");
	const [category, setCategory] = React.useState<Category>("B");
	const [isSubmitting, setIsSubmitting] = React.useState(false);
	const [formError, setFormError] = React.useState<string | null>(null);

	const loadCompanies = React.useCallback(() => {
		setIsLoading(true);
		api
			.listCompanies()
			.then((data) => setCompanies(data))
			.catch(() => setCompanies([]))
			.finally(() => setIsLoading(false));
	}, []);

	React.useEffect(() => {
		loadCompanies();
	}, [loadCompanies]);

	const handleAddCompany = async (e: React.FormEvent) => {
		e.preventDefault();
		setFormError(null);
		setIsSubmitting(true);
		try {
			await api.createCompany({ name, category });
			setShowAddModal(false);
			setName("");
			loadCompanies();
		} catch (err: unknown) {
			setFormError(err instanceof Error ? err.message : "Failed to register recruiting organization.");
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
							Recruiting Organizations & Category Tiers
						</h1>
						<p className="text-xs text-slate-500 mt-0.5">
							Manage active employers, tier classifications (A+, A, B, C), and recruitment drives.
						</p>
					</div>

					{(role === "placement_administrator" || role === "placement_officer") && (
						<Button
							size="sm"
							onClick={() => setShowAddModal(true)}
							className="bg-slate-900 text-white hover:bg-slate-800 gap-1.5 text-xs cursor-pointer"
						>
							<PlusIcon className="w-4 h-4" />
							Register Organization
						</Button>
					)}
				</div>

				{showAddModal && (
					<div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
						<Card className="max-w-md w-full bg-white border-slate-200 shadow-2xl">
							<CardHeader className="pb-3 border-b border-slate-100 flex flex-row items-center justify-between">
								<CardTitle className="text-base font-bold text-slate-900">
									Register Recruiting Organization
								</CardTitle>
								<button
									type="button"
									onClick={() => setShowAddModal(false)}
									className="text-slate-400 hover:text-slate-600 p-1"
								>
									<XMarkIcon className="w-5 h-5" />
								</button>
							</CardHeader>
							<CardContent className="pt-4">
								{formError && (
									<div className="p-3 mb-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs">
										{formError}
									</div>
								)}
								<form onSubmit={handleAddCompany} className="space-y-4">
									<div className="space-y-1">
										<label htmlFor="company-name-val" className="text-xs font-medium text-slate-700 block">
											Organization Name *
										</label>
										<Input
											id="company-name-val"
											type="text"
											required
											value={name}
											onChange={(e) => setName(e.target.value)}
											placeholder="e.g. CyberDefense Technologies"
											className="text-xs"
										/>
									</div>

									<SearchableSelect
										id="company-cat-select"
										label="Assigned Policy Category Tier"
										required
										options={categoryOptions}
										value={category}
										onChange={(val) => setCategory(val as Category)}
									/>

									<div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
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
											Save Organization
										</Button>
									</div>
								</form>
							</CardContent>
						</Card>
					</div>
				)}

				<Card className="bg-white border-slate-200/80 shadow-xs">
					<CardContent className="p-0">
						<div className="overflow-x-auto">
							<table className="w-full text-left text-xs">
								<thead className="bg-slate-50 border-b border-slate-200/80 text-slate-600 font-medium">
									<tr>
										<th className="px-4 py-3">ID</th>
										<th className="px-4 py-3">Organization Name</th>
										<th className="px-4 py-3">Category Tier</th>
										<th className="px-4 py-3">Switching Rule Constraint</th>
										<th className="px-4 py-3 text-right">Actions</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-slate-100">
									{isLoading ? (
										<tr>
											<td colSpan={5} className="px-4 py-8 text-center text-slate-400">
												Loading companies...
											</td>
										</tr>
									) : companies.length === 0 ? (
										<tr>
											<td colSpan={5} className="px-4 py-12 text-center text-slate-500">
												<BuildingOffice2Icon className="w-10 h-10 text-slate-300 mx-auto mb-2" />
												<p className="text-sm font-medium text-slate-700">No organizations registered yet</p>
												<p className="text-xs text-slate-400 mt-0.5">
													Add participating employers to link drives and offers.
												</p>
												{(role === "placement_administrator" || role === "placement_officer") && (
													<Button
														size="sm"
														onClick={() => setShowAddModal(true)}
														className="mt-3 bg-slate-900 text-white hover:bg-slate-800 text-xs gap-1.5 cursor-pointer"
													>
														<PlusIcon className="w-3.5 h-3.5" />
														Register First Organization
													</Button>
												)}
											</td>
										</tr>
									) : (
										companies.map((comp) => (
											<tr key={comp.id} className="hover:bg-slate-50/80 transition">
												<td className="px-4 py-3 font-mono text-slate-500">
													#{comp.id}
												</td>
												<td className="px-4 py-3 font-medium text-slate-900">
													{comp.name}
												</td>
												<td className="px-4 py-3">
													<Badge
														variant="outline"
														className={`text-[10px] font-mono font-bold ${
															comp.category === "A+"
																? "bg-purple-50 text-purple-700 border-purple-200"
																: comp.category === "A"
																? "bg-blue-50 text-blue-700 border-blue-200"
																: comp.category === "B"
																? "bg-emerald-50 text-emerald-700 border-emerald-200"
																: "bg-slate-100 text-slate-600 border-slate-200"
														}`}
													>
														Category {comp.category}
													</Badge>
												</td>
												<td className="px-4 py-3 text-slate-600">
													{comp.category === "A+" && "Terminal tier; no subsequent switching allowed."}
													{comp.category === "A" && "Switching permitted only to Category A+."}
													{comp.category === "B" && "Switching permitted at ≥ 1.5× package multiplier."}
													{comp.category === "C" && "Eligible for higher tiers per guidelines."}
												</td>
												<td className="px-4 py-3 text-right">
													<span className="text-xs text-slate-400">
														Active Tier
													</span>
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
