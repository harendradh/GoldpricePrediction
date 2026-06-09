import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Target, Check, X, MessageSquareReply, GitBranch, User, Hash, ChevronDown, ExternalLink } from "lucide-react";
import { api } from "../lib/api";
import type { Finding, PRSummary } from "../lib/types";
import { Card, ConfidenceBar, EmptyState, PageHeader, SeverityPill, Skeleton, VerdictPill, Button } from "../components/ui";
import { cn, initials, avatarColor, relativeTime } from "../lib/utils";
import { useAtlasStore } from "../store/useAtlasStore";

export default function Triage() {
  const { prId } = useParams();
  const nav = useNavigate();
  const numericId = prId ? parseInt(prId, 10) : null;

  const selectedTeam = useAtlasStore(s => s.selectedTeam);
  const { data: prs } = useQuery({ queryKey: ["prs", "open", selectedTeam], queryFn: () => api.listPRs("open", selectedTeam, 100), refetchInterval: 30_000 });
  const queue = (prs ?? []).filter(p => p.awaiting_count > 0);

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Triage"
        subtitle="Findings awaiting human decision · Accept posts to GitHub on the next sync"
      />
      <div className="grid grid-cols-[320px_1fr] gap-5 items-start">
        <Queue prs={queue} currentId={numericId} onPick={id => nav(`/triage/${id}`)} />
        <PRDetail prId={numericId} firstQueueId={queue[0]?.id ?? null} />
      </div>
    </div>
  );
}

