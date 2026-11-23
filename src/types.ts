export type ConsoleTab = "feed" | "evaluation" | "monitor" | "mock" | "export";

export type AblationMode = "full" | "no_classifier" | "single_agent";

export type EventStatus = "confirmed" | "dismissed" | "invalid_evidence" | "parse_failed";

export interface ServerCapabilities {
  defaultMode: "replay";
  localMode: boolean;
  hasKeys: boolean;
  liveAvailable: boolean;
  mockToggleAvailable: boolean;
  runActive: boolean;
  activeRunLabel: string | null;
  mockState: {
    locus_ai_summary_visible: boolean;
  };
  testsVerifiedCount: number;
}

export interface ClassifierOutput {
  is_feature_launch: boolean;
  category: "new_feature" | "bug_fix" | "cosmetic" | "blog_noise" | "pricing_change";
  feature_name: string | null;
  confidence: number;
}

export interface AnalystOutput {
  threat_level: "HIGH" | "MEDIUM" | "LOW";
  reasoning: string;
  evidence_quote: string;
  overlaps_roadmap_item: string | null;
  confidence: number;
}

export interface StrategistOutput {
  recommendation: "match" | "differentiate" | "ignore" | "monitor";
  actions: string[];
  contests_analyst: boolean;
  contest_reason: string | null;
}

export interface FeedEvent {
  event_id: string;
  competitor: string;
  page: string;
  as_of: string;
  detected_at: string;
  classifier: ClassifierOutput | null;
  analyst: AnalystOutput | null;
  strategist: StrategistOutput | null;
  status: EventStatus;
  contested: boolean;
  models: Record<string, string>;
  ablation: AblationMode;
  status_reason: string;
  tokens_approx: number;
}

export interface RunSummary {
  as_of: string;
  ablation: AblationMode;
  dry_run: boolean;
  pages_checked: number;
  baseline_pages: number;
  below_threshold: number;
  changed_events: number;
  counts: Record<EventStatus, number>;
  llm_calls: number;
  approx_tokens: number;
  digests: string[];
  ran_at: string;
}

export interface AblationMetrics {
  ablation: string;
  cases_evaluated: number;
  classifier: {
    tp: number;
    fp: number;
    fn: number;
    tn: number;
    precision: number;
    recall: number;
    f1: number;
  };
  analyst: {
    threat_accuracy: number;
    threat_total: number;
    confusion_matrix: Record<"HIGH" | "MEDIUM" | "LOW", Record<"HIGH" | "MEDIUM" | "LOW", number>>;
  };
  invalid_evidence: number;
  parse_failures: number;
  false_alerts: number;
  total_tokens: number;
  avg_tokens_per_event: number;
  total_llm_calls?: number;
  avg_llm_calls_per_event?: number;
}

export interface EvalReport {
  evaluated_at: string;
  split: "dev" | "heldout";
  num_cases: number;
  dry_run: boolean;
  prompt_hash: string;
  ablations: Record<string, AblationMetrics>;
  paired_diff: {
    false_alerts_diff?: number;
    classifier_f1_diff?: number;
  };
}

export interface MockPreviewData {
  state: {
    locus_ai_summary_visible: boolean;
  };
  changelogEntries: Array<{
    date: string;
    title: string;
    body: string;
    isNewLaunch: boolean;
  }>;
  pricingPlans: Array<{
    name: string;
    price: string;
    features: string[];
  }>;
}
