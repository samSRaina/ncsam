"use client";
import {
	AlignStartVertical,
	BarChart3,
	ChartPie,
	CircleUserRound,
	ClipboardList,
	CreditCard,
	Languages,
	LayoutPanelTop,
	type LucideIcon,
	Notebook,
	NotepadText,
	Table,
	Ticket,
} from "lucide-react";
import type React from "react";
import { NavMain } from "#/components/shadcn-space/blocks/dashboard-shell-01/nav-main.tsx";
import { SiteHeader } from "#/components/shadcn-space/blocks/dashboard-shell-01/site-header.tsx";
import { Button } from "#/components/ui/button.tsx";
import { Card, CardContent } from "#/components/ui/card.tsx";
import { ScrollArea } from "#/components/ui/scroll-area.tsx";
import {
	Sidebar,
	SidebarContent,
	SidebarHeader,
	SidebarMenu,
	SidebarMenuItem,
	SidebarProvider,
} from "#/components/ui/sidebar.tsx";
import Logo from "#/src/assets/logo/logo.tsx";

export type NavItem = {
	label?: string;
	isSection?: boolean;
	title?: string;
	icon?: LucideIcon;
	href?: string;
	children?: NavItem[];
	isActive?: boolean;
};

export const navData: NavItem[] = [
	// Dashboards Section
	{ label: "Dashboards", isSection: true },
	{ title: "Analytics", icon: BarChart3, href: "#", isActive: true },
	{ title: "CRM Dashboard", icon: ClipboardList, href: "#" },

	// Pages Section
	{ label: "Pages", isSection: true },
	{ title: "Tables", icon: Table, href: "#" },
	{ title: "Forms", icon: ClipboardList, href: "#" },
	{ title: "User Profile", icon: CircleUserRound, href: "#" },

	// Apps Section
	{ label: "Apps", isSection: true },
	{ title: "Notes", icon: Notebook, href: "#" },
	{ title: "Tickets", icon: Ticket, href: "#" },
	{
		title: "Blogs",
		icon: Languages,
		children: [
			{ title: "Blog Post", href: "#" },
			{ title: "Blog Detail", href: "#" },
			{ title: "Blog Edit", href: "#" },
			{ title: "Blog Create", href: "#" },
			{ title: "Manage Blogs", href: "#" },
		],
	},

	// Form Elements Section
	{ label: "Form Elements", isSection: true },
	{
		title: "Shadcn Forms",
		icon: NotepadText,
		children: [
			{ title: "Button", href: "#" },
			{ title: "Input", href: "#" },
			{ title: "Select", href: "#" },
			{ title: "Checkbox", href: "#" },
			{ title: "Radio", href: "#" },
		],
	},
	{
		title: "Form layouts",
		icon: AlignStartVertical,
		children: [
			{ title: "Forms Horizontal", href: "#" },
			{ title: "Forms Vertical", href: "#" },
			{ title: "Forms Validation", href: "#" },
			{ title: "Forms Examples", href: "#" },
			{ title: "Forms Wizard", href: "#" },
		],
	},
	{ label: "WIDGETS", isSection: true },
	{
		title: "Cards",
		icon: CreditCard,
		children: [
			{ title: "Ecommerce Actions", href: "#" },
			{ title: "Course ", href: "#" },
			{ title: "Campaign Performance ", href: "#" },
			{ title: "Selling Products ", href: "#" },
			{ title: "Activity Timeline ", href: "#" },
		],
	},
	{
		title: "Banners",
		icon: LayoutPanelTop,
		children: [{ title: "Analytic Banner ", href: "#" }],
	},
	{
		title: "Charts",
		icon: ChartPie,
		children: [
			{ title: "Sales Report", href: "#" },
			{ title: "Weekly Sales", href: "#" },
		],
	},
];

/* -------------------------------------------------------------------------- */
/*                                   Page                                     */
/* -------------------------------------------------------------------------- */

const AppSidebar = ({ children }: { children: React.ReactNode }) => {
	return (
		<SidebarProvider>
			<Sidebar className="py-4 px-0 bg-background">
				<div className="flex flex-col gap-6 bg-background">
					{/* ---------------- Header ---------------- */}
					<SidebarHeader className="py-0 px-4">
						<SidebarMenu>
							<SidebarMenuItem>
								<a href="#" className="w-full h-full">
									<Logo />
								</a>
							</SidebarMenuItem>
						</SidebarMenu>
					</SidebarHeader>

					{/* ---------------- Content ---------------- */}
					<SidebarContent className="overflow-hidden gap-0 px-0">
						<ScrollArea className="h-[calc(100vh-348px)] border-b border-border">
							<div className="px-4">
								<NavMain items={navData} />
							</div>
						</ScrollArea>
						{/* card */}
						<div className="pt-4 px-4">
							<Card className="shadow-none ring-0 bg-blue-500/10 px-4 py-6">
								<CardContent className="p-0 flex flex-col gap-3 items-center">
									<img
										src="https://images.shadcnspace.com/assets/backgrounds/download-img.png"
										alt="sidebar-img"
										width={74}
										height={74}
										className="h-20 w-20"
									/>
									<div className="flex flex-col gap-4 items-center">
										<div>
											<p className="text-base font-semibold text-card-foreground text-center">
												Grab Pro Now
											</p>
											<p className="text-sm font-regular text-muted-foreground text-center">
												Customize your admin
											</p>
										</div>
										<Button className="w-fit px-4 py-2 shadow-none cursor-pointer rounded-xl bg-blue-500 font-medium hover:bg-blue-500/80 h-9">
											Get Premium
										</Button>
									</div>
								</CardContent>
							</Card>
						</div>
					</SidebarContent>
				</div>
			</Sidebar>

			{/* ---------------- Main ---------------- */}
			<div className="flex flex-1 flex-col">
				<header className="sticky top-0 z-50 flex items-center border-b px-6 py-3 bg-background">
					<SiteHeader />
				</header>
				<main className="flex-1">{children}</main>
			</div>
		</SidebarProvider>
	);
};

export default AppSidebar;
