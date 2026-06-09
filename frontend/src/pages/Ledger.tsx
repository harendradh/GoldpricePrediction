import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  History, Search, Sparkles, CheckCircle2, XCircle, MessageSquare,
  AlertCircle, Activity, Zap, ExternalLink,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Card, CardHead, EmptyState, PageHeader, Skeleton } from "../components/ui";
import { useAtlasStore } from "../store/useAtlasStore";
import { cn, relativeTime } from "../lib/utils";
import type { LedgerEntry } from "../lib/types";

const WINDOWS = [
  { id: 7,  label: "7d"  },
  { id: 30, label: "30d" },
  { id: 90, label: "90d" },
];

const DECISIONS = [
  { id: "",         label: "All decisions" },
  { id: "accept",   label: "Accepted"      },
  { id: "dismiss",  label: "Dismissed"     },
  { id: "reply",    label: "Replied"       },
];

export default function Ledger() {
  const selectedTeam = useAtlasStore(s => s.selectedTeam);
  const [days, setDays] = useState(30);
  const [decision, setDecision] = useState("");
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");

  // Debounce search input · 250ms after last keystroke
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 250);
    return () => clearTimeout(t);
  }, [q]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["ledger", selectedTeam, days, decision, debouncedQ],
    queryFn: () => api.ledger({
      team: selectedTeam,
      days,
      decision: decision || undefined,
      q: debouncedQ || undefined,
      limit: 200,
    }),
    refetchInterval: 30_000,
  });

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="AI Decision Ledger"
        subtitle="Every AI finding · every human decision · every audit event · in one searchable timeline"
        actions={
          <span className="text-[11px] text-ink-500 inline-flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 text-brand-500" />
            Source of truth for post-mortems & audits
          </span>
        }
      />

      {/* Filter bar */}
      <Card className="mb-4">
        <div className="px-4 py-3 grid grid-cols-1 md:grid-cols-[1fr_180px_240px] gap-3 items-center">
          <div className="relative">
            <Search className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={q}
              onChange={e => setQ(e.target.value)}
              placeholder="Search rule, finding title, or dismissal note…"
              className="w-full h-10 pl-9 pr-3 text-sm rounded-lg bg-white border border-ink-200
                         placeholder:text-ink-400 focus:outline-none focus:border-brand-500
                         focus:shadow-glow transition-all"
            />
          </div>
          <select
            value={decision}
            onChange={e => setDecision(e.target.value)}
            className="h-10 px-3 text-sm rounded-lg bg-white border border-ink-200 font-semibold text-ink-700
                       focus:outline-none focus:border-brand-500 focus:shadow-glow transition-all"
          >
            {DECISIONS.map(d => <option key={d.id} value={d.id}>{d.label}</option>)}
          </select>
          <div className="inline-flex items-center bg-white border border-ink-200 rounded-lg p-0.5 shadow-soft">
            {WINDOWS.map(w => (
              <button
                key={w.id}
                onClick={() => setDays(w.id)}
                className={cn(
                  "flex-1 h-9 text-xs font-semibold rounded-md transition-all",
                  days === w.id
                    ? "bg-brand-grad text-white shadow-glow"
                    : "text-ink-600 hover:text-brand-600",
                )}
              >
                Last {w.label}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Timeline */}
      {error ? (
        <Card>
          <EmptyState icon={<Zap className="w-5 h-5" />} title="Couldn't load ledger" subtitle={(error as Error).message} />
        </Card>
      ) : (
        <Card>
          <CardHead
            title="Timeline"
            hint={data ? `${data.entries.length} of ${data.total} events · newest first` : ""}
          />
          {isLoading ? (
            <SkeletonRows />
          ) : !data || data.entries.length === 0 ? (
            <EmptyState
              icon={<History className="w-5 h-5" />}
              title={debouncedQ || decision ? "No events match these filters" : "No events in this window"}
              subtitle="Adjust the search, decision filter, or time window above."
            />
          ) : (
            <ul className="relative">
              {/* Vertical rail */}
              <div className="absolute left-[27px] top-2 bottom-2 w-px bg-gradient-to-b from-brand-200 via-ink-200 to-transparent" />
              {data.entries.map((e, i) => <TimelineRow key={e.id} entry={e} index={i} />)}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}

// ─── One timeline row ────────────────────────────────────────
function TimelineRow({ entry, index }: { entry: LedgerEntry; index: number }) {
  const cfg = kindConfig(entry);
  const Icon = cfg.Icon;
  return (
    <motion.li
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25, delay: Math.min(index * 0.025, 0.4) }}
      className="relative pl-14 pr-5 py-4 border-b border-ink-100 last:border-0 hover:bg-brand-50/30 transition-colors"
    >
      {/* Node */}
      <span className={cn(
        "absolute left-[14px] top-5 w-[28px] h-[28px] rounded-full inline-flex items-center justify-center text-white shadow-soft ring-4 ring-white",
        cfg.dot,
      )}>
        <Icon className="w-3.5 h-3.5" />
      </span>

      {/* Header */}
      <div className="flex items-start gap-3 flex-wrap">
        <span className={cn("pill text-[10.5px] uppercase tracking-wider font-bold", cfg.pill)}>
          {entry.kind}
        </span>
        {entry.severity && <SevPill sev={entry.severity} />}
        {entry.decision && <DecisionPill d={entry.decision} />}
        <span className="text-sm font-semibold text-ink-900 flex-1 min-w-0">{entry.title}</span>
        <span className="text-[11px] font-mono text-ink-500 shrink-0">{relativeTime(entry.timestamp)}</span>
      </div>

      {/* Body */}
      <div className="mt-2 text-[12.5px] text-ink-700 prose prose-sm max-w-none prose-p:my-1 prose-code:text-[11.5px]">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.detail}</ReactMarkdown>
      </div>

      {/* Footer */}
      <div className="mt-2 flex items-center gap-3 text-[11px] text-ink-500 flex-wrap">
        <span className="inline-flex items-center gap-1.5">
          <span className="w-1 h-1 rounded-full bg-ink-300" />
          actor <code className="font-mono font-semibold text-ink-700">{entry.actor}</code>
        </span>
        {entry.repo && entry.pr_number && (
          <Link
            to={`/triage/${entry.pr_id}`}
            className="inline-flex items-center gap-1 text-brand-600 hover:text-brand-700 font-semibold"
          >
            <ExternalLink className="w-3 h-3" />
            {entry.repo}#{entry.pr_number}
          </Link>
        )}
        {entry.team && entry.team !== "unassigned" && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-ink-100 text-[10.5px] font-semibold text-ink-600">
            {entry.team}
          </span>
        )}
      </div>
    </motion.li>
  );
}

function kindConfig(e: LedgerEntry) {
  if (e.kind === "decision") {
    if (e.decision === "accept")
      return { Icon: CheckCircle2, dot: "bg-emerald-500", pill: "bg-emerald-50 text-emerald-700 border-emerald-200" };
    if (e.decision === "dismiss")
      return { Icon: XCircle,      dot: "bg-ink-500",    pill: "bg-ink-100 text-ink-700 border-ink-200" };
    return     { Icon: MessageSquare, dot: "bg-blue-500", pill: "bg-blue-50 text-blue-700 border-blue-200" };
  }
  if (e.kind === "finding") {
    if (e.severity === "BLOCKER")
      return { Icon: AlertCircle, dot: "bg-rose-500", pill: "bg-rose-50 text-rose-700 border-rose-200" };
    return     { Icon: Sparkles,  dot: "bg-brand-500", pill: "bg-brand-50 text-brand-700 border-brand-200" };
  }
  return { Icon: Activity, dot: "bg-ink-400", pill: "bg-ink-100 text-ink-600 border-ink-200" };
}

function SevPill({ sev }: { sev: string }) {
  const cls = sev === "BLOCKER" ? "bg-rose-50 text-rose-700 border-rose-200" :
              sev === "MAJOR"   ? "bg-orange-50 text-orange-700 border-orange-200" :
              sev === "MINOR"   ? "bg-amber-50 text-amber-700 border-amber-200" :
                                  "bg-ink-100 text-ink-600 border-ink-200";
  return <span className={cn("pill font-mono text-[10px]", cls)}>{sev}</span>;
}

function DecisionPill({ d }: { d: string }) {
  const cls = d === "accept"  ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
              d === "dismiss" ? "bg-ink-100 text-ink-700 border-ink-200" :
                                "bg-blue-50 text-blue-700 border-blue-200";
  return <span className={cn("pill text-[10px] uppercase tracking-wider font-semibold", cls)}>{d}</span>;
}

function SkeletonRows() {
  return (
    <div className="divide-y divide-ink-100">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="pl-14 pr-5 py-4">
          <div className="flex gap-3 mb-2">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-2/3" />
          </div>
          <Skeleton className="h-3 w-full mb-1" />
          <Skeleton className="h-3 w-3/4" />
        </div>
      ))}
    </div>
  );
}
