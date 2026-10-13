import * as React from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
	AcademicCapIcon,
	ArrowRightStartOnRectangleIcon,
	BriefcaseIcon,
	ChartBarSquareIcon,
	ClipboardDocumentCheckIcon,
	DocumentCheckIcon,
	HomeIcon,
	ScaleIcon,
	ShieldCheckIcon,
} from "@heroicons/react/24/outline";
import { useAuth } from "../../lib/auth-context";
import { DevRoleSwitcher } from "../dev-role-switcher";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

interface NavItem {
	title: string;
	href: string;
	icon: React.ComponentType<{ className?: string }>;
	roles: string[];
}

// All navigation items for the NFSU Placement Portal
const navItems: NavItem[] = [
	{
		title: "Dashboard",
		href: "/",
		icon: HomeIcon,
		roles: [
			"admin",
			"administrator",
			"placement_admin",
			"placement_administrator",
			"officer",
			"placement_officer",
			"coordinator",
			"course_coordinator",
			"recruiter",
			"company",
		],
	},
	{
		title: "Students",
		href: "/students",
		icon: AcademicCapIcon,
		roles: [
			"admin",
			"administrator",
			"placement_admin",
			"placement_administrator",
			"officer",
			"placement_officer",
			"coordinator",
			"course_coordinator",
		],
	},
	{
		title: "Companies & Drives",
		href: "/recruitment",
		icon: BriefcaseIcon,
		roles: [
			"admin",
			"administrator",
			"placement_admin",
			"placement_administrator",
			"officer",
			"placement_officer",
			"recruiter",
			"company",
		],
	},
	{
		title: "Attendance Ledger",
		href: "/attendance",
		icon: ClipboardDocumentCheckIcon,
		roles: [
			"admin",
			"administrator",
			"placement_admin",
			"placement_administrator",
			"officer",
			"placement_officer",
			"recruiter",
			"company",
		],
	},
	{
		title: "Offers & PPOs",
		href: "/offers",
		icon: DocumentCheckIcon,
		roles: [
			"admin",
			"administrator",
			"placement_admin",
			"placement_administrator",
			"officer",
			"placement_officer",
			"recruiter",
			"company",
		],
	},
	{
		title: "Policy Engine",
		href: "/policy",
		icon: ScaleIcon,
		roles: [
			"admin",
			"administrator",
			"placement_admin",
			"placement_administrator",
			"officer",
			"placement_officer",
		],
	},
	{
		title: "Reports & Analytics",
		href: "/reports",
		icon: ChartBarSquareIcon,
		roles: [
			"admin",
			"administrator",
			"placement_admin",
			"placement_administrator",
			"officer",
			"placement_officer",
			"coordinator",
			"course_coordinator",
		],
	},
	{
		title: "Audit Trail",
		href: "/audit",
		icon: ShieldCheckIcon,
		roles: [
			"admin",
			"administrator",
			"placement_admin",
			"placement_administrator",
			"officer",
			"placement_officer",
		],
	},
];

export function NfsuShell({ children }: { children: React.ReactNode }) {
	const { user, role, rawRole, isLoading, logout, devBypassEnabled } = useAuth();
	const navigate = useNavigate();
	const routerState = useRouterState();
	const currentPath = routerState.location.pathname;

	// Route guard: When dev bypass is not enabled and user is not authenticated, redirect to /login
	React.useEffect(() => {
		if (!isLoading && !user && !devBypassEnabled) {
			navigate({ to: "/login" });
		}
	}, [isLoading, user, devBypassEnabled, navigate]);

	if (isLoading) {
		return (
			<div className="min-h-screen flex items-center justify-center bg-slate-900 text-white font-mono text-xs">
				Checking institutional session status...
			</div>
		);
	}

	if (!user && !devBypassEnabled) {
		return null; // Redirecting to login
	}

	// Filter navigation items matching either normalized role, raw backend role, or allow-all for admin
	const filteredNav = navItems.filter((item) => {
		// Administrator sees 100% of the elements
		if (role === "placement_administrator") return true;

		const currentRaw = rawRole.toLowerCase();
		return (
			item.roles.includes(role) ||
			item.roles.includes(currentRaw) ||
			item.roles.some((r) => currentRaw.includes(r))
		);
	});

	return (
		<div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 font-sans">
			<DevRoleSwitcher />

			{/* Persistent Header */}
			<header className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-40">
				<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
					<div className="flex items-center gap-3">
						<div className="w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-lg text-white shadow-md">
							NF
						</div>
						<div>
							<div className="font-semibold text-base tracking-tight leading-tight">
								NFSU Placement Cell
							</div>
							<div className="text-xs text-slate-400">
								Academic Session 2026–27 | Institutional Portal
							</div>
						</div>
					</div>

					{/* Role badge and controls */}
					<div className="flex items-center gap-3">
						<div className="hidden md:flex flex-col items-end text-xs">
							<span className="text-slate-300 font-medium">{user?.username}</span>
							<span className="text-slate-400 capitalize">
								{rawRole || role.replace("_", " ")}
								{user?.course ? ` (${user.course})` : ""}
							</span>
						</div>
						<Badge
							variant="outline"
							className="bg-indigo-950/80 border-indigo-500/40 text-indigo-300 text-xs px-2.5 py-0.5"
						>
							{role === "placement_administrator" && "Placement Administrator"}
							{role === "placement_officer" && "Placement Officer"}
							{role === "course_coordinator" && "Course Coordinator"}
							{role === "recruiter" && "Recruiter Scope"}
						</Badge>
						<Button
							variant="ghost"
							size="sm"
							onClick={async () => {
								await logout();
								navigate({ to: "/login" });
							}}
							className="text-slate-300 hover:text-white hover:bg-slate-800 gap-1.5 text-xs cursor-pointer"
						>
							<ArrowRightStartOnRectangleIcon className="w-4 h-4" />
							<span className="hidden sm:inline">Sign Out</span>
						</Button>
					</div>
				</div>
			</header>

			{/* Body Container with Sidebar and Main Content */}
			<div className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 flex gap-6">
				{/* Sidebar */}
				<aside className="w-64 shrink-0 hidden md:block">
					<nav className="space-y-1 sticky top-24 bg-white rounded-xl border border-slate-200/80 p-3 shadow-xs">
						<div className="px-3 py-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
							Navigation
						</div>
						{filteredNav.map((item) => {
							const Icon = item.icon;
							const isActive = currentPath === item.href;
							return (
								<Link
									key={item.href}
									to={item.href}
									className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
										isActive
											? "bg-slate-900 text-white shadow-xs"
											: "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
									}`}
								>
									<Icon
										className={`w-5 h-5 shrink-0 ${
											isActive ? "text-indigo-400" : "text-slate-400"
										}`}
									/>
									<span>{item.title}</span>
								</Link>
							);
						})}
					</nav>
				</aside>

				{/* Main Content Area */}
				<main className="flex-1 min-w-0">
					{children}
				</main>
			</div>
		</div>
	);
}
