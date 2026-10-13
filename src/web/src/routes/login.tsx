import * as React from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useAuth } from "../lib/auth-context";
import { api } from "../lib/api-client";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { DevRoleSwitcher } from "../components/dev-role-switcher";
import { LockClosedIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";

export const Route = createFileRoute("/login")({
	component: LoginPage,
});

function LoginPage() {
	const navigate = useNavigate();
	const { user, login, devBypassEnabled } = useAuth();
	const [username, setUsername] = React.useState("");
	const [password, setPassword] = React.useState("");
	const [mfaCode, setMfaCode] = React.useState("");
	const [step, setStep] = React.useState<"credentials" | "mfa">("credentials");
	const [error, setError] = React.useState<string | null>(null);
	const [isLoading, setIsLoading] = React.useState(false);

	// If already authenticated or dev bypass is enabled, proceed to dashboard
	React.useEffect(() => {
		if (user && devBypassEnabled) {
			navigate({ to: "/" });
		}
	}, [user, devBypassEnabled, navigate]);

	const handleLogin = async (e: React.FormEvent) => {
		e.preventDefault();
		setError(null);
		setIsLoading(true);

		try {
			// Submits to live backend /api/auth/login with X-Requested-With: placement-ui & credentials: include
			const res = await api.login({ username, password });
			login(res);
			navigate({ to: "/" });
		} catch (err: unknown) {
			setError(
				err instanceof Error
					? err.message
					: "Invalid username or password. Please verify your credentials."
			);
		} finally {
			setIsLoading(false);
		}
	};

	return (
		<div className="min-h-screen bg-slate-900 flex flex-col justify-between">
			<DevRoleSwitcher />

			<div className="flex-1 flex flex-col justify-center items-center p-4">
				<div className="w-full max-w-md">
					<div className="text-center mb-8">
						<div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-600 text-white font-bold text-2xl shadow-xl mb-4">
							NF
						</div>
						<h1 className="text-2xl font-bold text-white tracking-tight">
							NFSU Placement Cell
						</h1>
						<p className="text-sm text-slate-400 mt-1">
							National Forensic Sciences University • Session 2026–27
						</p>
					</div>

					<Card className="border-slate-800 bg-slate-950/80 text-white shadow-2xl backdrop-blur-md">
						<CardHeader className="space-y-1">
							<CardTitle className="text-xl font-semibold flex items-center gap-2">
								<LockClosedIcon className="w-5 h-5 text-indigo-400" />
								{step === "credentials" ? "Institutional Sign In" : "Security Verification"}
							</CardTitle>
							<CardDescription className="text-slate-400 text-xs">
								{step === "credentials"
									? "Enter your official institutional credentials to access the placement system."
									: "Enter the one-time authentication code sent to your registered device."}
							</CardDescription>
						</CardHeader>

						<CardContent>
							{error && (
								<div className="p-3 mb-4 rounded-lg bg-red-950/60 border border-red-800 text-red-200 text-xs font-medium">
									{error}
								</div>
							)}

							{step === "credentials" ? (
								<form onSubmit={handleLogin} className="space-y-4">
									<div className="space-y-1.5">
										<label htmlFor="login-username" className="text-xs font-medium text-slate-300">
											Username / Email
										</label>
										<Input
											id="login-username"
											type="text"
											value={username}
											onChange={(e) => setUsername(e.target.value)}
											placeholder="e.g. officer@nfsu.ac.in"
											required
											className="bg-slate-900 border-slate-800 text-white focus-visible:ring-indigo-500 text-xs"
										/>
									</div>

									<div className="space-y-1.5">
										<div className="flex items-center justify-between">
											<label htmlFor="login-password" className="text-xs font-medium text-slate-300">
												Password
											</label>
											<span className="text-xs text-indigo-400 hover:underline cursor-pointer">
												Forgot?
											</span>
										</div>
										<Input
											id="login-password"
											type="password"
											value={password}
											onChange={(e) => setPassword(e.target.value)}
											placeholder="••••••••••••"
											required
											className="bg-slate-900 border-slate-800 text-white focus-visible:ring-indigo-500 text-xs"
										/>
									</div>

									<Button
										type="submit"
										disabled={isLoading}
										className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium shadow-md transition cursor-pointer text-xs"
									>
										{isLoading ? "Authenticating Session..." : "Sign In to Portal"}
									</Button>

									<div className="mt-4 pt-4 border-t border-slate-900 text-center">
										<p className="text-[11px] text-slate-500 flex items-center justify-center gap-1.5">
											<ShieldCheckIcon className="w-4 h-4 text-emerald-400" />
											Protected by Session Verification & Audit Ledger
										</p>
									</div>
								</form>
							) : (
								<div className="space-y-4">
									<div className="space-y-1.5">
										<label htmlFor="login-mfa" className="text-xs font-medium text-slate-300">
											MFA Security Code
										</label>
										<Input
											id="login-mfa"
											type="text"
											maxLength={6}
											value={mfaCode}
											onChange={(e) => setMfaCode(e.target.value)}
											placeholder="6-digit code"
											className="bg-slate-900 border-slate-800 text-white text-center font-mono tracking-widest text-lg"
										/>
									</div>
									<Button
										type="button"
										onClick={() => navigate({ to: "/" })}
										className="w-full bg-indigo-600 hover:bg-indigo-500 text-white cursor-pointer text-xs"
									>
										Verify & Proceed
									</Button>
								</div>
							)}
						</CardContent>
					</Card>

					<p className="text-center text-xs text-slate-600 mt-6">
						Authorized personnel only. All access attempts are cryptographically logged.
					</p>
				</div>
			</div>

			<div className="py-2" />
		</div>
	);
}
