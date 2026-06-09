import type {
  PRSummary, PRDetail, Insights, WebhookConfig, Repo, Team,
  QuickReviewIn, QuickReviewOut,
  ChatIn, ChatOut,
  ScorecardMetrics, CABBrief, LedgerPage,
} from "./types";

// Dev: Vite proxies /api → http://127.0.0.1:8000
// Prod (nginx): same /api proxy
const API_BASE = "/api/v1";

class HttpError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function _fetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
    ...init,
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new HttpError(r.status, `${r.status} ${r.statusText} on ${path}${text ? ": " + text.slice(0, 200) : ""}`);
  }
  if (r.status === 204) return undefined as T;
  const ct = r.headers.get("content-type") || "";
  return (ct.includes("application/json") ? r.json() : r.text()) as Promise<T>;
}

export const api = {
  health:        () => _fetch<{ status: string }>("/health"),

  listPRs:       (status = "open", team = "all", limit = 50) =>
    _fetch<PRSummary[]>(`/pull-requests?status=${encodeURIComponent(status)}&team=${encodeURIComponent(team)}&limit=${limit}`),
  listTeams:     () => _fetch<Team[]>("/teams"),
  getPR:         (id: number) => _fetch<PRDetail>(`/pull-requests/${id}`),

  triage:        (findingId: number, decision: "accept" | "dismiss" | "reply", note = "") =>
    _fetch<{ status: string }>(`/findings/${findingId}/triage`, {
      method: "POST", body: JSON.stringify({ decision, note, user: "console-user" }),
    }),

  insights:      () => _fetch<Insights>("/insights"),

  listRepos:     () => _fetch<Repo[]>("/repos"),
  createRepo:    (b: Partial<Repo>) => _fetch<Repo>("/repos", { method: "POST", body: JSON.stringify(b) }),
  updateRepo:    (id: number, b: Partial<Repo>) =>
    _fetch<Repo>(`/repos/${id}`, { method: "PATCH", body: JSON.stringify(b) }),
  deleteRepo:    (id: number) => _fetch<void>(`/repos/${id}`, { method: "DELETE" }),
  webhookCfg:    () => _fetch<WebhookConfig>("/webhook-config"),

  quickReview:   (b: QuickReviewIn) =>
    _fetch<QuickReviewOut>("/quick-review", { method: "POST", body: JSON.stringify(b) }),

  chat:          (b: ChatIn) =>
    _fetch<ChatOut>("/chat", { method: "POST", body: JSON.stringify(b) }),

  // Engineering Intelligence + Governance
  scorecard:     (team = "all", days = 30) =>
    _fetch<ScorecardMetrics>(`/scorecard?team=${encodeURIComponent(team)}&days=${days}`),
  cabBrief:      (prId: number) =>
    _fetch<CABBrief>(`/cab-brief/${prId}`, { method: "POST" }),
  ledger:        (params: { team?: string; days?: number; decision?: string; q?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.team)     qs.set("team", params.team);
    if (params.days)     qs.set("days", String(params.days));
    if (params.decision) qs.set("decision", params.decision);
    if (params.q)        qs.set("q", params.q);
    if (params.limit)    qs.set("limit", String(params.limit));
    return _fetch<LedgerPage>(`/ledger?${qs.toString()}`);
  },
};
