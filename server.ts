import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import dotenv from "dotenv";
import express from "express";
import JSZip from "jszip";
import { createServer as createViteServer } from "vite";

dotenv.config({ override: false });

const ROOT_DIR = process.cwd();
const PY_DIR = path.resolve(ROOT_DIR, "competitor-tracker");

// Load competitor-tracker/.env as well if present, without overriding explicit env vars.
const pyEnvPath = path.join(PY_DIR, ".env");
if (fs.existsSync(pyEnvPath)) {
  dotenv.config({ path: pyEnvPath, override: false });
}

const PORT = 3000;
const RUN_TIMEOUT_MS = 120_000;
const VALID_ABLATIONS = new Set(["full", "no_classifier", "single_agent"]);
const VALID_EVAL_ABLATIONS = new Set(["all", "full", "no_classifier", "single_agent"]);
const PLACEHOLDER_KEYS = new Set([
  "",
  "your_gemini_key_here",
  "your_groq_key_here",
  "MY_GEMINI_API_KEY",
]);

function hasValidKey(val: string | undefined): boolean {
  if (!val) return false;
  return !PLACEHOLDER_KEYS.has(val.trim());
}

function getCapabilities() {
  const localMode = process.env.LOCAL_MODE === "1";
  const hasGemini = hasValidKey(process.env.GEMINI_API_KEY);
  const hasGroq = hasValidKey(process.env.GROQ_API_KEY);
  const hasKeys = hasGemini || hasGroq;
  return {
    localMode,
    hasKeys,
    liveAvailable: localMode && hasKeys,
    mockToggleAvailable: localMode,
  };
}

function resolvePythonBin(): string {
  const unixVenv = path.join(PY_DIR, ".venv", "bin", "python");
  if (fs.existsSync(unixVenv)) return unixVenv;
  const winVenv = path.join(PY_DIR, ".venv", "Scripts", "python.exe");
  if (fs.existsSync(winVenv)) return winVenv;
  return process.platform === "win32" ? "python" : "python3";
}

function isValidIsoDate(value: unknown): value is string {
  if (typeof value !== "string") return false;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [y, m, d] = value.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return (
    dt.getUTCFullYear() === y &&
    dt.getUTCMonth() === m - 1 &&
    dt.getUTCDate() === d
  );
}

function readJsonSafe<T>(filePath: string, fallback: T): T {
  try {
    if (!fs.existsSync(filePath)) return fallback;
    const raw = fs.readFileSync(filePath, "utf-8").trim();
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function readMockState(): { locus_ai_summary_visible: boolean } {
  const statePath = path.join(PY_DIR, "mock_sites", "state.json");
  const data = readJsonSafe<{ locus_ai_summary_visible?: boolean }>(statePath, {});
  return { locus_ai_summary_visible: Boolean(data.locus_ai_summary_visible) };
}

function writeMockState(nextState: { locus_ai_summary_visible: boolean }): void {
  const statePath = path.join(PY_DIR, "mock_sites", "state.json");
  const tmpPath = path.join(path.dirname(statePath), `.state_${Date.now()}.tmp`);
  fs.writeFileSync(tmpPath, JSON.stringify(nextState, null, 2) + "\n", "utf-8");
  fs.renameSync(tmpPath, statePath);
}

let activeRunLabel: string | null = null;

function runPythonModule(args: string[], label: string): Promise<{ code: number; stdout: string }> {
  return new Promise((resolve, reject) => {
    if (activeRunLabel !== null) {
      const busyErr = new Error("CONCURRENT_RUN");
      reject(busyErr);
      return;
    }
    activeRunLabel = label;

    const pythonBin = resolvePythonBin();
    const child = spawn(pythonBin, args, {
      cwd: PY_DIR,
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1",
      },
    });

    let stdout = "";
    let timedOut = false;

    child.stdout.on("data", (chunk: Buffer) => {
      if (stdout.length < 64_000) {
        stdout += chunk.toString("utf-8");
      }
    });

    // Drain stderr without ever forwarding raw stderr to clients.
    child.stderr.resume();

    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGTERM");
      setTimeout(() => {
        if (!child.killed) {
          child.kill("SIGKILL");
        }
      }, 2_000);
    }, RUN_TIMEOUT_MS);

    child.on("error", () => {
      clearTimeout(timer);
      activeRunLabel = null;
      reject(new Error("SPAWN_FAILED"));
    });

    child.on("close", (code) => {
      clearTimeout(timer);
      activeRunLabel = null;
      if (timedOut) {
        reject(new Error("RUN_TIMEOUT"));
        return;
      }
      resolve({ code: code ?? 1, stdout });
    });
  });
}

