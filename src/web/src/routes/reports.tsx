import * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { NfsuShell } from "../components/layout/nfsu-shell";
import { api } from "../lib/api-client";
import { useAuth } from "../lib/auth-context";
import type { Course, ReportSummary } from "../lib/api-types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { ArrowDownTrayIcon, ChartBarSquareIcon } from "@heroicons/react/24/outline";

export const Route = createFileRoute("/reports")({
	component: ReportsAnalytics,
});

const COURSES: Course[] = [
	"M.Tech CS",
	"M.Tech AIDS",
	"B.Tech-M.Tech CS",
	"M.Sc CS",
	"M.Sc DFIS",
];

function ReportsAnalytics() {
	const { role, user } = useAuth();
	const [summary, setSummary] = React.useState<ReportSummary | null>(null);
	const [isLoading, setIsLoading] = React.useState(true);

	React.useEffect(() => {
		api
			.getSummaryReport()
			.then((data) => setSummary(data))
			.catch(() => setSummary(null))
			.finally(() => setIsLoading(false));
	}, []);

	return (
		<NfsuShell>
			<div className="space-y-6">
				<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
					<div>
						<h1 className="text-xl font-bold text-slate-900 tracking-tight">
							Course-Wise Placement Analytics & Governance Reports
						</h1>
						<p className="text-xs text-slate-500 mt-0.5">
							Placement benchmarks with strict segregation of Monthly Stipend vs Annual FTE CTC.
						</p>
					</div>

					<a
						href={api.getExportUrl()}
						download
						className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-900 text-white hover:bg-slate-800 transition shadow-xs"
					>
						<ArrowDownTrayIcon className="w-4 h-4" />
						Download Official Report (CSV)
					</a>
				</div>

				{/* Strict Reporting Rules Callout */}
				<div className="p-3.5 bg-blue-50/60 border border-blue-200 rounded-xl text-xs text-blue-900 flex flex-col md:flex-row gap-3 md:items-center justify-between">
					<div className="flex items-center gap-2 font-medium">
						<span className="w-2 h-2 rounded-full bg-blue-600" />
						<span>
							Reporting Rule: <strong>Stipends</strong> and <strong>FTE CTCs</strong> are calculated and presented on independent scales.
						</span>
					</div>
					<Badge variant="outline" className="border-blue-300 text-blue-800 bg-blue-100 font-mono text-[11px] self-start md:self-auto">
						Audit Standard Compliant
					</Badge>
				</div>

				{/* University Totals Summary Cards */}
				<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
					<Card className="bg-white border-slate-200/80 shadow-xs">
						<CardHeader className="pb-2">
							<CardTitle className="text-xs text-slate-500">Total Registered Students</CardTitle>
						</CardHeader>
						<CardContent>
							<div className="text-2xl font-bold font-mono text-slate-900">
								{summary?.students?.registered ?? "—"}
							</div>
							<p className="text-[11px] text-slate-400 mt-1">
								Total pool: {summary?.students?.total ?? "—"} | Eligible: {summary?.students?.eligible ?? "—"}
							</p>
						</CardContent>
					</Card>

					<Card className="bg-white border-slate-200/80 shadow-xs">
						<CardHeader className="pb-2">
							<CardTitle className="text-xs text-slate-500">FTE Packages Recorded</CardTitle>
						</CardHeader>
						<CardContent>
							<div className="text-2xl font-bold font-mono text-blue-700">
								{summary?.fte_ctc_lpa?.highest != null ? `₹${summary.fte_ctc_lpa.highest} LPA` : "—"}
							</div>
							<p className="text-[11px] text-slate-400 mt-1">
								Highest package | Offers count: {summary?.fte_ctc_lpa?.count ?? 0}
							</p>
						</CardContent>
					</Card>

					<Card className="bg-white border-slate-200/80 shadow-xs">
						<CardHeader className="pb-2">
							<CardTitle className="text-xs text-slate-500">Internship Stipends</CardTitle>
						</CardHeader>
						<CardContent>
							<div className="text-2xl font-bold font-mono text-purple-700">
								{summary?.internship_stipend?.highest != null ? `₹${summary.internship_stipend.highest}` : "—"}
							</div>
							<p className="text-[11px] text-slate-400 mt-1">
								Highest stipend | Offers count: {summary?.internship_stipend?.count ?? 0}
							</p>
						</CardContent>
					</Card>
				</div>

				{/* 5 Programmes Comprehensive Breakdown */}
				<Card className="bg-white border-slate-200/80 shadow-xs">
					<CardHeader className="pb-3 border-b border-slate-100">
						<CardTitle className="text-sm font-semibold text-slate-900">
							Programme-Wise Outcome Matrix
						</CardTitle>
					</CardHeader>
					<CardContent className="p-0">
						<div className="overflow-x-auto">
							<table className="w-full text-left text-xs">
								<thead className="bg-slate-50 border-b border-slate-200/80 text-slate-600 font-medium">
									<tr>
										<th className="px-4 py-3">Academic Programme</th>
										<th className="px-4 py-3">Total Students</th>
										<th className="px-4 py-3">Registered</th>
										<th className="px-4 py-3">Unique Placed</th>
										<th className="px-4 py-3">Total Offers</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-slate-100">
									{COURSES.map((course) => {
										// Coordinator scope filter
										if (role === "course_coordinator" && user?.course && user.course !== course) {
											return null;
										}
										const data = summary?.by_course?.[course];
										return (
											<tr key={course} className="hover:bg-slate-50/80 transition">
												<td className="px-4 py-3 font-medium text-slate-900">
													{course}
												</td>
												<td className="px-4 py-3 font-mono text-slate-600">
													{data?.students ?? "—"}
												</td>
												<td className="px-4 py-3 font-mono text-slate-600">
													{data?.registered ?? "—"}
												</td>
												<td className="px-4 py-3 font-mono font-semibold text-emerald-700">
													{data?.placed_unique ?? "—"}
												</td>
												<td className="px-4 py-3 font-mono text-slate-700">
													{data?.offers_total ?? "—"}
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
