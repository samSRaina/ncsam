import * as React from "react";
import { useAuth } from "../lib/auth-context";
import type { Course, UserRole } from "../lib/api-types";
import { Badge } from "./ui/badge";

export function DevRoleSwitcher() {
	const {
		role,
		user,
		devBypassEnabled,
		setDevBypassEnabled,
		setDevRole,
		refreshSession,
	} = useAuth();

	if (process.env.NODE_ENV === "production") {
		return null;
	}

	return (
		<aside
			aria-label="Developer Testing & Authentication Controls"
			className="bg-slate-950 text-slate-200 text-xs px-3 py-1.5 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2 z-50 sticky top-0 font-mono shadow-sm"
		>
			<div className="flex items-center gap-2.5">
				<span className="font-bold flex items-center gap-1.5 text-amber-400">
					<span
						className={`inline-block w-2 h-2 rounded-full ${
							devBypassEnabled ? "bg-amber-400 animate-pulse" : "bg-emerald-400"
						}`}
					/>
					AUTH MODE:
				</span>

				{/* Dev Mode Enable/Disable Switch */}
				<button
					type="button"
					onClick={() => {
						const next = !devBypassEnabled;
						setDevBypassEnabled(next);
						if (!next) refreshSession();
					}}
					className={`px-2 py-0.5 rounded text-[11px] font-bold cursor-pointer transition border ${
						devBypassEnabled
							? "bg-amber-500 text-black border-amber-400"
							: "bg-emerald-950 text-emerald-300 border-emerald-700 hover:bg-emerald-900"
					}`}
				>
					{devBypassEnabled ? "DEV BYPASS ACTIVE (MOCK ROLES)" : "LIVE BACKEND AUTH ACTIVE"}
				</button>

				<span className="text-slate-600">|</span>

				<span className="text-slate-400">Current User:</span>
				<Badge
					variant="outline"
					className="bg-slate-900 border-slate-700 text-slate-200 text-[11px] font-mono capitalize"
				>
					{user ? user.username : "Unauthenticated (Guest)"}
				</Badge>

				{user && (
					<Badge
						variant="outline"
						className="bg-slate-900 border-slate-700 text-indigo-300 text-[11px] font-mono capitalize"
					>
						Role: {role.replace("_", " ")}
					</Badge>
				)}
			</div>

			{/* Role Switcher buttons only active when dev bypass is enabled */}
			{devBypassEnabled ? (
				<div className="flex items-center gap-1.5 flex-wrap">
					<span className="text-[11px] text-slate-400 mr-1">Simulate Role:</span>
					<button
						type="button"
						onClick={() => setDevRole("placement_administrator")}
						className={`px-2 py-0.5 rounded cursor-pointer transition text-[11px] ${
							role === "placement_administrator"
								? "bg-amber-400 text-black font-semibold"
								: "bg-slate-800 hover:bg-slate-700 text-slate-300"
						}`}
					>
						Admin
					</button>
					<button
						type="button"
						onClick={() => setDevRole("placement_officer")}
						className={`px-2 py-0.5 rounded cursor-pointer transition text-[11px] ${
							role === "placement_officer"
								? "bg-amber-400 text-black font-semibold"
								: "bg-slate-800 hover:bg-slate-700 text-slate-300"
						}`}
					>
						Officer
					</button>
					<button
						type="button"
						onClick={() => setDevRole("course_coordinator", "M.Tech CS")}
						className={`px-2 py-0.5 rounded cursor-pointer transition text-[11px] ${
							role === "course_coordinator"
								? "bg-amber-400 text-black font-semibold"
								: "bg-slate-800 hover:bg-slate-700 text-slate-300"
						}`}
					>
						Coordinator
					</button>
					<button
						type="button"
						onClick={() => setDevRole("recruiter")}
						className={`px-2 py-0.5 rounded cursor-pointer transition text-[11px] ${
							role === "recruiter"
								? "bg-amber-400 text-black font-semibold"
								: "bg-slate-800 hover:bg-slate-700 text-slate-300"
						}`}
					>
						Recruiter
					</button>
				</div>
			) : (
				<div className="text-[11px] text-slate-500">
					Session authenticated against backend via HTTP-only cookies
				</div>
			)}
		</aside>
	);
}
