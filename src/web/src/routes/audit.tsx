import * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { NfsuShell } from "../components/layout/nfsu-shell";
import { api } from "../lib/api-client";
import { useAuth } from "../lib/auth-context";
import type { AuditEntry } from "../lib/api-types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
	ArrowPathIcon,
	CheckBadgeIcon,
	ExclamationTriangleIcon,
	InformationCircleIcon,
	ShieldCheckIcon,
	XMarkIcon,
} from "@heroicons/react/24/outline";

export const Route = createFileRoute("/audit")({
	component: AuditTrailViewer,
});

export function AuditTrailViewer() {
	const { role } = useAuth();
	const [logs, setLogs] = React.useState<AuditEntry[]>([]);
	const [rawVerification, setRawVerification] = React.useState<any | null>(null);
	const [isLoading, setIsLoading] = React.useState(true);
	const [error, setError] = React.useState<string | null>(null);
	const [selectedLog, setSelectedLog] = React.useState<AuditEntry | null>(null);

	const loadAuditData = React.useCallback(() => {
		setIsLoading(true);
		setError(null);

		Promise.allSettled([api.getAuditLogs(100, 0), api.verifyAudit()])
			.then(([logsResult, verifyResult]) => {
				if (logsResult.status === "fulfilled") {
					const data = logsResult.value;
					if (Array.isArray(data)) {
						setLogs(data as AuditEntry[]);
					} else if (data && typeof data === "object") {
						const items =
							(data as any).items ||
							(data as any).logs ||
							(data as any).entries ||
							(data as any).results ||
							[];
						setLogs(Array.isArray(items) ? (items as AuditEntry[]) : []);
					} else {
						setLogs([]);
					}
				} else {
					setError(
						logsResult.reason instanceof Error
							? logsResult.reason.message
							: "Failed to load audit logs from backend."
					);
					setLogs([]);
				}

				if (verifyResult.status === "fulfilled") {
					setRawVerification(verifyResult.value);
				} else {
					setRawVerification(null);
				}
			})
			.finally(() => {
				setIsLoading(false);
			});
	}, []);

	React.useEffect(() => {
		loadAuditData();
	}, [loadAuditData]);

	const formatActor = (log: AuditEntry) => {
		if (log.actor_id != null) {
			return `User #${log.actor_id}`;
		}
		if (log.action.startsWith("login_failed") || log.action.startsWith("login_locked")) {
			const attemptUsername = (log.after as any)?.username;
			return attemptUsername ? `Guest ("${attemptUsername}")` : "Unauthenticated Guest";
		}
		return "System Process";
	};

	const formatRole = (role?: string | null) => {
		if (!role) return "Anonymous / System";
		const r = role.toLowerCase().replace(/_/g, " ");
		return r.charAt(0).toUpperCase() + r.slice(1);
	};

	const getRoleBadgeClass = (role?: string | null) => {
		if (!role) return "bg-slate-100 text-slate-600 border-slate-200";
		const lower = role.toLowerCase();
		if (lower.includes("admin")) return "bg-indigo-50 text-indigo-700 border-indigo-200 font-bold";
		if (lower.includes("officer")) return "bg-blue-50 text-blue-700 border-blue-200";
		if (lower.includes("coord")) return "bg-purple-50 text-purple-700 border-purple-200";
		if (lower.includes("student")) return "bg-emerald-50 text-emerald-700 border-emerald-200";
		if (lower.includes("recruit")) return "bg-amber-50 text-amber-700 border-amber-200";
		return "bg-slate-100 text-slate-700 border-slate-200";
	};

	const formatTimestamp = (ts?: string) => {
		if (!ts) return "—";
		try {
			const date = new Date(ts);
			if (Number.isNaN(date.getTime())) return ts;
			return `${date.toISOString().slice(0, 10)} ${date.toLocaleTimeString("en-IN", { hour12: false })} IST`;
		} catch {
			return ts;
		}
	};

	const verificationState = React.useMemo(() => {
		if (!rawVerification) return null;
		const verified =
			rawVerification.chain_verified === true ||
			rawVerification.tamper_evident === true ||
			rawVerification.verified === true ||
			rawVerification.valid === true ||
			rawVerification.status === "ok" ||
			rawVerification.status === "verified";

		return {
			verified,
			totalRecords:
				rawVerification.total_records ??
				rawVerification.count ??
				logs.length,
			lastHash: rawVerification.last_hash || rawVerification.hash || null,
		};
	}, [rawVerification, logs.length]);

	return (
		<NfsuShell>
			<div className="space-y-6">
				{/* Top Header */}
				<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
					<div>
						<h1 className="text-xl font-bold text-slate-900 tracking-tight">
							System Audit Ledger &amp; Integrity Verification
						</h1>
						<p className="text-xs text-slate-500 mt-0.5">
							Immutable, tamper-evident audit logs capturing administrative actions, sensitive data reveals, and policy overrides.
						</p>
					</div>

					<div className="flex items-center gap-2">
						<Button
							size="sm"
							variant="outline"
							onClick={() => loadAuditData()}
							disabled={isLoading}
							className="text-xs gap-1.5 cursor-pointer bg-white"
						>
							<ArrowPathIcon className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
							Refresh
						</Button>

						{verificationState && (
							<div>
								{verificationState.verified ? (
									<Badge className="bg-emerald-50 text-emerald-800 border-emerald-300 font-mono text-xs gap-1.5 py-1 px-3">
										<CheckBadgeIcon className="w-4 h-4 text-emerald-600" />
										Audit Chain: Verified
									</Badge>
								) : (
									<Badge className="bg-red-50 text-red-800 border-red-300 font-mono text-xs gap-1.5 py-1 px-3">
										<ExclamationTriangleIcon className="w-4 h-4 text-red-600" />
										Integrity Warning
									</Badge>
								)}
							</div>
						)}
					</div>
				</div>

				{error && (
					<div className="p-3.5 bg-red-50 border border-red-200 rounded-xl text-xs text-red-800 flex items-center justify-between">
						<div className="flex items-center gap-2">
							<ExclamationTriangleIcon className="w-4 h-4 text-red-600 shrink-0" />
							<span>{error}</span>
						</div>
						<Button
							size="sm"
							variant="ghost"
							onClick={() => loadAuditData()}
							className="text-xs text-red-700 hover:text-red-900 cursor-pointer"
						>
							Retry
						</Button>
					</div>
				)}

				{/* Verification Strip */}
				{verificationState?.lastHash && (
					<div className="p-3 bg-slate-900 text-slate-200 rounded-xl text-xs font-mono flex flex-wrap items-center justify-between gap-2 border border-slate-800">
						<div className="flex items-center gap-2">
							<ShieldCheckIcon className="w-4 h-4 text-emerald-400" />
							<span>Latest Cryptographic Hash:</span>
							<span className="text-emerald-300 break-all">{verificationState.lastHash}</span>
						</div>
						<span className="text-slate-400">Total Records: {verificationState.totalRecords}</span>
					</div>
				)}

				{/* Detail Modal for Selected Event */}
				{selectedLog && (
					<div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
						<Card className="max-w-lg w-full bg-white border-slate-200 shadow-2xl max-h-[85vh] flex flex-col">
							<CardHeader className="pb-3 border-b border-slate-100 flex flex-row items-center justify-between">
								<div className="flex items-center gap-2">
									<InformationCircleIcon className="w-5 h-5 text-indigo-600" />
									<CardTitle className="text-base font-bold text-slate-900">
										Audit Event #{selectedLog.id}
									</CardTitle>
								</div>
								<button
									type="button"
									onClick={() => setSelectedLog(null)}
									className="text-slate-400 hover:text-slate-600 p-1 rounded-md"
								>
									<XMarkIcon className="w-5 h-5" />
								</button>
							</CardHeader>
							<CardContent className="pt-4 overflow-y-auto flex-1 space-y-3 text-xs">
								<div className="grid grid-cols-2 gap-3 pb-3 border-b border-slate-100">
									<div>
										<span className="text-slate-400 block">Actor:</span>
										<span className="font-semibold text-slate-900">{formatActor(selectedLog)}</span>
									</div>
									<div>
										<span className="text-slate-400 block">Actor Role:</span>
										<Badge variant="outline" className={`text-[10px] mt-0.5 capitalize ${getRoleBadgeClass(selectedLog.actor_role)}`}>
											{formatRole(selectedLog.actor_role)}
										</Badge>
									</div>
								</div>

								<div className="grid grid-cols-2 gap-3 pb-3 border-b border-slate-100">
									<div>
										<span className="text-slate-400 block">Action:</span>
										<Badge variant="outline" className="text-[10px] font-mono mt-0.5">
											{selectedLog.action}
										</Badge>
									</div>
									<div>
										<span className="text-slate-400 block">Timestamp:</span>
										<span className="font-mono text-slate-800">{formatTimestamp(selectedLog.ts)}</span>
									</div>
								</div>

								<div className="grid grid-cols-2 gap-3 pb-3 border-b border-slate-100">
									<div>
										<span className="text-slate-400 block">Target Entity:</span>
										<span className="font-mono text-slate-800">
											{selectedLog.entity} {selectedLog.entity_id != null ? `(#${selectedLog.entity_id})` : ""}
										</span>
									</div>
									<div>
										<span className="text-slate-400 block">Client IP:</span>
										<span className="font-mono text-slate-800">{selectedLog.ip || "—"}</span>
									</div>
								</div>

								{/* State Changes / Diffs */}
								{(selectedLog.before != null || selectedLog.after != null) && (
									<div className="space-y-1 pt-1">
										<span className="text-slate-400 block font-semibold">State Changes / Payload:</span>
										<pre className="p-3 bg-slate-900 text-slate-100 rounded-lg text-[11px] overflow-x-auto font-mono">
											{JSON.stringify(
												{
													before: selectedLog.before,
													after: selectedLog.after,
												},
												null,
												2
											)}
										</pre>
									</div>
								)}

								<div className="flex justify-end pt-2">
									<Button
										type="button"
										variant="outline"
										size="sm"
										onClick={() => setSelectedLog(null)}
										className="text-xs cursor-pointer"
									>
										Close
									</Button>
								</div>
							</CardContent>
						</Card>
					</div>
				)}

				{/* Audit Table */}
				<Card className="bg-white border-slate-200/80 shadow-xs">
					<CardHeader className="pb-3 border-b border-slate-100 flex flex-row items-center justify-between">
						<div>
							<CardTitle className="text-sm font-semibold text-slate-900">
								Recent System Events
							</CardTitle>
							<p className="text-xs text-slate-500 mt-0.5">
								Chronological ledger of security and administrative interactions with IP tracking.
							</p>
						</div>
						<Badge variant="outline" className="text-xs font-mono">
							{logs.length} Events Captured
						</Badge>
					</CardHeader>
					<CardContent className="p-0">
						<div className="overflow-x-auto">
							<table className="w-full text-left text-xs">
								<thead className="bg-slate-50 border-b border-slate-200/80 text-slate-600 font-medium">
									<tr>
										<th className="px-4 py-3">ID</th>
										<th className="px-4 py-3">Timestamp (IST)</th>
										<th className="px-4 py-3">Actor</th>
										<th className="px-4 py-3">Actor Role</th>
										<th className="px-4 py-3">Action</th>
										<th className="px-4 py-3">Entity</th>
										<th className="px-4 py-3">Client IP</th>
										<th className="px-4 py-3 text-right">Actions</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-slate-100">
									{isLoading ? (
										<tr>
											<td
												colSpan={8}
												className="px-4 py-8 text-center text-slate-400"
											>
												Loading audit ledger...
											</td>
										</tr>
									) : logs.length === 0 ? (
										<tr>
											<td
												colSpan={8}
												className="px-4 py-12 text-center text-slate-500"
											>
												<ShieldCheckIcon className="w-10 h-10 text-slate-300 mx-auto mb-2" />
												<p className="text-sm font-medium text-slate-700">
													No audit events found
												</p>
												<p className="text-xs text-slate-400 mt-0.5">
													System interactions will be cryptographically hashed and listed here.
												</p>
											</td>
										</tr>
									) : (
										logs.map((log) => {
											return (
												<tr
													key={log.id}
													className="hover:bg-slate-50/80 transition"
												>
													<td className="px-4 py-3 font-mono text-slate-400 font-semibold">
														#{log.id}
													</td>
													<td className="px-4 py-3 font-mono text-slate-600">
														{formatTimestamp(log.ts)}
													</td>
													<td className="px-4 py-3 font-medium text-slate-900">
														{formatActor(log)}
													</td>
													<td className="px-4 py-3">
														<Badge
															variant="outline"
															className={`text-[10px] font-mono capitalize ${getRoleBadgeClass(log.actor_role)}`}
														>
															{formatRole(log.actor_role)}
														</Badge>
													</td>
													<td className="px-4 py-3">
														<Badge
															variant="outline"
															className="text-[10px] font-mono"
														>
															{log.action}
														</Badge>
													</td>
													<td className="px-4 py-3 font-mono text-slate-600">
														{log.entity} {log.entity_id != null ? `(#${log.entity_id})` : ""}
													</td>
													<td className="px-4 py-3 font-mono text-slate-500">
														{log.ip || "—"}
													</td>
													<td className="px-4 py-3 text-right">
														<button
															type="button"
															onClick={() => setSelectedLog(log)}
															className="text-xs text-indigo-600 hover:text-indigo-800 font-medium cursor-pointer"
														>
															Inspect &rarr;
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
