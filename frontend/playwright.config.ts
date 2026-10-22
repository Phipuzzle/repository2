import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./src/e2e",
  testMatch:
    process.env.PLAYWRIGHT_LIVE === "1" ? "**/*.spec.ts" : "**/home.spec.ts",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3100",
    channel: "chrome",
  },
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: "node ./node_modules/next/dist/bin/next start --port 3100",
        url: "http://localhost:3100",
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
        stdout: "ignore",
        stderr: "pipe",
        gracefulShutdown: { signal: "SIGTERM", timeout: 1_000 },
      },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
