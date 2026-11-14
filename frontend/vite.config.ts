import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

// Dev server only; the built app is served by FastAPI on one origin.
const api = "http://127.0.0.1:8000"

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/search": api, "/healthz": api } },
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"], css: false },
})
