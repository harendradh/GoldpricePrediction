import { NavLink, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Inbox as InboxIcon, Target, BarChart3, Settings as SettingsIcon,
  BookOpen, FileText, Sparkles, GaugeCircle, ClipboardList, History,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { cn } from "../lib/utils";
import { useAtlasStore } from "../store/useAtlasStore";

interface NavItemDef {
  to: string; label: string; Icon: typeof InboxIcon;
  badge?: () => string;
}

export function Sidebar() {
  const loc = useLocation();
  const selectedTeam = useAtlasStore(s => s.selectedTeam);
  const { data: prs } = useQuery({ queryKey: ["prs", "open", selectedTeam], queryFn: () => api.listPRs("open", selectedTeam, 100), refetchInterval: 10_000, retry: 5, retryDelay: 2_000 });

  const sections: { title: string; items: NavItemDef[] }[] = [
    {
      title: "Review",
      items: [
        { to: "/inbox",  label: "Inbox",  Icon: InboxIcon, badge: () => String(prs?.filter(p => p.status === "open").length ?? 0) },
        { to: "/triage", label: "Triage", Icon: Target,    badge: () => String(prs?.filter(p => p.awaiting_count > 0).length ?? 0) },
      ],
    },
    {
      title: "Intelligence",
      items: [
        { to: "/insights",  label: "Insights",  Icon: BarChart3 },
        { to: "/scorecard", label: "Scorecard", Icon: GaugeCircle },
      ],
    },
    {
      title: "Governance",
      items: [
        { to: "/change-briefs", label: "CAB Briefs", Icon: ClipboardList },
        { to: "/ledger",        label: "Ledger",     Icon: History },
      ],
    },
    { title: "Admin", items: [{ to: "/settings", label: "Settings", Icon: SettingsIcon }] },
  ];

  return (
    <aside className="w-60 shrink-0 bg-warm-grad border-r border-brand-200 flex flex-col overflow-y-auto relative">
      {/* Glowing accent top bar */}
      <div className="h-0.5 bg-gradient-to-r from-brand-500 via-orange-400 to-brand-600 shadow-[0_2px_10px_rgba(255,98,0,.3)]" />

      {/* Workspace chip */}
      <div className="m-3 p-3 rounded-xl bg-gradient-to-br from-white to-brand-50 border border-brand-200 shadow-soft hover:shadow-lift transition-shadow flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-brand-grad text-white font-extrabold text-sm inline-flex items-center justify-center shadow-glow">
          DCS
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-[9.5px] font-bold tracking-wider text-brand-700 uppercase">Workspace</span>
            <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse-soft shadow-[0_0_0_2px_rgba(255,98,0,.2)]" />
          </div>
          <div className="text-sm font-bold text-ink-900 truncate">DCS Platform</div>
        </div>
      </div>

      <nav className="px-2 pb-2 flex-1">
        {sections.map((sec, idx) => (
          <div key={sec.title} className={idx > 0 ? "mt-3" : ""}>
            <div className="flex items-center gap-2 px-3 py-2 text-[10.5px] font-extrabold tracking-[0.13em] text-brand-700 uppercase">
              <span className="w-0.5 h-3 rounded-full bg-gradient-to-b from-brand-500 to-brand-600 shadow-[0_0_6px_rgba(255,98,0,.5)]" />
              {sec.title}
            </div>
            {sec.items.map(item => <NavItem key={item.to} {...item} active={loc.pathname.startsWith(item.to)} />)}
          </div>
        ))}
      </nav>

      {/* Footer resources card */}
      <div className="m-3 p-3 rounded-xl bg-gradient-to-br from-brand-50 to-white border border-brand-200 shadow-soft text-xs">
        <div className="text-[10px] font-bold tracking-wider text-brand-700 uppercase mb-1.5">Resources</div>
        <Link href="../docs/ARCHITECTURE.md" Icon={BookOpen}>Architecture</Link>
        <Link href="../docs/QUICK_REVIEW.md" Icon={Sparkles}>Quick Review guide</Link>
        <Link href="/api/v1/docs" Icon={FileText}>API · Swagger</Link>
      </div>

      {/* Bottom radial warm wash */}
      <div className="pointer-events-none absolute left-0 right-0 bottom-0 h-32 bg-[radial-gradient(ellipse_200px_120px_at_50%_100%,rgba(255,98,0,.10),transparent_70%)]" />
    </aside>
  );
}

function NavItem({ to, label, Icon, badge, active }: NavItemDef & { active: boolean }) {
  const count = badge?.();
  return (
    <NavLink to={to} end={false} className="relative block">
      {active && (
        <motion.div
          layoutId="atlas-nav-glow"
          className="absolute inset-x-2 inset-y-0 rounded-lg bg-brand-grad shadow-glow"
          transition={{ type: "spring", stiffness: 350, damping: 30 }}
        />
      )}
      <div className={cn(
        "relative flex items-center gap-3 mx-2 my-1 px-3.5 py-2.5 rounded-lg cursor-pointer transition-all",
        active ? "text-white" : "text-ink-700 hover:bg-white hover:shadow-soft hover:translate-x-0.5",
      )}>
        <span className={cn(
          "inline-flex items-center justify-center w-7 h-7 rounded-md border transition-all",
          active
            ? "bg-white/20 border-white/30 text-white"
            : "bg-white border-brand-200 text-brand-500 group-hover:bg-brand-50",
        )}>
          <Icon className="w-3.5 h-3.5" strokeWidth={2.4} />
        </span>
        <span className="text-[13px] font-semibold flex-1">{label}</span>
        {count !== undefined && (
          <span className={cn(
            "min-w-[22px] h-[18px] inline-flex items-center justify-center px-1.5 rounded-full text-[10.5px] font-bold font-mono",
            active
              ? "bg-white/25 text-white border border-white/30"
              : "bg-ink-100 text-ink-600 border border-ink-200",
          )}>{count}</span>
        )}
      </div>
    </NavLink>
  );
}

function Link({ href, Icon, children }: { href: string; Icon: typeof InboxIcon; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="flex items-center gap-2 py-1 text-ink-700 hover:text-brand-600 transition-colors">
      <Icon className="w-3 h-3" />
      <span className="font-medium">{children}</span>
    </a>
  );
}
