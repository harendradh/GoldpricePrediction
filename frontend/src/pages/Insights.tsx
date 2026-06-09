import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { TrendingUp, Zap, AlertTriangle, Activity } from "lucide-react";
import { api } from "../lib/api";
import { Card, CardHead, EmptyState, PageHeader, Skeleton } from "../components/ui";
import { cn } from "../lib/utils";

export default function Insights() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["insights"], queryFn: api.insights, refetchInterval: 30_000,
  });

  return (
    <div className="animate-fade-in">
      <PageHeader title="Insights" subtitle="Live KPIs and rule activity from the backend" />

      {error ? (
        <Card>
          <EmptyState icon={<Zap className="w-5 h-5" />} title="Couldn't reach the backend" subtitle={(error as Error).message} />
        </Card>
      ) : (
        <>
          {/* KPI grid */}
          <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4 mb-5">
            <Kpi loading={isLoading} label="PRs reviewed" value={data?.total_prs ?? 0} sub={`${data?.open_prs ?? 0} open`} Icon={Activity} tint="brand" />
            <Kpi loading={isLoading} label="Findings total" value={data?.findings_total ?? 0} sub="across all reviews" Icon={TrendingUp} tint="blue" />
            <Kpi loading={isLoading} label="Auto-post rate" value={`${data?.auto_post_rate ?? 0}%`} sub={`${data?.auto_posted ?? 0} posted automatically`} Icon={Zap} tint="emerald" />
            <Kpi loading={isLoading} label="Blockers caught" value={data?.blockers_caught ?? 0} sub="before merge" Icon={AlertTriangle} tint="rose" />
          </div>

          {/* Top rules */}
          <Card>
            <CardHead title="Top rules firing" hint="By number of findings · all time" />
            <div className="p-5">
              {isLoading ? (
                <BarsSkeleton />
              ) : !data || data.top_rules.length === 0 ? (
                <EmptyState icon={<TrendingUp className="w-5 h-5" />} title="No data yet" subtitle="As ChangePilot reviews PRs, the top-firing rules will appear here." />
              ) : (
                <BarChart rules={data.top_rules} />
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

const tintMap = {
  brand:   { ring: "ring-brand-200/50",   from: "from-brand-50",   icon: "bg-brand-grad text-white",          val: "text-brand-700" },
  blue:    { ring: "ring-blue-200/50",    from: "from-blue-50",    icon: "bg-gradient-to-br from-blue-500 to-blue-700 text-white", val: "text-blue-700" },
  emerald: { ring: "ring-emerald-200/50", from: "from-emerald-50", icon: "bg-gradient-to-br from-emerald-500 to-emerald-700 text-white", val: "text-emerald-700" },
  rose:    { ring: "ring-rose-200/50",    from: "from-rose-50",    icon: "bg-gradient-to-br from-rose-500 to-rose-700 text-white", val: "text-rose-700" },
};

function Kpi({ loading, label, value, sub, Icon, tint }: {
  loading: boolean; label: string; value: number | string; sub: string;
  Icon: typeof TrendingUp; tint: keyof typeof tintMap;
}) {
  const t = tintMap[tint];
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.2, 0.8, 0.4, 1] }}
      className={cn("card card-glow p-5 relative overflow-hidden ring-1", t.ring, `bg-gradient-to-br ${t.from} via-white to-white`)}
    >
      <div className={cn("absolute -right-4 -top-4 w-24 h-24 rounded-full blur-2xl opacity-20", t.icon.split(" ")[0])} />
      <div className="flex items-start justify-between mb-3 relative">
        <div className="text-[11.5px] font-bold tracking-wider text-ink-500 uppercase">{label}</div>
        <div className={cn("w-9 h-9 rounded-lg inline-flex items-center justify-center shadow-soft", t.icon)}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      {loading ? (
        <Skeleton className="h-9 w-24" />
      ) : (
        <div className={cn("font-bold leading-none text-[28px] tracking-tight", t.val)}>{value}</div>
      )}
      <div className="text-[12px] text-ink-500 mt-1.5">{sub}</div>
    </motion.div>
  );
}

function BarChart({ rules }: { rules: { rule_id: string; count: number }[] }) {
  const max = Math.max(1, ...rules.map(r => r.count));
  return (
    <ul className="space-y-3">
      {rules.map((r, i) => {
        const pct = (r.count / max) * 100;
        return (
          <li key={r.rule_id} className="grid grid-cols-[1fr_56px] gap-4 items-center">
            <div>
              <code className="text-[12.5px] font-mono font-semibold text-ink-700">{r.rule_id}</code>
              <div className="mt-1.5 h-2 rounded-full bg-ink-100 overflow-hidden">
                <motion.div
                  initial={{ width: 0 }} animate={{ width: `${pct}%` }}
                  transition={{ duration: 0.8, delay: i * 0.06, ease: [0.2, 0.8, 0.4, 1] }}
                  className="h-full rounded-full bg-brand-grad shadow-[inset_0_1px_0_rgba(255,255,255,.35)]"
                />
              </div>
            </div>
            <div className="font-mono text-sm font-bold text-ink-900 text-right tabular-nums">{r.count}</div>
          </li>
        );
      })}
    </ul>
  );
}

function BarsSkeleton() {
  return (
    <ul className="space-y-3">
      {[...Array(5)].map((_, i) => (
        <li key={i} className="grid grid-cols-[1fr_56px] gap-4 items-center">
          <div className="space-y-2"><Skeleton className="h-4 w-44" /><Skeleton className="h-2 w-full" /></div>
          <Skeleton className="h-4 w-10 justify-self-end" />
        </li>
      ))}
    </ul>
  );
}
