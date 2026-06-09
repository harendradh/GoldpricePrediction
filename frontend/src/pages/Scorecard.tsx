import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  GaugeCircle, AlertTriangle, Activity, Zap, Clock, Users, ListChecks,
  TrendingDown, TrendingUp,
} from "lucide-react";
import { api } from "../lib/api";
import { Card, CardHead, EmptyState, PageHeader, Skeleton } from "../components/ui";
import { useAtlasStore } from "../store/useAtlasStore";
import { cn } from "../lib/utils";
import { useState } from "react";

const WINDOWS = [
  { id: 7,  label: "Last 7 days"  },
  { id: 30, label: "Last 30 days" },
  { id: 90, label: "Last 90 days" },
];

export default function Scorecard() {
  const selectedTeam = useAtlasStore(s => s.selectedTeam);
  const [days, setDays] = useState(30);

  const { data, isLoading, error } = useQuery({
    queryKey: ["scorecard", selectedTeam, days],
    queryFn: () => api.scorecard(selectedTeam, days),
    refetchInterval: 30_000,
  });

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Engineering Health Scorecard"
        subtitle={`AI-derived KPIs for ${data?.team_label ?? "your team"} · use the team switcher to scope`}
        actions={
          <div className="inline-flex items-center bg-white border border-ink-200 rounded-lg p-0.5 shadow-soft">
            {WINDOWS.map(w => (
              <button
                key={w.id}
                onClick={() => setDays(w.id)}
                className={cn(
                  "px-3 h-8 text-xs font-semibold rounded-md transition-all",
                  days === w.id
                    ? "bg-brand-grad text-white shadow-glow"
                    : "text-ink-600 hover:text-brand-600",
                )}
              >
                {w.label}
              </button>
            ))}
          </div>
        }
      />

      {error ? (
        <Card>
          <EmptyState
            icon={<Zap className="w-5 h-5" />}
            title="Couldn't load scorecard"
            subtitle={(error as Error).message}
          />
        </Card>
      ) : (
        <>
          {/* KPI grid · 4 leadership-grade signals */}
          <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4 mb-5">
            <Kpi
              loading={isLoading}
              label="PRs reviewed"
              value={data?.total_prs ?? 0}
              sub={`${data?.open_prs ?? 0} still open · ${data?.findings_per_pr ?? 0} findings/PR`}
              Icon={Activity}
              tint="brand"
            />
            <Kpi
              loading={isLoading}
              label="Blocker leakage"
              value={data ? `${(data.blocker_leakage_rate * 100).toFixed(1)}%` : "—"}
              sub={data?.blockers_caught ? `${data.blockers_caught} blockers caught` : "no blockers in window"}
              Icon={AlertTriangle}
              tint={data && data.blocker_leakage_rate > 0.05 ? "rose" : "emerald"}
              trendGood={!!(data && data.blocker_leakage_rate <= 0.05)}
            />
            <Kpi
              loading={isLoading}
              label="Median cycle time"
              value={data?.median_cycle_time_hours != null ? `${data.median_cycle_time_hours}h` : "—"}
              sub="from PR opened → reviewed"
              Icon={Clock}
              tint="blue"
            />
            <Kpi
              loading={isLoading}
              label="Triage queue depth"
              value={data?.queue_depth ?? 0}
              sub="findings awaiting decision"
              Icon={ListChecks}
              tint={data && data.queue_depth > 20 ? "amber" : "emerald"}
            />
          </div>

          {/* Lower row · Dimension mix · Reviewers · Sparkline */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-5">
            <Card className="lg:col-span-1">
              <CardHead title="Findings by dimension" hint="last window" />
              <div className="p-5">
                {isLoading ? (
                  <Skeleton className="h-40 w-full" />
                ) : !data || Object.keys(data.dimension_mix).length === 0 ? (
                  <EmptyState icon={<GaugeCircle className="w-5 h-5" />} title="No findings yet" />
                ) : (
                  <DimensionBars mix={data.dimension_mix} />
                )}
              </div>
            </Card>

            <Card className="lg:col-span-1">
              <CardHead title="Top reviewers" hint="by triage decisions" />
              <div className="p-5">
                {isLoading ? (
                  <Skeleton className="h-40 w-full" />
                ) : !data || data.top_reviewers.length === 0 ? (
                  <EmptyState icon={<Users className="w-5 h-5" />} title="No triage activity" />
                ) : (
                  <ReviewerList rows={data.top_reviewers} />
                )}
              </div>
            </Card>

            <Card className="lg:col-span-1">
              <CardHead title="Findings · daily" hint={`last ${Math.min(days, 14)} days`} />
              <div className="p-5">
                {isLoading ? (
                  <Skeleton className="h-40 w-full" />
                ) : !data || data.daily_findings.length === 0 ? (
                  <EmptyState icon={<TrendingUp className="w-5 h-5" />} title="No data" />
                ) : (
                  <Sparkline points={data.daily_findings} />
                )}
              </div>
            </Card>
          </div>

          {/* Secondary KPIs · operational health */}
          <Card>
            <CardHead title="Operational signals" hint="lower-priority but useful" />
            <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-ink-100">
              <Stat
                label="Auto-post rate"
                value={data ? `${(data.auto_post_rate * 100).toFixed(0)}%` : "—"}
                sub="findings auto-posted at ≥ threshold"
                loading={isLoading}
              />
              <Stat
                label="Dismissal rate"
                value={data ? `${(data.dismissal_rate * 100).toFixed(0)}%` : "—"}
                sub="of triaged findings · high = rule tuning needed"
                loading={isLoading}
              />
              <Stat
                label="Findings total"
                value={data?.findings_total ?? 0}
                sub={`window: ${days} day${days === 1 ? "" : "s"}`}
                loading={isLoading}
              />
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

// ─── KPI tile ────────────────────────────────────────────────
const tintMap = {
  brand:   { ring: "ring-brand-200/50",   from: "from-brand-50",   icon: "bg-brand-grad text-white",                             val: "text-brand-700" },
  blue:    { ring: "ring-blue-200/50",    from: "from-blue-50",    icon: "bg-gradient-to-br from-blue-500 to-blue-700 text-white", val: "text-blue-700" },
  emerald: { ring: "ring-emerald-200/50", from: "from-emerald-50", icon: "bg-gradient-to-br from-emerald-500 to-emerald-700 text-white", val: "text-emerald-700" },
  rose:    { ring: "ring-rose-200/50",    from: "from-rose-50",    icon: "bg-gradient-to-br from-rose-500 to-rose-700 text-white", val: "text-rose-700" },
  amber:   { ring: "ring-amber-200/50",   from: "from-amber-50",   icon: "bg-gradient-to-br from-amber-500 to-amber-700 text-white", val: "text-amber-700" },
};

function Kpi({ loading, label, value, sub, Icon, tint, trendGood }: {
  loading: boolean; label: string; value: number | string; sub: string;
  Icon: typeof Activity; tint: keyof typeof tintMap; trendGood?: boolean;
}) {
  const t = tintMap[tint];
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className={cn("card p-5 relative overflow-hidden ring-1", t.ring, `bg-gradient-to-br ${t.from} via-white to-white`)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="text-[11.5px] font-bold tracking-wider text-ink-500 uppercase">{label}</div>
        <div className={cn("w-9 h-9 rounded-lg inline-flex items-center justify-center shadow-soft", t.icon)}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      {loading ? (
        <Skeleton className="h-9 w-24" />
      ) : (
        <div className="flex items-baseline gap-2">
          <div className={cn("font-bold leading-none text-[28px] tracking-tight", t.val)}>{value}</div>
          {trendGood !== undefined && (
            trendGood
              ? <TrendingDown className="w-4 h-4 text-emerald-500" />
              : <TrendingUp   className="w-4 h-4 text-rose-500" />
          )}
        </div>
      )}
      <div className="text-[12px] text-ink-500 mt-1.5">{sub}</div>
    </motion.div>
  );
}

// ─── Dimension bars ──────────────────────────────────────────
const dimColor: Record<string, string> = {
  audit:  "bg-violet-500",
  perf:   "bg-blue-500",
  secure: "bg-rose-500",
  style:  "bg-amber-500",
  test:   "bg-emerald-500",
};

function DimensionBars({ mix }: { mix: Record<string, number> }) {
  const entries = Object.entries(mix).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, v]) => s + v, 0) || 1;
  return (
    <ul className="space-y-3">
      {entries.map(([dim, count], i) => {
        const pct = (count / total) * 100;
        const color = dimColor[dim] ?? "bg-ink-400";
        return (
          <li key={dim} className="grid grid-cols-[80px_1fr_50px] gap-3 items-center">
            <span className="text-[12px] font-semibold text-ink-700 uppercase tracking-wide">{dim}</span>
            <div className="h-2.5 rounded-full bg-ink-100 overflow-hidden">
              <motion.div
                initial={{ width: 0 }} animate={{ width: `${pct}%` }}
                transition={{ duration: 0.7, delay: i * 0.07 }}
                className={cn("h-full rounded-full", color)}
              />
            </div>
            <span className="font-mono text-sm font-bold text-ink-900 text-right tabular-nums">{count}</span>
          </li>
        );
      })}
    </ul>
  );
}

// ─── Reviewer list ───────────────────────────────────────────
function ReviewerList({ rows }: { rows: { user: string; decisions: number }[] }) {
  return (
    <ul className="space-y-2.5">
      {rows.map(r => (
        <li key={r.user} className="flex items-center gap-3 px-2 py-1.5 rounded-lg hover:bg-brand-50/40 transition-colors">
          <span className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-600 to-blue-800 text-white text-xs font-bold inline-flex items-center justify-center">
            {r.user.slice(0, 2).toUpperCase()}
          </span>
          <span className="flex-1 text-sm font-semibold text-ink-800 truncate">{r.user}</span>
          <span className="font-mono text-xs font-bold text-ink-600 bg-ink-100 border border-ink-200 rounded-full px-2 py-0.5">
            {r.decisions}
          </span>
        </li>
      ))}
    </ul>
  );
}

// ─── Sparkline ───────────────────────────────────────────────
function Sparkline({ points }: { points: { date: string; count: number }[] }) {
  const max = Math.max(1, ...points.map(p => p.count));
  return (
    <div>
      <div className="h-32 flex items-end gap-1.5">
        {points.map((p, i) => {
          const h = (p.count / max) * 100;
          return (
            <motion.div
              key={p.date}
              initial={{ height: 0 }}
              animate={{ height: `${Math.max(h, 4)}%` }}
              transition={{ duration: 0.5, delay: i * 0.04, ease: [0.2, 0.8, 0.4, 1] }}
              title={`${p.date} · ${p.count}`}
              className={cn(
                "flex-1 rounded-t-md",
                p.count === 0 ? "bg-ink-100" : "bg-brand-grad shadow-[inset_0_1px_0_rgba(255,255,255,.4)]",
              )}
            />
          );
        })}
      </div>
      <div className="flex justify-between mt-2 text-[10px] font-mono text-ink-400">
        <span>{points[0]?.date.slice(5)}</span>
        <span>{points[points.length - 1]?.date.slice(5)}</span>
      </div>
    </div>
  );
}

function Stat({ label, value, sub, loading }: { label: string; value: string | number; sub: string; loading: boolean }) {
  return (
    <div className="px-5 py-4">
      <div className="text-[10.5px] font-bold tracking-wider text-ink-500 uppercase mb-1.5">{label}</div>
      {loading
        ? <Skeleton className="h-7 w-20" />
        : <div className="text-2xl font-bold text-ink-900 tracking-tight">{value}</div>}
      <div className="text-[11.5px] text-ink-500 mt-1">{sub}</div>
    </div>
  );
}
