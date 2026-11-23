import { useState } from "react";
import { Lock, RefreshCw } from "lucide-react";
import type { MockPreviewData, ServerCapabilities } from "../types";

interface MockSiteViewProps {
  preview: MockPreviewData | null;
  capabilities: ServerCapabilities;
  onRefresh: () => Promise<void>;
}

export function MockSiteView({ preview, capabilities, onRefresh }: MockSiteViewProps) {
  const [toggling, setToggling] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const visible = preview?.state.locus_ai_summary_visible ?? false;
  const toggleAllowed = capabilities.mockToggleAvailable;

  const handleToggle = async () => {
    if (!toggleAllowed) return;
    setToggling(true);
    setErrorMsg(null);
    try {
      const resp = await fetch("/api/mock/toggle", { method: "POST" });
      const data = await resp.json();
      if (!resp.ok) {
        setErrorMsg(data.error || "Failed to toggle mock state.");
      } else {
        await onRefresh();
      }
    } catch {
      setErrorMsg("Network error toggling mock state.");
    } finally {
      setToggling(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Mock Competitor Site: Locus
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Simulated competitor changelog and pricing pages backed by <code className="font-mono text-xs">mock_sites/state.json</code>.
          </p>
        </div>

        <button
          type="button"
          disabled={!toggleAllowed || toggling}
          onClick={handleToggle}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-blue-700 rounded-md hover:bg-blue-800 disabled:opacity-45 disabled:cursor-not-allowed transition-colors whitespace-nowrap shrink-0 cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${toggling ? "animate-spin" : ""}`} />
          {visible ? "Hide Locus AI Feature" : "Enable Locus AI Feature"}
        </button>
      </div>

      {!toggleAllowed && (
        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-start gap-3">
          <Lock className="w-4 h-4 text-slate-500 mt-0.5 shrink-0" />
          <div className="text-xs text-slate-600">
            <span className="font-semibold text-slate-900">Local-Only Toggle Locked:</span>{" "}
            The mock site toggle is strictly enabled when <code className="font-mono">LOCAL_MODE=1</code> is set in the server environment on your machine.
          </div>
        </div>
      )}

      {errorMsg && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-xs text-red-800">
          {errorMsg}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="text-slate-600">
          Current <code className="font-mono">locus_ai_summary_visible</code> flag:
        </span>
        <span
          className={`font-mono font-semibold px-2 py-0.5 rounded border ${
            visible
              ? "text-emerald-700 bg-emerald-50 border-emerald-200"
              : "text-slate-700 bg-slate-100 border-slate-200"
          }`}
        >
          {String(visible)}
        </span>
      </div>

      {preview && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 items-stretch">
          {/* Changelog Preview */}
          <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
            <div className="border-b border-slate-200 pb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-900">/changelog</h2>
              <span className="text-xs font-mono text-slate-500">
                {preview.changelogEntries.length} entries
              </span>
            </div>
            <div className="divide-y divide-slate-200">
              {preview.changelogEntries.map((entry, idx) => (
                <div key={idx} className="py-3 first:pt-0 last:pb-0 space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-mono text-slate-500">{entry.date}</span>
                    {entry.isNewLaunch && (
                      <span className="text-xs font-medium text-blue-700">Hidden Launch Active</span>
                    )}
                  </div>
                  <h3 className="text-sm font-semibold text-slate-900">{entry.title}</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">{entry.body}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Pricing Preview */}
          <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
            <div className="border-b border-slate-200 pb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-900">/pricing</h2>
              <span className="text-xs font-mono text-slate-500">3 tiers</span>
            </div>
            <div className="space-y-4">
              {preview.pricingPlans.map((plan) => (
                <div key={plan.name} className="border border-slate-200 rounded-md p-4 space-y-2">
                  <div className="flex items-baseline justify-between gap-2">
                    <h3 className="text-sm font-semibold text-slate-900">{plan.name}</h3>
                    <span className="text-xs font-mono text-slate-600">{plan.price}</span>
                  </div>
                  <ul className="list-disc list-inside space-y-1 text-xs text-slate-700">
                    {plan.features.map((feat, i) => (
                      <li
                        key={i}
                        className={
                          feat === "AI thread summaries" ? "font-semibold text-blue-700" : ""
                        }
                      >
                        {feat}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
