import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { ClipboardList, FileText, Copy, Check, X, Sparkles, Zap, Shield, AlertTriangle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../lib/api";
import { Card, CardHead, EmptyState, PageHeader, Skeleton, Button } from "../components/ui";
import { useAtlasStore } from "../store/useAtlasStore";
import { cn, relativeTime } from "../lib/utils";
import type { CABBrief, PRSummary } from "../lib/types";

export default function CABBriefs() {
  const selectedTeam = useAtlasStore(s => s.selectedTeam);
  const [openBrief, setOpenBrief] = useState<CABBrief | null>(null);

  // Show only merged + open PRs · those are CAB-eligible
  const { data: prs, isLoading, error } = useQuery({
    queryKey: ["prs", "all", selectedTeam, "cab"],
    queryFn: () => api.listPRs("all", selectedTeam, 50),
    refetchInterval: 60_000,
  });

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="CAB Briefs"
        subtitle="Auto-generated change-management memos · paste into ServiceNow / JIRA as Standard Change evidence"
      />

      {error ? (
        <Card>
          <EmptyState icon={<Zap className="w-5 h-5" />} title="Couldn't load PRs" subtitle={(error as Error).message} />
        </Card>
      ) : (
        <Card>
          <CardHead
            title="Eligible PRs"
            hint={prs ? `${prs.length} candidates for CAB brief generation` : ""}
            actions={
              <span className="text-[11px] text-ink-500 inline-flex items-center gap-1.5">
                <Sparkles className="w-3 h-3 text-brand-500" />
                Briefs are generated on demand
              </span>
            }
          />
          {isLoading ? (
            <SkeletonRows />
          ) : !prs || prs.length === 0 ? (
            <EmptyState
              icon={<ClipboardList className="w-5 h-5" />}
              title="No PRs in this scope"
              subtitle="Switch teams or wait for a PR to be reviewed."
            />
          ) : (
            <ul className="divide-y divide-ink-100">
              {prs.map(pr => (
                <BriefRow key={pr.id} pr={pr} onOpen={b => setOpenBrief(b)} />
              ))}
            </ul>
          )}
        </Card>
      )}

      <BriefViewer brief={openBrief} onClose={() => setOpenBrief(null)} />
    </div>
  );
}

// ─── Row ─────────────────────────────────────────────────────
function BriefRow({ pr, onOpen }: { pr: PRSummary; onOpen: (brief: CABBrief) => void }) {
  const gen = useMutation({
    mutationFn: () => api.cabBrief(pr.id),
    onSuccess: brief => onOpen(brief),
  });

  return (
    <li className="grid grid-cols-[60px_1fr_180px_140px_140px] items-center gap-4 px-5 py-3.5">
      <div className="font-mono text-xs font-semibold text-ink-500">#{pr.number}</div>
      <div className="min-w-0">
        <div className="text-sm font-semibold text-ink-900 truncate flex items-center gap-2">
          <FileText className="w-3.5 h-3.5 text-ink-400 shrink-0" />
          {pr.title}
        </div>
        <div className="text-[11.5px] text-ink-500 mt-0.5">{pr.author} · {pr.repo}</div>
      </div>
      <div className="flex items-center gap-2">
        <RiskHint pr={pr} />
      </div>
      <div className="text-[11.5px] text-ink-500 font-mono">{relativeTime(pr.updated_at)}</div>
      <div className="flex justify-end">
        <Button
          variant="primary"
          onClick={() => gen.mutate()}
          disabled={gen.isPending}
        >
          {gen.isPending ? (
            <>
              <motion.span
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                className="inline-block"
              >
                <Sparkles className="w-3.5 h-3.5" />
              </motion.span>
              Generating…
            </>
          ) : (
            <>
              <Sparkles className="w-3.5 h-3.5" />
              Generate brief
            </>
          )}
        </Button>
      </div>
    </li>
  );
}

// ─── Visual risk hint (computed inline from finding counts) ──
function RiskHint({ pr }: { pr: PRSummary }) {
  // Heuristic preview · server returns the authoritative risk on generate
  const f = pr.findings_count;
  const awaiting = pr.awaiting_count;
  let risk: "low" | "medium" | "high";
  if (awaiting > 5) risk = "high";
  else if (f > 5) risk = "medium";
  else risk = "low";

  const cfg = {
    low:    { cls: "bg-emerald-50 text-emerald-700 border-emerald-200", Icon: Shield,         label: "low risk"    },
    medium: { cls: "bg-amber-50 text-amber-700 border-amber-200",       Icon: AlertTriangle,  label: "medium risk" },
    high:   { cls: "bg-rose-50 text-rose-700 border-rose-200",          Icon: AlertTriangle,  label: "high risk"   },
  }[risk];
  const Icon = cfg.Icon;
  return (
    <span className={cn("pill text-[10.5px]", cfg.cls)}>
      <Icon className="w-3 h-3" />
      {cfg.label}
    </span>
  );
}

// ─── Brief viewer modal ─────────────────────────────────────
function BriefViewer({ brief, onClose }: { brief: CABBrief | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = async () => {
    if (!brief) return;
    await navigator.clipboard.writeText(brief.markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <AnimatePresence>
      {brief && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            className="fixed inset-0 bg-ink-900/50 backdrop-blur-sm z-40"
          />
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.2, ease: [0.2, 0.8, 0.4, 1] }}
            className="fixed inset-x-8 top-12 bottom-12 max-w-4xl mx-auto bg-white rounded-2xl shadow-2xl z-50 flex flex-col overflow-hidden"
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-ink-200 bg-gradient-to-r from-brand-50 to-white">
              <div className="flex items-center gap-3">
                <span className={cn(
                  "w-9 h-9 rounded-lg inline-flex items-center justify-center text-white shadow-soft",
                  brief.risk_level === "high"   ? "bg-gradient-to-br from-rose-500 to-rose-700" :
                  brief.risk_level === "medium" ? "bg-gradient-to-br from-amber-500 to-amber-700" :
                                                  "bg-gradient-to-br from-emerald-500 to-emerald-700",
                )}>
                  <ClipboardList className="w-4 h-4" />
                </span>
                <div>
                  <h3 className="text-base font-bold text-ink-900">Change Brief · PR #{brief.number}</h3>
                  <p className="text-[11.5px] text-ink-500 mt-0.5">{brief.repo} · risk: <span className="font-semibold uppercase">{brief.risk_level}</span></p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" onClick={copyToClipboard}>
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? "Copied" : "Copy markdown"}
                </Button>
                <button onClick={onClose}
                  className="w-9 h-9 rounded-md text-ink-500 hover:bg-ink-100 inline-flex items-center justify-center">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-8 py-6 prose prose-sm max-w-none prose-headings:text-ink-900 prose-h1:text-xl prose-h2:text-base prose-table:text-xs">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{brief.markdown}</ReactMarkdown>
            </div>
            <div className="px-6 py-3 border-t border-ink-200 bg-ink-50 text-[11px] text-ink-500 flex justify-between">
              <span>Generated {relativeTime(brief.generated_at)} · ChangePilot Studio</span>
              <span>Paste into ServiceNow as <strong>Standard Change · AI-assisted</strong></span>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function SkeletonRows() {
  return (
    <div className="divide-y divide-ink-100">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="grid grid-cols-[60px_1fr_180px_140px_140px] items-center gap-4 px-5 py-4">
          <Skeleton className="h-4 w-12" />
          <div className="space-y-1.5"><Skeleton className="h-4 w-3/4" /><Skeleton className="h-3 w-1/2" /></div>
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-9 w-32" />
        </div>
      ))}
    </div>
  );
}
