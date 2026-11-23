import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  MinusCircle,
  Search,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import type { EventStatus, FeedEvent } from "../types";

interface FeedViewProps {
  events: FeedEvent[];
  loading: boolean;
  error: string | null;
  mode: "replay" | "live";
  onGoToMonitor: () => void;
}

const STATUS_META: Record<
  EventStatus,
  { label: string; colorClass: string; Icon: typeof CheckCircle2 }
> = {
  confirmed: {
    label: "Confirmed",
    colorClass: "text-emerald-700 bg-emerald-50 border-emerald-200",
    Icon: CheckCircle2,
  },
  dismissed: {
    label: "Dismissed",
    colorClass: "text-slate-600 bg-slate-100 border-slate-200",
    Icon: MinusCircle,
  },
  invalid_evidence: {
    label: "Invalid Evidence",
    colorClass: "text-amber-700 bg-amber-50 border-amber-200",
    Icon: AlertTriangle,
  },
  parse_failed: {
    label: "Parse Failed",
    colorClass: "text-red-700 bg-red-50 border-red-200",
    Icon: XCircle,
  },
};

const THREAT_COLORS: Record<string, string> = {
  HIGH: "text-red-700 bg-red-50 border-red-200",
  MEDIUM: "text-amber-700 bg-amber-50 border-amber-200",
  LOW: "text-slate-700 bg-slate-100 border-slate-200",
};

