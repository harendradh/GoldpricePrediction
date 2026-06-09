import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Inbox as InboxIcon, ChevronRight, GitPullRequest, Zap } from "lucide-react";
import { api } from "../lib/api";
import { cn, relativeTime } from "../lib/utils";
import { Card, CardHead, PageHeader, EmptyState, Skeleton, VerdictPill } from "../components/ui";
import { useAtlasStore } from "../store/useAtlasStore";
import type { PRStatus, PRSummary } from "../lib/types";

const statusChips: { id: PRStatus | "all"; label: string }[] = [
  { id: "open",   label: "Open"   },
  { id: "merged", label: "Merged" },
  { id: "closed", label: "Closed" },
  { id: "all",    label: "All"    },
];

export default function Inbox() {
  const [status, setStatus] = useState<PRStatus | "all">("open");
  const selectedTeam = useAtlasStore(s => s.selectedTeam);
  const nav = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ["prs", status, selectedTeam],
    queryFn: () => api.listPRs(status, selectedTeam, 100),
    refetchInterval: 10_000,
    retry: 5,
    retryDelay: 2_000,
  });

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Inbox"
        subtitle="PRs reviewed by ChangePilot — click any row to triage."
      />

      <Card>
        <CardHead
          title="Recent reviews"
          hint={data ? `${data.length} pull request${data.length === 1 ? "" : "s"}` : ""}
        />

        {/* Filter chips */}
        <div className="px-5 py-3 border-b border-ink-200 bg-gradient-to-r from-brand-50/50 to-transparent flex items-center gap-2">
          {statusChips.map(c => (
            <button
              key={c.id}
              onClick={() => setStatus(c.id)}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border transition-all",
                status === c.id
                  ? "bg-brand-grad text-white border-transparent shadow-glow"
                  : "bg-white text-ink-600 border-ink-200 hover:border-brand-400 hover:text-brand-600",
              )}
            >
              {c.label}
            </button>
          ))}
        </div>

        {isLoading ? (
          <SkeletonRows />
        ) : error ? (
          <EmptyState
            icon={<Zap className="w-5 h-5" />}
            title="Couldn't reach the backend"
            subtitle={(error as Error).message}
          />
        ) : !data || data.length === 0 ? (
          <EmptyState
            icon={<InboxIcon className="w-5 h-5" />}
            title={selectedTeam === "all" ? "No reviews yet" : "No PRs for this team"}
            subtitle={
              selectedTeam === "all"
                ? "Open a PR on a connected repo, or use Quick Review for an ad-hoc check."
                : "Switch to All teams in the top bar, or assign repos to this team in Settings."
            }
          />
        ) : (
          <ul className="divide-y divide-ink-100">
            {data.map(pr => <Row key={pr.id} pr={pr} onOpen={id => nav(`/triage/${id}`)} />)}
          </ul>
        )}
      </Card>
    </div>
  );
}

function Row({ pr, onOpen }: { pr: PRSummary; onOpen: (id: number) => void }) {
  return (
    <li
      onClick={() => onOpen(pr.id)}
      className="group grid grid-cols-[60px_1fr_130px_180px_130px_70px_24px] items-center gap-4 px-5 py-3.5 cursor-pointer
                 hover:bg-gradient-to-r hover:from-brand-50/40 hover:to-transparent transition-colors"
    >
      <div className="font-mono text-xs font-semibold text-ink-500">#{pr.number}</div>
      <div className="min-w-0">
        <div className="text-sm font-semibold text-ink-900 truncate group-hover:text-brand-700">
          <GitPullRequest className="inline w-3.5 h-3.5 mr-1.5 -mt-px text-ink-400 group-hover:text-brand-500" />
          {pr.title}
        </div>
        <div className="text-[11.5px] text-ink-500 mt-0.5">{pr.author} · {pr.repo}</div>
      </div>
      <div>{pr.verdict ? <VerdictPill verdict={pr.verdict} /> : <VerdictPill verdict={pr.review_state} />}</div>
      <div className="font-mono text-xs text-ink-600">
        <span className="font-semibold">{pr.findings_count}</span> finding{pr.findings_count === 1 ? "" : "s"}
        {pr.awaiting_count > 0 && <span className="ml-2 text-amber-700">· {pr.awaiting_count} to triage</span>}
      </div>
      <div className="text-[11.5px] text-ink-500">
        {pr.auto_posted_count > 0 ? <span className="inline-flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />{pr.auto_posted_count} auto-posted</span> : ""}
      </div>
      <div className="text-[11.5px] text-ink-500 text-right font-mono">{relativeTime(pr.updated_at)}</div>
      <ChevronRight className="w-4 h-4 text-ink-300 group-hover:text-brand-500 group-hover:translate-x-1 transition-all" />
    </li>
  );
}

function SkeletonRows() {
  return (
    <div className="divide-y divide-ink-100">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="grid grid-cols-[60px_1fr_130px_180px_130px_70px] items-center gap-4 px-5 py-4">
          <Skeleton className="h-4 w-12" />
          <div className="space-y-1.5"><Skeleton className="h-4 w-3/4" /><Skeleton className="h-3 w-1/2" /></div>
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-3 w-12" />
        </div>
      ))}
    </div>
  );
}
