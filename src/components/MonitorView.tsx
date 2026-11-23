import { useState } from "react";
import { Lock, Play } from "lucide-react";
import type { AblationMode, RunSummary, ServerCapabilities } from "../types";

interface MonitorViewProps {
  mode: "replay" | "live";
  capabilities: ServerCapabilities;
  lastSummary: RunSummary | null;
  onCycleCompleted: () => Promise<void>;
}

export function MonitorView({
  mode,
  capabilities,
  lastSummary,
  onCycleCompleted,
}: MonitorViewProps) {
  const [asOf, setAsOf] = useState<string>("2026-11-23");
  const [ablation, setAblation] = useState<AblationMode>("full");
  const [dryRun, setDryRun] = useState<boolean>(false);
  const [running, setRunning] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [liveSummary, setLiveSummary] = useState<RunSummary | null>(null);

  const activeSummary = liveSummary ?? lastSummary;
  const canRun = mode === "live" && capabilities.localMode && (dryRun || capabilities.hasKeys);

  const handleRunCycle = async () => {
    setRunning(true);
    setErrorMsg(null);
    try {
      const resp = await fetch("/api/pipeline/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asOf, ablation, dryRun }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setErrorMsg(data.error || "Pipeline execution failed.");
      } else {
        setLiveSummary(data.summary ?? null);
        await onCycleCompleted();
      }
    } catch {
      setErrorMsg("Network error executing monitor cycle.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Pipeline Monitor
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Invokes <code className="font-mono text-xs">python -m src.pipeline</code> with strict information barriers across Scout, Diff-Engine, Classifier, Analyst, Evidence Check, Strategist, and Scribe.
        </p>
      </div>

      {mode === "replay" ? (
        <div className="bg-white border border-slate-200 rounded-lg p-5 flex items-start gap-3">
          <Lock className="w-4 h-4 text-slate-500 mt-0.5 shrink-0" />
          <div className="space-y-1 text-sm">
            <div className="font-medium text-slate-900">
              Replay Mode Active (Read-Only Snapshot)
            </div>
            <p className="text-xs text-slate-600">
              Live execution requires <code className="font-mono">LOCAL_MODE=1</code> and valid API keys configured on a local server. Below is the most recent saved run summary from <code className="font-mono">data/last_run_summary.json</code>.
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label htmlFor="as-of-input" className="block text-xs font-medium text-slate-700 mb-1.5">
                As-of Date (YYYY-MM-DD)
              </label>
              <input
                id="as-of-input"
                type="date"
                value={asOf}
                onChange={(e) => setAsOf(e.target.value)}
                className="w-full h-9 px-3 text-xs font-mono bg-white border border-slate-200 rounded-md text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>

            <div>
              <label htmlFor="ablation-select" className="block text-xs font-medium text-slate-700 mb-1.5">
                Ablation Mode
              </label>
              <select
                id="ablation-select"
                value={ablation}
                onChange={(e) => setAblation(e.target.value as AblationMode)}
                className="w-full h-9 px-3 text-xs font-mono bg-white border border-slate-200 rounded-md text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                <option value="full">full (Classifier + Analyst + Evidence + Strategist)</option>
                <option value="no_classifier">no_classifier (Skip Classifier)</option>
                <option value="single_agent">single_agent (Collapsed Baseline)</option>
              </select>
            </div>

            <div className="flex flex-col justify-end">
              <label className="inline-flex items-center gap-2 text-xs font-medium text-slate-700 mb-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                  className="rounded border-slate-300 text-blue-700 focus:ring-blue-600"
                />
                Dry Run (FakeLLMClient)
              </label>
              <button
                type="button"
                disabled={!canRun || running}
                onClick={handleRunCycle}
                className="h-9 inline-flex items-center justify-center gap-2 px-4 text-xs font-medium text-white bg-blue-700 rounded-md hover:bg-blue-800 disabled:opacity-45 disabled:cursor-not-allowed transition-colors whitespace-nowrap shrink-0 cursor-pointer"
              >
                <Play className="w-3.5 h-3.5" />
                {running ? "Executing Python Pipeline..." : "Run Monitor Cycle"}
              </button>
            </div>
          </div>

          {errorMsg && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md text-xs text-red-800">
              {errorMsg}
            </div>
          )}
        </div>
      )}

      {/* Last Run Summary */}
      {activeSummary ? (
        <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-slate-900">Last Pipeline Run Summary</h2>
            <div className="text-xs font-mono text-slate-500">
              as_of: {activeSummary.as_of} · ablation: {activeSummary.ablation} ·{" "}
              {activeSummary.dry_run ? "dry-run" : "live"}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="border border-slate-200 rounded-md p-3">
              <div className="text-xs text-slate-500">Pages Checked</div>
              <div className="mt-1 text-xl font-semibold font-mono tabular-nums text-slate-900">
                {activeSummary.pages_checked}
              </div>
            </div>
            <div className="border border-slate-200 rounded-md p-3">
              <div className="text-xs text-slate-500">Changed Events</div>
              <div className="mt-1 text-xl font-semibold font-mono tabular-nums text-slate-900">
                {activeSummary.changed_events}
              </div>
            </div>
            <div className="border border-slate-200 rounded-md p-3">
              <div className="text-xs text-slate-500">LLM Calls</div>
              <div className="mt-1 text-xl font-semibold font-mono tabular-nums text-slate-900">
                {activeSummary.llm_calls}
              </div>
            </div>
            <div className="border border-slate-200 rounded-md p-3">
              <div className="text-xs text-slate-500">Approx Tokens</div>
              <div className="mt-1 text-xl font-semibold font-mono tabular-nums text-slate-900">
                {activeSummary.approx_tokens}
              </div>
            </div>
          </div>

          {activeSummary.digests && activeSummary.digests.length > 0 && (
            <div className="space-y-1.5 pt-2 border-t border-slate-100">
              <div className="text-xs font-medium text-slate-600">Scribe Stdout Digest</div>
              <div className="bg-slate-50 border border-slate-200 rounded-md p-3 space-y-1 font-mono text-xs text-slate-800">
                {activeSummary.digests.map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-lg p-6 text-xs text-slate-500">
          No run summary recorded yet.
        </div>
      )}

      {/* Reproducible Day 1 / Day 9 Sequence */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
        <h2 className="text-sm font-semibold text-slate-900">
          Reproducible Day 1 / Day 9 Live Demo Sequence
        </h2>
        <p className="text-xs text-slate-600">
          Timestamped snapshot IDs (<code className="font-mono">YYYY-MM-DD_HHMMSS_ffffff.md</code>) prevent same-day overwrites, and <code className="font-mono">min_diff_chars: 60</code> lets short real announcements reach the Classifier.
        </p>
        <ol className="list-decimal list-inside space-y-2 text-xs text-slate-700">
          <li>
            Start the local Flask competitor site: <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">python mock_sites/app.py</code>
          </li>
          <li>
            Capture Day 1 baseline scans (feature hidden): <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">python -m src.pipeline --as-of 2026-11-15</code>
          </li>
          <li>
            Toggle Locus AI feature visible via <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">POST http://127.0.0.1:5001/toggle</code> or the local-only Mock Site tab.
          </li>
          <li>
            Run Day 9 scan to detect the launch: <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">python -m src.pipeline --as-of 2026-11-23</code>
          </li>
        </ol>
      </div>
    </div>
  );
}