// ─── Queue (left rail) ─────────────────────────────────────
function Queue({ prs, currentId, onPick }: { prs: PRSummary[]; currentId: number | null; onPick: (id: number) => void }) {
  return (
    <Card className="sticky top-5 flex flex-col overflow-hidden" style={{ maxHeight: "calc(100vh - 160px)" }}>
      <div className="shrink-0 px-4 py-3 border-b border-ink-200 bg-gradient-to-r from-brand-50/70 to-transparent">
        <div className="flex items-center justify-between">
          <div className="text-sm font-bold text-ink-900 inline-flex items-center gap-2">
            <Target className="w-4 h-4 text-brand-500" />
            <span>Triage queue</span>
          </div>
          <span className="font-mono text-xs font-bold bg-brand-subtle text-brand-700 border border-brand-200 rounded-full px-2.5 py-0.5">
            {prs.length}
          </span>
        </div>
      </div>
      {/* flex-1 min-h-0 forces the scroll container to respect the card's max-height */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {prs.length === 0 ? (
          <EmptyState icon={<Check className="w-5 h-5" />} title="All clear" subtitle="No PRs awaiting triage." />
        ) : (
          <ul>{prs.map(pr => <QueueRow key={pr.id} pr={pr} active={pr.id === currentId} onClick={() => onPick(pr.id)} />)}</ul>
        )}
      </div>
    </Card>
  );
}

function QueueRow({ pr, active, onClick }: { pr: PRSummary; active: boolean; onClick: () => void }) {
  const av = avatarColor(pr.author);
  return (
    <li
      onClick={onClick}
      className={cn(
        "px-3.5 py-3 cursor-pointer border-l-[3px] transition-all flex items-start gap-2.5",
        active
          ? "bg-gradient-to-r from-brand-50 to-transparent border-l-brand-500"
          : "border-l-transparent hover:bg-ink-50",
      )}
    >
      <div
        className="w-7 h-7 shrink-0 rounded-full text-white text-[10.5px] font-bold inline-flex items-center justify-center shadow-sm"
        style={{ background: av }}
      >
        {initials(pr.author)}
      </div>
      <div className="min-w-0 flex-1">
        <div className={cn("font-mono text-[11.5px] font-semibold", active ? "text-brand-700" : "text-ink-500")}>#{pr.number} · {pr.author}</div>
        <div className="text-[12.5px] font-semibold text-ink-900 leading-snug line-clamp-2">{pr.title}</div>
        <div className="text-[10.5px] text-ink-500 mt-0.5">{pr.awaiting_count} awaiting · {relativeTime(pr.updated_at)}</div>
      </div>
    </li>
  );
}

// ─── PR detail (right) ─────────────────────────────────────
function PRDetail({ prId, firstQueueId }: { prId: number | null; firstQueueId: number | null }) {
  const nav = useNavigate();
  const activeId = prId ?? firstQueueId;

  if (activeId == null) {
    return (
      <Card>
        <EmptyState
          icon={<Target className="w-5 h-5" />}
          title="Pick a PR to triage"
          subtitle="Or wait for a new webhook to arrive — Atlas auto-registers any repo on first hit."
        />
      </Card>
    );
  }

  return <PRDetailLoaded id={activeId} onPickAnother={() => nav("/triage")} />;
}

function PRDetailLoaded({ id, onPickAnother }: { id: number; onPickAnother: () => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["pr", id], queryFn: () => api.getPR(id),
    refetchInterval: 30_000,
  });

  if (isLoading) {
    return (
      <Card>
        <div className="p-5 space-y-3">
          <Skeleton className="h-7 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-32 w-full" />
        </div>
      </Card>
    );
  }
  if (error || !data) {
    return <Card><EmptyState icon={<X className="w-5 h-5" />} title="Couldn't load PR" subtitle={(error as Error)?.message ?? "Unknown error"} /></Card>;
  }

  const { pr, findings } = data;
  const done = findings.filter(f => f.decision).length;
  const groups = new Map<string, Finding[]>();
  findings.forEach(f => { (groups.get(f.file) ?? groups.set(f.file, []).get(f.file)!).push(f); });

  return (
    <div className="space-y-4 animate-slide-up">
      {/* Hero summary card */}
      <Card>
        <div className="p-5 bg-gradient-to-br from-brand-50/40 via-white to-white">
          <div className="flex items-start gap-4">
            <div className="flex-1 min-w-0">
              <button onClick={onPickAnother} className="text-[11.5px] font-semibold text-brand-600 hover:text-brand-700 inline-flex items-center gap-1 mb-1.5">
                <ChevronDown className="w-3 h-3 rotate-90" /> Back to queue
              </button>
              <h2 className="text-lg font-bold text-ink-900 leading-tight">#{pr.number} · {pr.title}</h2>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] text-ink-500 mt-2">
                <span className="inline-flex items-center gap-1"><User className="w-3 h-3" /> <b className="text-ink-700 font-semibold">{pr.author}</b></span>
                <span className="inline-flex items-center gap-1"><GitBranch className="w-3 h-3" /> <b className="text-ink-700 font-semibold">{pr.branch}</b></span>
                <span className="inline-flex items-center gap-1"><Hash className="w-3 h-3" /> <b className="text-ink-700 font-semibold">{pr.repo}</b></span>
                <span>Reviewed {relativeTime(pr.updated_at)}</span>
              </div>
              <div className="flex flex-wrap items-center gap-2 mt-3">
                {pr.verdict && <VerdictPill verdict={pr.verdict} />}
                {pr.auto_posted_count > 0 && (
                  <span className="pill bg-blue-50 text-blue-700 border-blue-200">
                    <ExternalLink className="w-3 h-3" /> {pr.auto_posted_count} auto-posted
                  </span>
                )}
                {pr.awaiting_count > 0 && (
                  <span className="pill bg-amber-50 text-amber-700 border-amber-200">
                    {pr.awaiting_count} awaiting triage
                  </span>
                )}
              </div>
            </div>
            <div className="text-right shrink-0 min-w-[110px]">
              <div className="text-[11.5px] uppercase tracking-wider text-ink-500 font-semibold">Triaged</div>
              <div className="font-mono text-[28px] font-bold text-ink-900 leading-none mt-1">
                {done}<span className="text-ink-400">/{findings.length}</span>
              </div>
              <div className="w-full mt-2 h-1.5 bg-ink-100 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: findings.length ? `${(done / findings.length) * 100}%` : "0%" }}
                  transition={{ duration: 0.6, ease: [0.2, 0.8, 0.4, 1] }}
                  className="h-full bg-brand-grad"
                />
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Findings grouped by file */}
      {findings.length === 0 ? (
        <Card>
          <EmptyState icon={<Check className="w-5 h-5" />} title="No findings" subtitle="Atlas didn't surface anything for this PR." />
        </Card>
      ) : (
        Array.from(groups.entries()).map(([file, fs]) => (
          <Card key={file}>
            <div className="px-5 py-2.5 bg-ink-50 border-b border-ink-200 flex items-center justify-between">
              <code className="text-xs font-mono font-semibold text-ink-700">{file}</code>
              <span className="text-[11.5px] text-ink-500">{fs.length} finding{fs.length === 1 ? "" : "s"}</span>
            </div>
            <ul className="divide-y divide-ink-100">
              {fs.map(f => <FindingRow key={f.id} f={f} prId={id} />)}
            </ul>
          </Card>
        ))
      )}
    </div>
  );
}

