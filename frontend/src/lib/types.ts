// Matches backend Pydantic models in app/api/v1.py

export type Severity = "BLOCKER" | "MAJOR" | "MINOR" | "NIT";
export type Verdict = "merge" | "improve" | "block" | "running" | null;
export type PRStatus = "open" | "merged" | "closed" | "draft";

export interface PRSummary {
  id: number; repo: string; number: number; title: string;
  author: string; branch: string; status: PRStatus;
  verdict: Verdict; review_state: string;
  findings_count: number; awaiting_count: number; auto_posted_count: number;
  updated_at: string;
}

export interface Finding {
  id: number; rule_id: string; pack: string;
  severity: Severity; dimension: string;
  file: string; line: number; confidence: number;
  title: string; quote: string | null; why: string; fix: string | null;
  auto_posted: boolean; decision: "accept" | "dismiss" | "reply" | null;
}

export interface PRDetail { pr: PRSummary; findings: Finding[]; }

export interface Insights {
  total_prs: number; open_prs: number; blockers_caught: number;
  auto_posted: number; findings_total: number; auto_post_rate: number;
  top_rules: { rule_id: string; count: number }[];
}

export interface WebhookConfig {
  url_template: string; secret_set: boolean; events: string[];
  auto_post_threshold: number; block_on_blocker: boolean; run_on_draft_prs: boolean;
}

export interface Repo {
  id: number; full_name: string; team: string; enabled: boolean;
  default_branch: string; threshold_override: number | null;
  slack_url: string | null; notes: string | null;
  created_at: string; last_event_at: string | null;
  review_count: number; auto_registered: boolean;
}

export interface Team { id: string; label: string; }

export interface QuickReviewIn {
  review_id: string; title: string; files: string[];
  languages: string[]; context: string; priorities: Record<string, string>;
}

export interface QuickReviewOut { spec_path: string; invocation: string; }

// ── Chat assistant ──────────────────────────────────────────
export interface ChatMessage { role: "user" | "assistant"; content: string; }
export interface ChatContext {
  page?: string;                  // inbox | triage | insights | scorecard | change-briefs | ledger | settings
  current_pr_id?: number;
  current_finding_id?: number;
  selected_team?: string;         // active team filter from the TopBar
}
export interface ChatIn { messages: ChatMessage[]; context: ChatContext; }
export interface ChatOut { role: "assistant"; content: string; }

// ── Engineering Health Scorecard ────────────────────────────
export interface ScorecardMetrics {
  team: string;
  team_label: string;
  window_days: number;
  total_prs: number;
  open_prs: number;
  findings_total: number;
  findings_per_pr: number;
  blockers_caught: number;
  blocker_leakage_rate: number;
  dismissal_rate: number;
  auto_post_rate: number;
  median_cycle_time_hours: number | null;
  queue_depth: number;
  dimension_mix: Record<string, number>;
  top_reviewers: { user: string; decisions: number }[];
  daily_findings: { date: string; count: number }[];
}

// ── CAB Brief ───────────────────────────────────────────────
export interface CABBrief {
  pr_id: number;
  repo: string;
  number: number;
  title: string;
  generated_at: string;
  markdown: string;
  risk_level: "low" | "medium" | "high";
}

// ── AI Decision Ledger ──────────────────────────────────────
export interface LedgerEntry {
  id: string;
  timestamp: string;
  kind: "finding" | "decision" | "audit" | "review";
  actor: string;
  title: string;
  detail: string;
  severity?: Severity | null;
  pr_id?: number | null;
  pr_number?: number | null;
  repo?: string | null;
  team?: string | null;
  finding_id?: number | null;
  decision?: "accept" | "dismiss" | "reply" | null;
}

export interface LedgerPage {
  entries: LedgerEntry[];
  total: number;
  window_days: number;
  team: string;
}