const EXCLUDED_DIRS = new Set([
  ".venv",
  "__pycache__",
  ".pytest_cache",
  "cache",
  "snapshots",
  "logs",
  "node_modules",
]);

function collectRepoFiles(dir: string, relBase = ""): string[] {
  const results: string[] = [];
  if (!fs.existsSync(dir)) return results;

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const rel = relBase ? `${relBase}/${entry.name}` : entry.name;
    if (entry.isDirectory()) {
      if (EXCLUDED_DIRS.has(entry.name)) continue;
      if (rel === "data/cache" || rel === "data/snapshots") continue;
      results.push(...collectRepoFiles(path.join(dir, entry.name), rel));
    } else if (entry.isFile()) {
      if (entry.name === ".env" || entry.name.endsWith(".pyc") || entry.name.endsWith(".log")) continue;
      if (entry.name === "feed_dryrun.json" || entry.name === "last_run_dryrun.json") continue;
      results.push(rel);
    }
  }
  return results.sort();
}

async function startServer() {
  const app = express();
  app.use(express.json({ limit: "1mb" }));

  app.get("/api/status", (_req, res) => {
    const caps = getCapabilities();
    res.json({
      defaultMode: "replay",
      ...caps,
      runActive: activeRunLabel !== null,
      activeRunLabel,
      mockState: readMockState(),
      testsVerifiedCount: 22,
    });
  });

  app.get("/api/feed", (_req, res) => {
    const feedPath = path.join(PY_DIR, "data", "feed.json");
    const summaryPath = path.join(PY_DIR, "data", "last_run_summary.json");
    const events = readJsonSafe<unknown[]>(feedPath, []);
    const lastSummary = readJsonSafe<Record<string, unknown> | null>(summaryPath, null);
    res.json({
      events: Array.isArray(events) ? events : [],
      lastSummary,
    });
  });

  app.get("/api/evaluation", (_req, res) => {
    const jsonPath = path.join(PY_DIR, "data", "eval_report.json");
    const mdPath = path.join(PY_DIR, "data", "eval_report.md");
    const flagPath = path.join(PY_DIR, "data", "labels", "heldout_used.flag");
    const report = readJsonSafe<Record<string, unknown> | null>(jsonPath, null);
    const markdown = fs.existsSync(mdPath) ? fs.readFileSync(mdPath, "utf-8") : "";
    res.json({
      report,
      markdown,
      heldoutConsumed: fs.existsSync(flagPath),
    });
  });

  app.get("/api/mock/preview", (_req, res) => {
    const state = readMockState();
    const visible = state.locus_ai_summary_visible;
    const changelogEntries = [
      ...(visible
        ? [
            {
              date: "November 23, 2026",
              title: "Locus AI: summarize any thread in one click",
              body: "Starting today, Locus AI is available across all Free and Team workspaces. Click the Summarize button on any engineering discussion thread to generate instant decision bullets, assigned owners, and follow-up action items without leaving your channel.",
              isNewLaunch: true,
            },
          ]
        : []),
      {
        date: "November 12, 2026",
        title: "Faster Workspace Switching with Cmd+K",
        body: "Jump instantaneously between unread channels, direct messages, and saved threads using our rebuilt client-side command palette across macOS, Windows, and Linux desktop apps.",
        isNewLaunch: false,
      },
      {
        date: "November 4, 2026",
        title: "Inline Syntax Highlighting for Build Logs",
        body: "Paste multi-line stack traces, JSON payloads, and Terraform plans with automatic language detection and one-click line copying inside threaded replies.",
        isNewLaunch: false,
      },
      {
        date: "October 22, 2026",
        title: "Custom Quiet Hours by Timezone",
        body: "Configure predictable Do Not Disturb schedules per workspace timezone while allowing urgent PagerDuty incident mentions to break through when needed.",
        isNewLaunch: false,
      },
      {
        date: "October 10, 2026",
        title: "CSV Channel Audit Exports",
        body: "Workspace administrators can now download weekly channel membership and retention summaries directly from the security dashboard.",
        isNewLaunch: false,
      },
    ];

    const pricingPlans = [
      {
        name: "Free",
        price: "$0 / active user / month",
        features: [
          "Up to 10 workspace members",
          "90 days of searchable message history",
          "25 MB file upload limit",
          "Standard channel and thread messaging",
          ...(visible ? ["AI thread summaries"] : []),
        ],
      },
      {
        name: "Team",
        price: "$8 / active user / month",
        features: [
          "Unlimited members and message history",
          "250 MB engineering artifact sharing",
          "GitHub and Jira webhook alerts",
          "Role-based private channel controls",
        ],
      },
      {
        name: "Enterprise",
        price: "$18 / active user / month",
        features: [
          "SAML SSO and SCIM user provisioning",
          "99.99% uptime SLA guarantee",
          "Dedicated regional cloud hosting",
          "Compliance archival exports",
        ],
      },
    ];

    res.json({
      state,
      changelogEntries,
      pricingPlans,
    });
  });

  app.post("/api/mock/toggle", (_req, res) => {
    const caps = getCapabilities();
    if (!caps.mockToggleAvailable) {
      res.status(403).json({
        error: "Mock site toggle is disabled. Set LOCAL_MODE=1 on your local server environment to enable it.",
      });
      return;
    }
    const current = readMockState();
    const next = { locus_ai_summary_visible: !current.locus_ai_summary_visible };
    writeMockState(next);
    res.json({ state: next });
  });

  app.post("/api/pipeline/run", async (req, res) => {
    const caps = getCapabilities();
    if (!caps.localMode) {
      res.status(403).json({
        error: "Live pipeline execution requires LOCAL_MODE=1 configured on the server.",
      });
      return;
    }

    const { asOf, ablation = "full", dryRun = false } = (req.body ?? {}) as Record<string, unknown>;
    const isDryRun = dryRun === true;

    if (!isDryRun && !caps.hasKeys) {
      res.status(403).json({
        error: "Live LLM pipeline execution requires GEMINI_API_KEY or GROQ_API_KEY configured on the server.",
      });
      return;
    }

    if (!isValidIsoDate(asOf)) {
      res.status(400).json({ error: "Invalid asOf date. Expected YYYY-MM-DD." });
      return;
    }

    if (typeof ablation !== "string" || !VALID_ABLATIONS.has(ablation)) {
      res.status(400).json({ error: "Invalid ablation. Allowed: full, no_classifier, single_agent." });
      return;
    }

    const args = ["-m", "src.pipeline", "--as-of", asOf, "--ablation", ablation];
    if (isDryRun) args.push("--dry-run");

    try {
      const result = await runPythonModule(args, `pipeline:${ablation}`);
      if (result.code !== 0) {
        res.status(500).json({
          error: `Pipeline exited with non-zero status (${result.code}). Ensure local mock site or target URLs are reachable and keys are valid.`,
        });
        return;
      }

      const summaryFile = isDryRun ? "last_run_dryrun.json" : "last_run_summary.json";
      const feedFile = isDryRun ? "feed_dryrun.json" : "feed.json";
      const summary = readJsonSafe<Record<string, unknown> | null>(path.join(PY_DIR, "data", summaryFile), null);
      const events = readJsonSafe<unknown[]>(path.join(PY_DIR, "data", feedFile), []);
      res.json({ ok: true, summary, events });
    } catch (err) {
      const code = err instanceof Error ? err.message : "UNKNOWN";
      if (code === "CONCURRENT_RUN") {
        res.status(409).json({ error: "Another Python run is currently active. Wait for it to finish." });
        return;
      }
      if (code === "RUN_TIMEOUT") {
        res.status(504).json({ error: "Pipeline execution exceeded timeout and was terminated." });
        return;
      }
      res.status(500).json({ error: "Failed to start Python pipeline process." });
    }
  });

  app.post("/api/evaluate", async (req, res) => {
    const caps = getCapabilities();
    if (!caps.localMode) {
      res.status(403).json({
        error: "Evaluation runs require LOCAL_MODE=1 configured on the server.",
      });
      return;
    }

    const { split = "dev", ablation = "all", dryRun = false } = (req.body ?? {}) as Record<string, unknown>;
    if (split !== "dev") {
      res.status(403).json({
        error: "Only the 'dev' split may be executed from the web console. Held-out runs are CLI-only with --final.",
      });
      return;
    }

    const isDryRun = dryRun === true;
    if (!isDryRun && !caps.hasKeys) {
      res.status(403).json({
        error: "Live evaluation requires GEMINI_API_KEY or GROQ_API_KEY, or select Dry Run.",
      });
      return;
    }

    if (typeof ablation !== "string" || !VALID_EVAL_ABLATIONS.has(ablation)) {
      res.status(400).json({ error: "Invalid ablation. Allowed: all, full, no_classifier, single_agent." });
      return;
    }

    const args = ["-m", "src.evaluate", "--split", "dev", "--ablation", ablation];
    if (isDryRun) args.push("--dry-run");

    try {
      const result = await runPythonModule(args, `evaluate:dev:${ablation}`);
      if (result.code !== 0) {
        res.status(500).json({
          error: `Evaluation exited with non-zero status (${result.code}). Verify dataset labels and LLM configuration.`,
        });
        return;
      }

      const report = readJsonSafe<Record<string, unknown> | null>(
        path.join(PY_DIR, "data", "eval_report.json"),
        null
      );
      const mdPath = path.join(PY_DIR, "data", "eval_report.md");
      const markdown = fs.existsSync(mdPath) ? fs.readFileSync(mdPath, "utf-8") : "";
      res.json({ ok: true, report, markdown });
    } catch (err) {
      const code = err instanceof Error ? err.message : "UNKNOWN";
      if (code === "CONCURRENT_RUN") {
        res.status(409).json({ error: "Another Python run is currently active. Wait for it to finish." });
        return;
      }
      if (code === "RUN_TIMEOUT") {
        res.status(504).json({ error: "Evaluation exceeded timeout and was terminated." });
        return;
      }
      res.status(500).json({ error: "Failed to start Python evaluation process." });
    }
  });

  app.get("/api/repo/files", (_req, res) => {
    const files = collectRepoFiles(PY_DIR);
    res.json({ rootName: "competitor-tracker", files });
  });

  app.get("/api/repo/file", (req, res) => {
    const relPath = typeof req.query.path === "string" ? req.query.path : "";
    if (!relPath || relPath.includes("..")) {
      res.status(400).json({ error: "Invalid file path." });
      return;
    }
    const allowed = new Set(collectRepoFiles(PY_DIR));
    if (!allowed.has(relPath)) {
      res.status(404).json({ error: "File not found in verified repository snapshot." });
      return;
    }
    const absPath = path.resolve(PY_DIR, relPath);
    if (!absPath.startsWith(PY_DIR + path.sep)) {
      res.status(403).json({ error: "Access denied." });
      return;
    }
    const content = fs.readFileSync(absPath, "utf-8");
    res.json({ path: relPath, content });
  });

  app.get("/api/repo/zip", async (_req, res) => {
    try {
      const files = collectRepoFiles(PY_DIR);
      const zip = new JSZip();
      const rootFolder = zip.folder("competitor-tracker");
      if (!rootFolder) {
        res.status(500).json({ error: "Failed to create archive container." });
        return;
      }
      for (const rel of files) {
        const abs = path.resolve(PY_DIR, rel);
        rootFolder.file(rel, fs.readFileSync(abs));
      }
      const buffer = await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" });
      res.setHeader("Content-Type", "application/zip");
      res.setHeader("Content-Disposition", 'attachment; filename="competitor-tracker.zip"');
      res.send(buffer);
    } catch {
      res.status(500).json({ error: "Failed to package Python repository snapshot." });
    }
  });

  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distDir = path.resolve(ROOT_DIR, "dist");
    app.use(express.static(distDir));
    app.get("*", (_req, res) => {
      res.sendFile(path.join(distDir, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Competitor Tracker console listening on http://0.0.0.0:${PORT}`);
  });
}

startServer();