// ─── Finding row ─────────────────────────────────────
function FindingRow({ f, prId }: { f: Finding; prId: number }) {
  const qc = useQueryClient();
  const { pushToast } = useAtlasStore();
  const [showFix, setShowFix] = useState(false);
  const mut = useMutation({
    mutationFn: (decision: "accept" | "dismiss") => api.triage(f.id, decision),
    onSuccess: (_, decision) => {
      qc.invalidateQueries({ queryKey: ["pr", prId] });
      qc.invalidateQueries({ queryKey: ["prs"] });
      pushToast(decision === "accept" ? "Accepted · will post on next sync" : "Dismissed · Atlas learns from this", "success");
    },
    onError: (e: Error) => pushToast("Failed: " + e.message, "error"),
  });

  const isAccepted = f.decision === "accept";
  const isDismissed = f.decision === "dismiss";

  return (
    <li className={cn(
      "px-5 py-4 grid grid-cols-[1fr_140px] gap-5 items-start transition-colors",
      isAccepted && "bg-emerald-50/60",
      isDismissed && "opacity-50",
    )}>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2.5 mb-2">
          <SeverityPill severity={f.severity} />
          <span className="font-mono text-[11.5px] text-ink-500">{f.rule_id}</span>
          <ConfidenceBar value={f.confidence} />
          <span className="ml-auto font-mono text-[11.5px] text-ink-500">:{f.line}</span>
        </div>
        <div className="text-[14px] font-semibold text-ink-900 mb-1.5 leading-snug">{f.title}</div>
        {f.quote && (
          <pre className="border-l-4 border-brand-500 bg-ink-900 text-ink-100 rounded-r-md px-3 py-2.5 font-mono text-[12px] leading-relaxed whitespace-pre-wrap break-words mb-2">
            {f.quote}
          </pre>
        )}
        <div className="text-[12.5px] text-ink-600 leading-relaxed" dangerouslySetInnerHTML={{ __html: f.why }} />
        {f.fix && (
          <div className="mt-3">
            <button onClick={() => setShowFix(s => !s)} className="text-[12px] font-semibold text-brand-600 hover:text-brand-700 inline-flex items-center gap-1">
              <ChevronDown className={cn("w-3.5 h-3.5 transition-transform", showFix && "rotate-180")} />
              {showFix ? "Hide" : "Show"} suggested fix
            </button>
            <AnimatePresence>
              {showFix && (
                <motion.pre
                  initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden mt-2 bg-ink-900 text-ink-100 rounded-md px-3 py-2.5 font-mono text-[12px] leading-relaxed whitespace-pre-wrap break-words"
                >{f.fix}</motion.pre>
              )}
            </AnimatePresence>
          </div>
        )}
        {f.auto_posted && (
          <div className="mt-2.5 text-[11.5px] font-semibold text-emerald-700 inline-flex items-center gap-1.5">
            <Check className="w-3 h-3" /> posted to GitHub
          </div>
        )}
      </div>
      <div className="flex flex-col gap-2">
        <Button variant="success" disabled={mut.isPending} onClick={() => mut.mutate("accept")}>
          <Check className="w-3.5 h-3.5" /> Accept
        </Button>
        <Button variant="danger" disabled={mut.isPending} onClick={() => mut.mutate("dismiss")}>
          <X className="w-3.5 h-3.5" /> Dismiss
        </Button>
        <Button variant="ghost">
          <MessageSquareReply className="w-3.5 h-3.5" /> Reply
        </Button>
      </div>
    </li>
  );
}
