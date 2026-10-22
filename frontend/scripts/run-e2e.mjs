import { existsSync } from "node:fs";
import { spawn, spawnSync } from "node:child_process";
import { resolve } from "node:path";

const liveArgument = process.argv.includes("--live");
if (liveArgument) process.env.PLAYWRIGHT_LIVE = "1";
const live = process.env.PLAYWRIGHT_LIVE === "1";
const providedBaseUrl = Boolean(process.env.PLAYWRIGHT_BASE_URL);
process.env.PLAYWRIGHT_BASE_URL ??= live
  ? "http://localhost:3000"
  : "http://localhost:3100";
const baseUrl = process.env.PLAYWRIGHT_BASE_URL;
const testArguments = process.argv
  .slice(2)
  .filter((value) => value !== "--live");
let server = null;

function stopServer() {
  if (!server || server.exitCode !== null) return;
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(server.pid), "/T", "/F"], {
      stdio: "ignore",
    });
  } else {
    server.kill("SIGTERM");
  }
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    stopServer();
    process.exit(1);
  });
}

async function waitForServer() {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(baseUrl);
      if (response.ok) return;
    } catch {
      // The production server is still starting.
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 500));
  }
  throw new Error(`Next.js did not become ready at ${baseUrl}`);
}

if (!live && !providedBaseUrl) {
  if (!existsSync(resolve(".next", "BUILD_ID"))) {
    throw new Error("Run `npm run build` before `npm run e2e`");
  }
  server = spawn(
    process.execPath,
    [
      resolve("node_modules", "next", "dist", "bin", "next"),
      "start",
      "--port",
      "3100",
    ],
    { stdio: "ignore", env: process.env },
  );
  server.unref();
  await waitForServer();
}

let exitCode = 1;
try {
  const result = spawnSync(
    process.execPath,
    [
      resolve("node_modules", "@playwright", "test", "cli.js"),
      "test",
      ...testArguments,
    ],
    {
      stdio: "inherit",
      env: { ...process.env, PLAYWRIGHT_BASE_URL: baseUrl },
    },
  );
  if (result.error) throw result.error;
  exitCode = result.status ?? (result.signal ? 1 : 0);
} finally {
  stopServer();
}
process.exitCode = exitCode;
