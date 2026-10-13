import * as React from "react";
import { api } from "./api-client";
import type { Course, UserMe, UserRole } from "./api-types";

interface AuthContextType {
	user: UserMe | null;
	isLoading: boolean;
	role: UserRole;
	rawRole: string;
	devBypassEnabled: boolean;
	setDevBypassEnabled: (enabled: boolean) => void;
	setDevRole: (role: UserRole, course?: Course | null) => void;
	login: (user: UserMe) => void;
	logout: () => Promise<void>;
	refreshSession: () => Promise<void>;
}

const defaultDevUser: UserMe = {
	id: 1,
	username: "administrator",
	email: "admin@nfsu.ac.in",
	role: "placement_administrator",
	course: null,
	company_id: null,
};

const AuthContext = React.createContext<AuthContextType | undefined>(undefined);

// Normalizes arbitrary backend role strings ("admin", "placement_admin", "placement_administrator", "officer", "coordinator", etc.)
export function normalizeRole(raw?: string | null): UserRole {
	if (!raw) return "placement_administrator";
	const lower = String(raw).toLowerCase().trim().replace(/[-\s]/g, "_");

	if (lower.includes("admin")) {
		return "placement_administrator";
	}
	if (lower.includes("officer")) {
		return "placement_officer";
	}
	if (lower.includes("coord")) {
		return "course_coordinator";
	}
	if (lower.includes("recruit") || lower.includes("company")) {
		return "recruiter";
	}
	return "placement_administrator";
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
	const [devBypassEnabled, setDevBypassState] = React.useState<boolean>(() => {
		if (typeof window !== "undefined") {
			const saved = localStorage.getItem("nfsu_dev_bypass_enabled");
			if (saved !== null) {
				return saved === "true";
			}
		}
		return false;
	});

	const [devUser, setDevUserState] = React.useState<UserMe>(() => {
		if (typeof window !== "undefined") {
			const saved = localStorage.getItem("nfsu_dev_user");
			if (saved) {
				try {
					return JSON.parse(saved);
				} catch {
					// fallback
				}
			}
		}
		return defaultDevUser;
	});

	const [liveUser, setLiveUser] = React.useState<UserMe | null>(null);
	const [isLoading, setIsLoading] = React.useState(true);

	const refreshSession = React.useCallback(async () => {
		setIsLoading(true);
		try {
			const me = await api.getMe();
			setLiveUser(me);
		} catch {
			setLiveUser(null);
		} finally {
			setIsLoading(false);
		}
	}, []);

	React.useEffect(() => {
		refreshSession();
	}, [refreshSession]);

	const setDevBypassEnabled = React.useCallback((enabled: boolean) => {
		setDevBypassState(enabled);
		if (typeof window !== "undefined") {
			localStorage.setItem("nfsu_dev_bypass_enabled", String(enabled));
		}
	}, []);

	const setDevRole = React.useCallback(
		(role: UserRole, course: Course | null = null) => {
			const newUser: UserMe = {
				id: 999,
				username: `test_${role}`,
				email: `${role}@nfsu.ac.in`,
				role,
				course,
				company_id: role === "recruiter" ? 1 : null,
			};
			setDevUserState(newUser);
			if (typeof window !== "undefined") {
				localStorage.setItem("nfsu_dev_user", JSON.stringify(newUser));
			}
		},
		[],
	);

	const login = React.useCallback((loggedInUser: UserMe) => {
		setLiveUser(loggedInUser);
	}, []);

	const logout = React.useCallback(async () => {
		try {
			await api.logout();
		} catch {
			// ignore network err
		}
		setLiveUser(null);
	}, []);

	const user = devBypassEnabled ? devUser : liveUser;
	const rawRole = String(user?.role || "");
	const role = normalizeRole(user?.role);

	return (
		<AuthContext.Provider
			value={{
				user,
				isLoading,
				role,
				rawRole,
				devBypassEnabled,
				setDevBypassEnabled,
				setDevRole,
				login,
				logout,
				refreshSession,
			}}
		>
			{children}
		</AuthContext.Provider>
	);
}

export function useAuth() {
	const context = React.useContext(AuthContext);
	if (!context) {
		throw new Error("useAuth must be used within an AuthProvider");
	}
	return context;
}
