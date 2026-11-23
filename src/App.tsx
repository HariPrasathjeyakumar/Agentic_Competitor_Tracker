import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  BarChart3,
  Download,
  FolderArchive,
  Globe,
  ListFilter,
  Lock,
} from "lucide-react";
import { EvaluationView } from "./components/EvaluationView";
import { ExportView } from "./components/ExportView";
import { FeedView } from "./components/FeedView";
import { MockSiteView } from "./components/MockSiteView";
import { MonitorView } from "./components/MonitorView";
import type {
  ConsoleTab,
  EvalReport,
  FeedEvent,
  MockPreviewData,
  RunSummary,
  ServerCapabilities,
} from "./types";

const DEFAULT_CAPABILITIES: ServerCapabilities = {
  defaultMode: "replay",
  localMode: false,
  hasKeys: false,
  liveAvailable: false,
  mockToggleAvailable: false,
  runActive: false,
  activeRunLabel: null,
  mockState: { locus_ai_summary_visible: false },
  testsVerifiedCount: 22,
};

const NAV_ITEMS: Array<{ id: ConsoleTab; label: string; Icon: typeof ListFilter }> = [
  { id: "feed", label: "Intelligence Feed", Icon: ListFilter },
  { id: "evaluation", label: "Evaluation", Icon: BarChart3 },
  { id: "monitor", label: "Monitor", Icon: Activity },
  { id: "mock", label: "Mock Site", Icon: Globe },
  { id: "export", label: "Python Export", Icon: FolderArchive },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<ConsoleTab>("feed");
  const [mode, setMode] = useState<"replay" | "live">("replay");
  const [capabilities, setCapabilities] = useState<ServerCapabilities>(DEFAULT_CAPABILITIES);
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [lastSummary, setLastSummary] = useState<RunSummary | null>(null);
  const [feedLoading, setFeedLoading] = useState<boolean>(true);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [evalReport, setEvalReport] = useState<EvalReport | null>(null);
  const [evalMarkdown, setEvalMarkdown] = useState<string>("");
  const [heldoutConsumed, setHeldoutConsumed] = useState<boolean>(false);
  const [mockPreview, setMockPreview] = useState<MockPreviewData | null>(null);

  const loadAllData = useCallback(async () => {
    setFeedLoading(true);
    setFeedError(null);
    try {
      const [statusRes, feedRes, evalRes, mockRes] = await Promise.all([
        fetch("/api/status"),
        fetch("/api/feed"),
        fetch("/api/evaluation"),
        fetch("/api/mock/preview"),
      ]);

      if (statusRes.ok) {
        const st = (await statusRes.json()) as ServerCapabilities;
        setCapabilities(st);
        if (!st.liveAvailable) {
          setMode("replay");
        }
      }

      if (feedRes.ok) {
        const fd = await feedRes.json();
        setEvents(Array.isArray(fd.events) ? fd.events : []);
        setLastSummary(fd.lastSummary ?? null);
      } else {
        setFeedError("Unable to load committed intelligence feed.");
      }

      if (evalRes.ok) {
        const ev = await evalRes.json();
        setEvalReport(ev.report ?? null);
        setEvalMarkdown(typeof ev.markdown === "string" ? ev.markdown : "");
        setHeldoutConsumed(Boolean(ev.heldoutConsumed));
      }

      if (mockRes.ok) {
        const mk = (await mockRes.json()) as MockPreviewData;
        setMockPreview(mk);
      }
    } catch {
      setFeedError("Failed to connect to the Competitor Tracker backend.");
    } finally {
      setFeedLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAllData();
  }, [loadAllData]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
      {/* Three-Zone Top Bar Contract */}
      <header className="bg-white border-b border-slate-200 px-6 h-14 flex items-center justify-between gap-8 sticky top-0 z-20">
        <a
          href="#feed"
          onClick={(e) => {
            e.preventDefault();
            setActiveTab("feed");
          }}
          className="text-base font-bold tracking-tight text-slate-900 whitespace-nowrap shrink-0"
        >
          Competitor Tracker
        </a>

        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-600">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveTab(item.id)}
              className={`whitespace-nowrap shrink-0 py-1 border-b-2 transition-colors cursor-pointer ${
                activeTab === item.id
                  ? "text-slate-900 border-blue-700"
                  : "text-slate-600 border-transparent hover:text-slate-900"
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-3 shrink-0">
          <a
            href="/api/repo/zip"
            download="competitor-tracker.zip"
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-slate-900 rounded-md hover:bg-slate-800 transition-colors whitespace-nowrap shrink-0"
          >
            <Download className="w-3.5 h-3.5" />
            Export Python ZIP
          </a>
        </div>
      </header>

      {/* Main Workspace Layout: Sidebar + Content Viewport */}
      <div className="flex-1 flex flex-col lg:flex-row">
        <aside className="w-full lg:w-60 shrink-0 bg-white border-b lg:border-b-0 lg:border-r border-slate-200 p-4 flex flex-col justify-between gap-6">
          <div className="space-y-5">
            {/* Workspace Mode Switch (Default Replay; Live only when LOCAL_MODE=1 & keys set) */}
            <div className="space-y-2">
              <div className="text-xs font-semibold text-slate-500">Workspace Mode</div>
              {capabilities.liveAvailable ? (
                <div className="grid grid-cols-2 gap-1 p-1 bg-slate-100 rounded-md">
                  <button
                    type="button"
                    onClick={() => setMode("replay")}
                    className={`py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                      mode === "replay"
                        ? "bg-white text-slate-900 border border-slate-200"
                        : "text-slate-600 hover:text-slate-900 border border-transparent"
                    }`}
                  >
                    Replay
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("live")}
                    className={`py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                      mode === "live"
                        ? "bg-white text-blue-700 border border-slate-200"
                        : "text-slate-600 hover:text-slate-900 border border-transparent"
                    }`}
                  >
                    Live
                  </button>
                </div>
              ) : (
                <div className="border border-slate-200 bg-slate-50 rounded-md p-3 space-y-1">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-900">
                    <Lock className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                    Replay Mode (Default)
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    Reads committed feed & eval artifacts. Live runs activate only with{" "}
                    <code className="font-mono">LOCAL_MODE=1</code> and API keys set.
                  </p>
                </div>
              )}
            </div>

            {/* Sidebar Navigation */}
            <nav className="space-y-1">
              <div className="text-xs font-semibold text-slate-500 px-2 pb-1">Views</div>
              {NAV_ITEMS.map(({ id, label, Icon }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setActiveTab(id)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium rounded-md transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                    activeTab === id
                      ? "bg-blue-50 text-blue-800 border border-blue-200"
                      : "text-slate-700 hover:bg-slate-50 border border-transparent"
                  }`}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span>{label}</span>
                </button>
              ))}
            </nav>
          </div>

          <div className="hidden lg:block pt-4 border-t border-slate-200 space-y-1.5 text-xs text-slate-500">
            <div className="font-medium text-slate-700">Engine Architecture</div>
            <div>Target Product: TeamChat</div>
            <div>Competitor: Locus</div>
            <div className="font-mono tabular-nums">
              Engine: Python ({capabilities.testsVerifiedCount} tests)
            </div>
          </div>
        </aside>

        <main className="flex-1 min-w-0 p-6 lg:p-8">
          <div className="max-w-6xl mx-auto">
            {activeTab === "feed" && (
              <FeedView
                events={events}
                loading={feedLoading}
                error={feedError}
                mode={mode}
                onGoToMonitor={() => setActiveTab("monitor")}
              />
            )}

            {activeTab === "evaluation" && (
              <EvaluationView
                report={evalReport}
                markdown={evalMarkdown}
                heldoutConsumed={heldoutConsumed}
                capabilities={capabilities}
                mode={mode}
                onRefresh={loadAllData}
              />
            )}

            {activeTab === "monitor" && (
              <MonitorView
                mode={mode}
                capabilities={capabilities}
                lastSummary={lastSummary}
                onCycleCompleted={loadAllData}
              />
            )}

            {activeTab === "mock" && (
              <MockSiteView
                preview={mockPreview}
                capabilities={capabilities}
                onRefresh={loadAllData}
              />
            )}

            {activeTab === "export" && (
              <ExportView testsVerifiedCount={capabilities.testsVerifiedCount} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
