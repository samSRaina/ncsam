import tailwindcss from "@tailwindcss/vite";
import { devtools } from "@tanstack/devtools-vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const targetBackend = process.env.VITE_API_BASE_URL || "http://172.18.45.24:8000";

const config = defineConfig({
	resolve: { tsconfigPaths: true },
	plugins: [devtools(), tailwindcss(), tanstackStart(), viteReact()],
	server: {
		proxy: {
			"/api": {
				target: targetBackend,
				changeOrigin: true,
				secure: false,
			},
		},
	},
});

export default config;
