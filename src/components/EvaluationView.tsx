import { useState } from "react";
import { Lock, Play, ShieldCheck } from "lucide-react";
import type { EvalReport, ServerCapabilities } from "../types";

interface EvaluationViewProps {
  report: EvalReport | null;
  markdown: string;
  heldoutConsumed: boolean;
  capabilities: ServerCapabilities;
  mode: "replay" | "live";
  onRefresh: () => Promise<void>;
}

const LEVELS = ["HIGH", "MEDIUM", "LOW"] as const;

export function EvaluationView({
  report,
  markdown,
  heldoutConsumed,
  capabilities,
  mode,
  onRefresh,
}: EvaluationViewProps) {
  const [selectedAblation, setSelectedAblation] = useState<string>("full");
  const [dryRun, setDryRun] = useState<boolean>(true);
  const [running, setRunning] = useState<boolean>(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [showMarkdown, setShowMarkdown] = useState<boolean>(false);

  const canExecuteDev = mode === "live" && capabilities.localMode && (dryRun || capabilities.hasKeys);

  const handleRunDevEval = async () => {
    setRunning(true);
    setRunError(null);
    try {
      const resp = await fetch("/api/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ split: "dev", ablation: "all", dryRun }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setRunError(data.error || "Evaluation run failed.");
      } else {
        await onRefresh();
      }
    } catch {
      setRunError("Network error contacting evaluation endpoint.");
    } finally {
      setRunning(false);
    }
  };

  const ablationKeys = report ? Object.keys(report.ablations) : [];
  const activeMatrixAblation =
    report && report.ablations[selectedAblation] ? selectedAblation : ablationKeys[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Ablation & Evaluation Harness
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Measures precision, recall, F1, threat accuracy, and false alerts across the 40-case stratified benchmark.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-600 bg-white border border-slate-200 rounded-md px-3 py-1.5">
          <Lock className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          <span className="whitespace-nowrap">
            Held-out Lock: {heldoutConsumed ? "Consumed (heldout_used.flag)" : "Locked CLI-only (--final)"}
          </span>
        </div>
      </div>

      {/* Dev Evaluation Control Bar */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1">
          <div className="text-sm font-medium text-slate-900">
            Dev Split Runner (python -m src.evaluate --split dev)
          </div>
          <p className="text-xs text-slate-500">
            {mode === "replay"
              ? "Replay mode displays committed data/eval_report.json. Held-out execution is strictly CLI-only."
              : "Runs all 3 ablations (full, no_classifier, single_agent) on the dev split only. Held-out remains locked to CLI --final."}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 shrink-0">
          {mode === "live" && (
            <label className="inline-flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                className="rounded border-slate-300 text-blue-700 focus:ring-blue-600"
              />
              Dry Run (FakeLLMClient)
            </label>
          )}
          <button
            type="button"
            disabled={!canExecuteDev || running}
            onClick={handleRunDevEval}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-blue-700 rounded-md hover:bg-blue-800 disabled:opacity-45 disabled:cursor-not-allowed transition-colors whitespace-nowrap shrink-0 cursor-pointer"
          >
            <Play className="w-3.5 h-3.5" />
            {running ? "Running Dev Eval..." : "Run Dev Evaluation"}
          </button>
        </div>
      </div>

      {runError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-xs text-red-800">
          {runError}
        </div>
      )}

      {!report ? (
        <div className="bg-white border border-slate-200 rounded-lg p-10 text-center">
          <p className="text-sm font-medium text-slate-900">No evaluation report available</p>
          <p className="mt-1 text-xs text-slate-500">
            Run python -m src.dataset and python -m src.evaluate --split dev --dry-run to generate metrics.
          </p>
        </div>
      ) : (
        <>
          {/* Provenance & Paired Comparison */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-1">
              <div className="text-xs font-medium text-slate-500">Evaluated Split & Provenance</div>
              <div className="text-sm font-semibold text-slate-900 font-mono">
                {report.split} · {report.num_cases} cases · {report.dry_run ? "dry-run" : "live"}
              </div>
              <div className="text-xs text-slate-500 font-mono truncate" title={report.prompt_hash}>
                Prompt SHA-256: {report.prompt_hash}
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-1">
              <div className="text-xs font-medium text-slate-500">
                False Alerts Delta (full - single_agent)
              </div>
              <div className="text-2xl font-semibold text-emerald-700 font-mono tabular-nums">
                {report.paired_diff?.false_alerts_diff !== undefined
                  ? report.paired_diff.false_alerts_diff
                  : "N/A"}
              </div>
              <div className="text-xs text-slate-500">
                Lower false alerts indicate fewer non-launches confirmed as threats.
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-1">
              <div className="text-xs font-medium text-slate-500">
                Classifier F1 Delta (full - single_agent)
              </div>
              <div className="text-2xl font-semibold text-blue-700 font-mono tabular-nums">
                {report.paired_diff?.classifier_f1_diff !== undefined
                  ? (report.paired_diff.classifier_f1_diff >= 0 ? "+" : "") +
                    report.paired_diff.classifier_f1_diff.toFixed(4)
                  : "N/A"}
              </div>
              <div className="text-xs text-slate-500">
                Measures isolation benefit over single-prompt bundling.
              </div>
            </div>
          </div>

          {/* Per-Ablation Comparison Table */}
          <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
            <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-900">Per-Ablation Metrics</h2>
              <button
                type="button"
                onClick={() => setShowMarkdown((v) => !v)}
                className="text-xs font-medium text-blue-700 hover:underline whitespace-nowrap shrink-0 cursor-pointer"
              >
                {showMarkdown ? "Hide Markdown Report" : "View Markdown Report"}
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-xs font-medium text-slate-600">
                    <th className="py-2.5 px-4">Ablation</th>
                    <th className="py-2.5 px-4 text-right">Precision</th>
                    <th className="py-2.5 px-4 text-right">Recall</th>
                    <th className="py-2.5 px-4 text-right">F1</th>
                    <th className="py-2.5 px-4 text-right">Threat Acc</th>
                    <th className="py-2.5 px-4 text-right">False Alerts</th>
                    <th className="py-2.5 px-4 text-right">Invalid Evid.</th>
                    <th className="py-2.5 px-4 text-right">Parse Fail</th>
                    <th className="py-2.5 px-4 text-right">Calls/Event</th>
                    <th className="py-2.5 px-4 text-right">Tokens/Event</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-xs">
                  {Object.entries(report.ablations).map(([name, m]) => (
                    <tr key={name} className="hover:bg-slate-50">
                      <td className="py-2.5 px-4 font-mono font-semibold text-slate-900">{name}</td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums">
                        {m.classifier.precision.toFixed(3)}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums">
                        {m.classifier.recall.toFixed(3)}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums font-semibold text-slate-900">
                        {m.classifier.f1.toFixed(3)}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums">
                        {m.analyst.threat_accuracy.toFixed(3)}
                      </td>
                      <td
                        className={`py-2.5 px-4 text-right font-mono tabular-nums font-semibold ${
                          m.false_alerts > 0 ? "text-red-700" : "text-emerald-700"
                        }`}
                      >
                        {m.false_alerts}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums">
                        {m.invalid_evidence}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums">
                        {m.parse_failures}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums">
                        {(m.avg_llm_calls_per_event ?? 0).toFixed(2)}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums">
                        {m.avg_tokens_per_event.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {showMarkdown && markdown && (
            <div className="bg-white border border-slate-200 rounded-lg p-5">
              <div className="text-xs font-semibold text-slate-700 mb-2">data/eval_report.md</div>
              <pre className="text-xs font-mono text-slate-800 whitespace-pre-wrap overflow-x-auto bg-slate-50 border border-slate-200 rounded p-4">
                {markdown}
              </pre>
            </div>
          )}

          {/* 3x3 Threat Confusion Matrix */}
          {activeMatrixAblation && (
            <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">
                    3×3 Threat Confusion Matrix (True Launches)
                  </h2>
                  <p className="text-xs text-slate-500">
                    Rows represent labeled ground-truth threat; columns represent Analyst predictions.
                  </p>
                </div>

                <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-md self-start">
                  {ablationKeys.map((abl) => (
                    <button
                      key={abl}
                      type="button"
                      onClick={() => setSelectedAblation(abl)}
                      className={`px-3 py-1.5 text-xs font-mono font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                        activeMatrixAblation === abl
                          ? "bg-white text-slate-900 border border-slate-200"
                          : "text-slate-600 hover:text-slate-900 border border-transparent"
                      }`}
                    >
                      {abl}
                    </button>
                  ))}
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full max-w-lg text-left border-collapse border border-slate-200">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-xs font-medium text-slate-600">
                      <th className="py-2.5 px-4 border-r border-slate-200">Actual \ Predicted</th>
                      {LEVELS.map((pred) => (
                        <th key={pred} className="py-2.5 px-4 text-right font-mono">
                          {pred}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 text-xs">
                    {LEVELS.map((actual) => (
                      <tr key={actual}>
                        <td className="py-2.5 px-4 font-mono font-semibold text-slate-900 border-r border-slate-200 bg-slate-50">
                          {actual}
                        </td>
                        {LEVELS.map((pred) => {
                          const val =
                            report.ablations[activeMatrixAblation].analyst.confusion_matrix[actual]?.[
                              pred
                            ] ?? 0;
                          const isDiag = actual === pred;
                          return (
                            <td
                              key={pred}
                              className={`py-2.5 px-4 text-right font-mono tabular-nums ${
                                isDiag
                                  ? "bg-emerald-50/70 font-semibold text-emerald-800"
                                  : "text-slate-700"
                              }`}
                            >
                              {val}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-start gap-2 text-xs text-slate-600">
                <ShieldCheck className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
                <span>
                  Three-layer held-out enforcement: <code className="font-mono">held_out_locked: true</code> in{" "}
                  <code className="font-mono">config.yaml</code>, mandatory <code className="font-mono">--final</code>{" "}
                  CLI flag, and atomic <code className="font-mono">data/labels/heldout_used.flag</code> lockfile.
                </span>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