export function FeedView({ events, loading, error, mode, onGoToMonitor }: FeedViewProps) {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [competitorFilter, setCompetitorFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});

  const competitors = useMemo(
    () => Array.from(new Set(events.map((e) => e.competitor))).sort(),
    [events]
  );

  const orderedEvents = useMemo(() => [...events].reverse(), [events]);

  const filteredEvents = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return orderedEvents.filter((ev) => {
      if (statusFilter !== "all" && ev.status !== statusFilter) return false;
      if (competitorFilter !== "all" && ev.competitor !== competitorFilter) return false;
      if (!q) return true;
      const featureName = ev.classifier?.feature_name ?? "";
      const quote = ev.analyst?.evidence_quote ?? "";
      const reason = ev.status_reason ?? "";
      return (
        featureName.toLowerCase().includes(q) ||
        quote.toLowerCase().includes(q) ||
        reason.toLowerCase().includes(q) ||
        ev.competitor.toLowerCase().includes(q) ||
        ev.page.toLowerCase().includes(q)
      );
    });
  }, [orderedEvents, statusFilter, competitorFilter, searchQuery]);

  const counts = useMemo(() => {
    const map: Record<string, number> = {
      total: events.length,
      confirmed: 0,
      dismissed: 0,
      invalid_evidence: 0,
      parse_failed: 0,
      contested: 0,
    };
    for (const ev of events) {
      map[ev.status] = (map[ev.status] ?? 0) + 1;
      if (ev.contested) map.contested += 1;
    }
    return map;
  }, [events]);

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Intelligence Feed
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Structured decisions recorded by Scribe across confirmed launches, dismissed noise, and evidence checks.
          </p>
        </div>
        <div className="text-xs text-slate-500 font-mono tabular-nums">
          Source: {mode === "replay" ? "data/feed.json (committed replay)" : "data/feed.json (live workspace)"}
        </div>
      </div>

      {/* Summary KPI strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">Total Events</div>
          <div className="mt-1 text-2xl font-semibold text-slate-900 font-mono tabular-nums">
            {counts.total}
          </div>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">Confirmed</div>
          <div className="mt-1 text-2xl font-semibold text-emerald-700 font-mono tabular-nums">
            {counts.confirmed}
          </div>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">Dismissed</div>
          <div className="mt-1 text-2xl font-semibold text-slate-700 font-mono tabular-nums">
            {counts.dismissed}
          </div>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">Invalid Evidence</div>
          <div className="mt-1 text-2xl font-semibold text-amber-700 font-mono tabular-nums">
            {counts.invalid_evidence}
          </div>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">Contested Ratings</div>
          <div className="mt-1 text-2xl font-semibold text-blue-700 font-mono tabular-nums">
            {counts.contested}
          </div>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-1 p-1 bg-slate-100 rounded-md">
          {(["all", "confirmed", "dismissed", "invalid_evidence", "parse_failed"] as const).map(
            (st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                  statusFilter === st
                    ? "bg-white text-slate-900 border border-slate-200"
                    : "text-slate-600 hover:text-slate-900 border border-transparent"
                }`}
              >
                {st === "all" ? "All Statuses" : STATUS_META[st].label}
              </button>
            )
          )}
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <select
            aria-label="Filter by competitor"
            value={competitorFilter}
            onChange={(e) => setCompetitorFilter(e.target.value)}
            className="h-9 px-3 text-xs font-medium bg-white border border-slate-200 rounded-md text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600"
          >
            <option value="all">All Competitors</option>
            {competitors.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search feature or quote..."
              className="h-9 pl-8 pr-3 text-xs bg-white border border-slate-200 rounded-md text-slate-800 placeholder:text-slate-400 w-full sm:w-60 focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>
        </div>
      </div>

      {/* Loading / Error / Empty / List */}
      {loading ? (
        <div className="bg-white border border-slate-200 rounded-lg divide-y divide-slate-200">
          {[1, 2, 3].map((idx) => (
            <div key={idx} className="p-5 animate-pulse space-y-2">
              <div className="h-4 w-1/3 bg-slate-200 rounded" />
              <div className="h-3 w-2/3 bg-slate-100 rounded" />
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-5 text-sm text-red-800">
          {error}
        </div>
      ) : filteredEvents.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-lg p-10 text-center">
          <p className="text-sm font-medium text-slate-900">No matching intelligence events</p>
          <p className="mt-1 text-xs text-slate-500">
            Adjust your status or competitor filters, or run a monitoring cycle in local Live mode.
          </p>
          {mode === "live" && (
            <button
              type="button"
              onClick={onGoToMonitor}
              className="mt-4 px-4 py-2 text-xs font-medium text-white bg-blue-700 rounded-md hover:bg-blue-800 transition-colors whitespace-nowrap shrink-0 cursor-pointer"
            >
              Open Pipeline Monitor
            </button>
          )}
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-lg divide-y divide-slate-200">
          {filteredEvents.map((ev) => {
            const isExpanded = Boolean(expandedIds[ev.event_id]);
            const meta = STATUS_META[ev.status] ?? STATUS_META.dismissed;
            const StatusIcon = meta.Icon;
            const title =
              ev.classifier?.feature_name ||
              (ev.classifier?.category ? `${ev.classifier.category} update` : `${ev.page} change`);
            const modelSummary = Object.entries(ev.models || {})
              .map(([agent, m]) => `${agent}: ${m}`)
              .join(" · ");

            return (
              <div key={ev.event_id} className="transition-colors">
                <button
                  type="button"
                  onClick={() => toggleExpand(ev.event_id)}
                  className="w-full text-left p-5 hover:bg-slate-50 transition-colors flex items-start justify-between gap-4 cursor-pointer"
                >
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium border rounded whitespace-nowrap shrink-0 ${meta.colorClass}`}
                      >
                        <StatusIcon className="w-3.5 h-3.5" />
                        {meta.label}
                      </span>

                      {ev.analyst?.threat_level && (
                        <span
                          className={`inline-flex items-center px-2 py-0.5 text-xs font-semibold font-mono border rounded whitespace-nowrap shrink-0 ${
                            THREAT_COLORS[ev.analyst.threat_level] ?? THREAT_COLORS.LOW
                          }`}
                        >
                          Threat: {ev.analyst.threat_level}
                        </span>
                      )}

                      {ev.contested && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium border border-blue-200 bg-blue-50 text-blue-800 rounded whitespace-nowrap shrink-0">
                          <ShieldAlert className="w-3.5 h-3.5" />
                          Strategist Contested
                        </span>
                      )}

                      <h3 className="text-base font-semibold text-slate-900 truncate">
                        {ev.competitor}: {title}
                      </h3>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <span className="font-mono">{ev.page}</span>
                      <span aria-hidden="true">·</span>
                      <span className="font-mono tabular-nums">{ev.as_of}</span>
                      <span aria-hidden="true">·</span>
                      <span className="font-mono tabular-nums">{ev.tokens_approx} approx tokens</span>
                      <span aria-hidden="true">·</span>
                      <span className="font-mono">ablation: {ev.ablation}</span>
                      <span aria-hidden="true">·</span>
                      <span className="font-mono">id: {ev.event_id}</span>
                    </div>

                    <p className="text-sm text-slate-700">{ev.status_reason}</p>
                  </div>

                  <div className="pt-1 text-slate-400 shrink-0">
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                  </div>
                </button>

                {isExpanded && (
                  <div className="px-5 pb-5 pt-2 border-t border-slate-100 bg-slate-50/60 space-y-4">
                    {ev.analyst?.evidence_quote && (
                      <div className="bg-white border border-slate-200 rounded-md p-3.5">
                        <div className="text-xs font-medium text-slate-500">
                          Verbatim Evidence Quote ({ev.status === "invalid_evidence" ? "Verification Failed" : "Verified in Snapshot"})
                        </div>
                        <blockquote className="mt-1 font-mono text-xs text-slate-800">
                          "{ev.analyst.evidence_quote}"
                        </blockquote>
                      </div>
                    )}

                    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                      <div className="bg-white border border-slate-200 rounded-md p-4 space-y-2">
                        <div className="text-xs font-semibold text-slate-900">1. Classifier</div>
                        {ev.classifier ? (
                          <dl className="space-y-1.5 text-xs">
                            <div className="flex justify-between gap-2">
                              <dt className="text-slate-500">Feature Launch</dt>
                              <dd className="font-mono font-medium text-slate-900">
                                {String(ev.classifier.is_feature_launch)}
                              </dd>
                            </div>
                            <div className="flex justify-between gap-2">
                              <dt className="text-slate-500">Category</dt>
                              <dd className="font-mono text-slate-900">{ev.classifier.category}</dd>
                            </div>
                            <div className="flex justify-between gap-2">
                              <dt className="text-slate-500">Confidence</dt>
                              <dd className="font-mono tabular-nums text-slate-900">
                                {ev.classifier.confidence.toFixed(2)}
                              </dd>
                            </div>
                          </dl>
                        ) : (
                          <p className="text-xs text-slate-500">Skipped in ablation mode.</p>
                        )}
                      </div>

                      <div className="bg-white border border-slate-200 rounded-md p-4 space-y-2">
                        <div className="text-xs font-semibold text-slate-900">2. Analyst</div>
                        {ev.analyst ? (
                          <div className="space-y-2 text-xs">
                            <div className="flex justify-between gap-2">
                              <span className="text-slate-500">Threat Level</span>
                              <span className="font-mono font-semibold text-slate-900">
                                {ev.analyst.threat_level}
                              </span>
                            </div>
                            <div className="flex justify-between gap-2">
                              <span className="text-slate-500">Roadmap Overlap</span>
                              <span className="font-mono text-slate-900 text-right">
                                {ev.analyst.overlaps_roadmap_item ?? "None"}
                              </span>
                            </div>
                            <p className="text-slate-700 leading-relaxed pt-1">
                              {ev.analyst.reasoning}
                            </p>
                          </div>
                        ) : (
                          <p className="text-xs text-slate-500">Not executed for this event.</p>
                        )}
                      </div>

                      <div className="bg-white border border-slate-200 rounded-md p-4 space-y-2">
                        <div className="text-xs font-semibold text-slate-900">3. Strategist</div>
                        {ev.strategist ? (
                          <div className="space-y-2 text-xs">
                            <div className="flex justify-between gap-2">
                              <span className="text-slate-500">Recommendation</span>
                              <span className="font-mono font-semibold text-blue-700">
                                {ev.strategist.recommendation}
                              </span>
                            </div>
                            {ev.strategist.contests_analyst && ev.strategist.contest_reason && (
                              <div className="p-2.5 bg-blue-50 border border-blue-200 rounded text-blue-900">
                                <span className="font-semibold">Contest rationale: </span>
                                {ev.strategist.contest_reason}
                              </div>
                            )}
                            <ul className="list-disc list-inside space-y-1 text-slate-700">
                              {ev.strategist.actions.map((act, idx) => (
                                <li key={idx}>{act}</li>
                              ))}
                            </ul>
                          </div>
                        ) : (
                          <p className="text-xs text-slate-500">Not executed (halted earlier).</p>
                        )}
                      </div>
                    </div>

                    {modelSummary && (
                      <div className="text-xs font-mono text-slate-500">
                        Models: {modelSummary}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
