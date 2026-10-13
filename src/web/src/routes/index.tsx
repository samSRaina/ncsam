import * as React from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { NfsuShell } from "../components/layout/nfsu-shell";
import { api } from "../lib/api-client";
import { useAuth } from "../lib/auth-context";
import type { ReportSummary } from "../lib/api-types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import {
	AcademicCapIcon,
	BanknotesIcon,
	BriefcaseIcon,
	ClockIcon,
	ScaleIcon,
	UserGroupIcon,
} from "@heroicons/react/24/outline";

export const Route = createFileRoute("/")({
	component: DashboardOverview,
});

function DashboardOverview() {
	const { role, user } = useAuth();
	const [summary, setSummary] = React.useState<ReportSummary | null>(null);
	const [isLoading, setIsLoading] = React.useState(true);

	React.useEffect(() => {
		let isMounted = true;
		setIsLoading(true);
		api
			.getSummaryReport()
			.then((data) => {
				if (isMounted) {
					setSummary(data);
				}
			})
			.catch(() => {
				if (isMounted) {
					setSummary(null);
				}
			})
			.finally(() => {
				if (isMounted) setIsLoading(false);
			});

		return () => {
			isMounted = false;
		};
	}, []);

	return (
		<NfsuShell>
			<div className="space-y-6">
				{/* Top Hero Banner */}
				<div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
					<div>
						<div className="flex items-center gap-2">
							<h1 className="text-xl font-bold text-slate-900 tracking-tight">
								Placement Session Overview
							</h1>
							<Badge variant="outline" className="text-xs bg-indigo-50 border-indigo-200 text-indigo-700">
								NFSU 2026–27
							</Badge>
						</div>
						<p className="text-xs text-slate-500 mt-1">
							Course-wise recruitment statistics and policy compliance under NFSU Student Placement Guidelines.
						</p>
					</div>

					<div className="flex items-center gap-2">
						<Link
							to="/students"
							className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-900 text-white hover:bg-slate-800 transition"
						>
							<UserGroupIcon className="w-4 h-4" />
							View Students
						</Link>
						<Link
							to="/policy"
							className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition"
						>
							<ScaleIcon className="w-4 h-4" />
							Eligibility Simulator
						</Link>
					</div>
				</div>

				{/* Rule Adherence Metric: Unique Placed vs Total Offers (Side by Side) */}
				<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
					{/* Card 1: Unique Placed */}
					<Card className="bg-white border-slate-200/80 shadow-xs">
						<CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
							<CardTitle className="text-xs font-medium text-slate-500">
								Unique Placed Students
							</CardTitle>
							<AcademicCapIcon className="w-4 h-4 text-emerald-600" />
						</CardHeader>
						<CardContent>
							<div className="text-2xl font-bold font-mono text-slate-900">
								{summary?.students?.placed_unique ?? "—"}
							</div>
							<p className="text-[11px] text-slate-400 mt-1">
								Total registered: {summary?.students?.registered ?? "—"} | Unplaced: {summary?.students?.unplaced ?? "—"}
							</p>
						</CardContent>
					</Card>

					{/* Card 2: Total Offers */}
					<Card className="bg-white border-slate-200/80 shadow-xs">
						<CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
							<CardTitle className="text-xs font-medium text-slate-500">
								Total Offers Extended
							</CardTitle>
							<BriefcaseIcon className="w-4 h-4 text-indigo-600" />
						</CardHeader>
						<CardContent>
							<div className="text-2xl font-bold font-mono text-slate-900">
								{summary?.offers_total ?? "—"}
							</div>
							<p className="text-[11px] text-slate-400 mt-1">
								Aggregate offers across I, F, & I+F
							</p>
						</CardContent>
					</Card>

					{/* Card 3: FTE Package CTC (Separated) */}
					<Card className="bg-white border-slate-200/80 shadow-xs">
						<CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
							<CardTitle className="text-xs font-medium text-slate-500">
								Highest FTE Package
							</CardTitle>
							<BanknotesIcon className="w-4 h-4 text-blue-600" />
						</CardHeader>
						<CardContent>
							<div className="text-2xl font-bold font-mono text-slate-900">
								{summary?.fte_ctc_lpa?.highest != null ? `₹${summary.fte_ctc_lpa.highest} LPA` : "—"}
							</div>
							<p className="text-[11px] text-slate-400 mt-1">
								Avg: {summary?.fte_ctc_lpa?.average != null ? `₹${summary.fte_ctc_lpa.average} LPA` : "—"} | Count: {summary?.fte_ctc_lpa?.count ?? 0}
							</p>
						</CardContent>
					</Card>

					{/* Card 4: Highest Internship Stipend (Separated) */}
					<Card className="bg-white border-slate-200/80 shadow-xs">
						<CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
							<CardTitle className="text-xs font-medium text-slate-500">
								Highest Stipend
							</CardTitle>
							<ClockIcon className="w-4 h-4 text-purple-600" />
						</CardHeader>
						<CardContent>
							<div className="text-2xl font-bold font-mono text-slate-900">
								{summary?.internship_stipend?.highest != null ? `₹${summary.internship_stipend.highest}` : "—"}
							</div>
							<p className="text-[11px] text-slate-400 mt-1">
								Avg: {summary?.internship_stipend?.average != null ? `₹${summary.internship_stipend.average}` : "—"} | Count: {summary?.internship_stipend?.count ?? 0}
							</p>
						</CardContent>
					</Card>
				</div>

				{/* 5 Programmes Course-Wise Scaffolding Table */}
				<Card className="bg-white border-slate-200/80 shadow-xs">
					<CardHeader className="pb-3 border-b border-slate-100">
						<div className="flex items-center justify-between">
							<div>
								<CardTitle className="text-sm font-semibold text-slate-900">
									Course-Wise Placement Ledger
								</CardTitle>
								<p className="text-xs text-slate-500 mt-0.5">
									All 5 mandatory academic programmes under NFSU placement guidelines.
								</p>
							</div>
							<Badge variant="outline" className="text-[11px] font-mono text-slate-500">
								5 Programmes
							</Badge>
						</div>
					</CardHeader>
					<CardContent className="p-0">
						<div className="overflow-x-auto">
							<table className="w-full text-left text-xs">
								<thead className="bg-slate-50 border-b border-slate-200/80 text-slate-600 font-medium">
									<tr>
										<th className="px-4 py-3">Programme</th>
										<th className="px-4 py-3">Total Students</th>
										<th className="px-4 py-3">Registered</th>
										<th className="px-4 py-3">Placed Unique</th>
										<th className="px-4 py-3">Offers Total</th>
										<th className="px-4 py-3 text-right">Actions</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-slate-100">
									{[
										"M.Tech CS",
										"M.Tech AIDS",
										"B.Tech-M.Tech CS",
										"M.Sc CS",
										"M.Sc DFIS",
									].map((course) => {
										const courseData = summary?.by_course?.[course];
										return (
											<tr key={course} className="hover:bg-slate-50/80 transition">
												<td className="px-4 py-3 font-medium text-slate-900">
													{course}
												</td>
												<td className="px-4 py-3 font-mono text-slate-600">
													{courseData?.students ?? "—"}
												</td>
												<td className="px-4 py-3 font-mono text-slate-600">
													{courseData?.registered ?? "—"}
												</td>
												<td className="px-4 py-3 font-mono font-semibold text-emerald-700">
													{courseData?.placed_unique ?? "—"}
												</td>
												<td className="px-4 py-3 font-mono text-slate-700">
													{courseData?.offers_total ?? "—"}
												</td>
												<td className="px-4 py-3 text-right">
													<Link
														to="/students"
														search={{ course }}
														className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
													>
														Filter &rarr;
													</Link>
												</td>
											</tr>
										);
									})}
								</tbody>
							</table>
						</div>
					</CardContent>
				</Card>
			</div>
		</NfsuShell>
	);
}
