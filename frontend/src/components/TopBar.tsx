import { Plus, Search, Sparkles, Users, ChevronDown, Check } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAtlasStore } from "../store/useAtlasStore";
import { api } from "../lib/api";
import type { Team } from "../lib/types";
import { cn } from "../lib/utils";

export function TopBar() {
  const setQuickReviewOpen = useAtlasStore(s => s.setQuickReviewOpen);
  const backendUp = useAtlasStore(s => s.backendUp);
  const chatOpen = useAtlasStore(s => s.chatOpen);
  const setChatOpen = useAtlasStore(s => s.setChatOpen);

  return (
    <header className="relative h-16 flex items-center gap-5 px-6 bg-white border-b border-ink-200 shadow-soft z-30">
      {/* Brand · stacked: name + tagline */}
      <div className="flex items-center gap-3 select-none">
        <span className="text-[20px] font-extrabold leading-none text-brand-500 tracking-tight inline-flex items-baseline">
          fiserv<span className="ml-0.5 w-1.5 h-1.5 rounded-full bg-brand-500 inline-block" />
        </span>
        <span className="w-px h-7 bg-ink-200" />
        <div className="flex flex-col leading-tight">
          <div className="flex items-center gap-2">
            <span className="text-[15px] font-extrabold text-ink-900 tracking-tight">
              ChangePilot <span className="text-brand-500">Studio</span>
            </span>
            <span className="text-[10px] font-semibold text-ink-500 bg-ink-100 border border-ink-200 rounded-full px-1.5 py-0.5 leading-none">
              v0.2
            </span>
          </div>
          <Tagline />
        </div>
      </div>

      {/* Team switcher */}
      <TeamSwitcher />

      {/* Search */}
      <div className="relative flex-1 max-w-md ml-2">
        <Search className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          type="text"
          placeholder="Search PRs by number or title…"
          className="w-full h-9 pl-9 pr-3 text-sm rounded-lg bg-ink-50 border border-ink-200
                     placeholder:text-ink-400 focus:outline-none focus:border-brand-500
                     focus:bg-white focus:shadow-glow transition-all"
        />
      </div>

      <div className="ml-auto flex items-center gap-2">
        <StatusPill up={backendUp} />
        <button
          onClick={() => setQuickReviewOpen(true)}
          className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-lg text-sm font-semibold text-ink-700
                     bg-white border border-ink-200 hover:border-brand-500 hover:text-brand-600
                     hover:shadow-glow transition-all"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Quick review</span>
        </button>
        {/* AI Chat toggle — always in TopBar, zero z-index issues */}
        <button
          onClick={() => setChatOpen(!chatOpen)}
          className={cn(
            "relative inline-flex items-center gap-1.5 h-9 pl-2.5 pr-3 rounded-lg text-[13px] font-semibold border transition-all",
            chatOpen
              ? "bg-[linear-gradient(135deg,#7c3aed,#FF6200)] border-transparent text-white shadow-[0_0_0_2px_rgba(124,58,237,.25),0_4px_14px_rgba(255,98,0,.3)]"
              : "bg-white border-ink-200 text-ink-700 hover:border-violet-400 hover:text-violet-600 hover:shadow-[0_0_0_2px_rgba(124,58,237,.12)]",
          )}
          title={chatOpen ? "Close AI Assistant" : "Open AI Assistant"}
        >
          {/* icon */}
          <span className={cn(
            "w-5 h-5 rounded-md inline-flex items-center justify-center shrink-0 transition-all",
            chatOpen
              ? "bg-white/20 text-white"
              : "bg-violet-50 border border-violet-200 text-violet-600",
          )}>
            <Sparkles className="w-3 h-3" />
          </span>
          <span>AI Chat</span>
          {/* live dot when closed */}
          {!chatOpen && (
            <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-amber-400 ring-1.5 ring-white animate-pulse" />
          )}
        </button>
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-700 to-blue-900 text-white text-xs font-bold inline-flex items-center justify-center shadow-soft">
          HS
        </div>
      </div>
    </header>
  );
}

// ─── Team Switcher ────────────────────────────────────────────
// Compact dropdown that scopes Inbox / Triage / Insights to a Fiserv team.
function TeamSwitcher() {
  const selectedTeam = useAtlasStore(s => s.selectedTeam);
  const setSelectedTeam = useAtlasStore(s => s.setSelectedTeam);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const { data: teams = FALLBACK_TEAMS } = useQuery({
    queryKey: ["teams"],
    queryFn: api.listTeams,
    staleTime: 5 * 60_000,
  });

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", onDown);
    return () => window.removeEventListener("mousedown", onDown);
  }, [open]);

  const current = teams.find(t => t.id === selectedTeam) ?? teams[0];
  const isAll = current?.id === "all";

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className={cn(
          "inline-flex items-center gap-2 h-9 pl-2.5 pr-2 rounded-lg text-sm font-semibold border transition-all",
          isAll
            ? "bg-ink-50 text-ink-700 border-ink-200 hover:border-brand-400 hover:text-brand-600"
            : "bg-brand-50 text-brand-700 border-brand-200 hover:border-brand-500 hover:shadow-glow",
        )}
        aria-haspopup="menu"
        aria-expanded={open}
        title="Switch team scope"
      >
        <span className={cn(
          "w-6 h-6 rounded-md inline-flex items-center justify-center",
          isAll ? "bg-white border border-ink-200 text-ink-500" : "bg-brand-grad text-white shadow-soft",
        )}>
          <Users className="w-3.5 h-3.5" />
        </span>
        <span className="max-w-[180px] truncate">{current?.label ?? "All teams"}</span>
        <ChevronDown className={cn("w-3.5 h-3.5 text-ink-400 transition-transform", open && "rotate-180")} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.97 }}
            transition={{ duration: 0.14, ease: [0.2, 0.8, 0.4, 1] }}
            className="absolute top-full left-0 mt-1.5 w-72 rounded-xl bg-white border border-ink-200 shadow-lift overflow-hidden z-50"
            role="menu"
          >
            <div className="px-3 py-2 bg-gradient-to-r from-brand-50 to-transparent border-b border-ink-100">
              <div className="text-[10.5px] font-bold uppercase tracking-wider text-brand-700">Workspace scope</div>
              <div className="text-[11px] text-ink-500 mt-0.5">Filters Inbox · Triage · Insights</div>
            </div>
            <ul className="py-1 max-h-80 overflow-y-auto">
              {teams.map(t => (
                <li key={t.id}>
                  <button
                    onClick={() => { setSelectedTeam(t.id); setOpen(false); }}
                    className={cn(
                      "w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left transition-colors",
                      t.id === selectedTeam
                        ? "bg-brand-50/70 text-brand-700 font-semibold"
                        : "text-ink-700 hover:bg-ink-50",
                    )}
                  >
                    <TeamDot id={t.id} />
                    <span className="flex-1 truncate">{t.label}</span>
                    {t.id === selectedTeam && <Check className="w-3.5 h-3.5 text-brand-500" />}
                  </button>
                </li>
              ))}
            </ul>
            <div className="px-3 py-2 border-t border-ink-100 bg-ink-50/60">
              <button
                onClick={() => setOpen(false)}
                className="w-full inline-flex items-center justify-center gap-1.5 text-[11.5px] font-semibold text-ink-500 hover:text-brand-600"
              >
                <Plus className="w-3 h-3" />
                Manage teams in Settings
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function TeamDot({ id }: { id: string }) {
  // Color-coded team chips for at-a-glance scope identification
  // Stable hash-based color so any team ID gets a consistent dot color
  const palette = ["bg-blue-500", "bg-emerald-500", "bg-violet-500", "bg-amber-500", "bg-rose-500", "bg-cyan-500", "bg-fuchsia-500"];
  if (id === "all") return <span className={cn("w-2 h-2 rounded-full bg-ink-300")} />;
  const hash = id.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  return <span className={cn("w-2 h-2 rounded-full", palette[hash % palette.length])} />;
}

// Minimal bootstrap entry · real teams come from /api/v1/teams.
const FALLBACK_TEAMS: Team[] = [{ id: "all", label: "All teams" }];

// ─── Tagline · fixed product tagline with gradient shimmer ─────
function Tagline() {
  return (
    <div className="relative mt-0.5 min-w-[400px]">
      <span className="text-[10.5px] font-semibold tracking-wide
                       bg-clip-text text-transparent
                       bg-[linear-gradient(90deg,#FF6200_0%,#ff8c1e_30%,#0f172a_50%,#ff8c1e_70%,#FF6200_100%)]
                       bg-[length:200%_100%] animate-shimmer
                       whitespace-nowrap">
        The Intelligent Platform for Reviews, Governance &amp; Releases
      </span>
    </div>
  );
}

function StatusPill({ up }: { up: boolean }) {
  return (
    <motion.div
      layout
      className={cn(
        "pill",
        up
          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
          : "bg-rose-50 text-rose-700 border-rose-200",
      )}
    >
      <span className={cn(
        "w-1.5 h-1.5 rounded-full",
        up ? "bg-emerald-500 animate-pulse-soft" : "bg-rose-500",
      )} />
      {up ? "Live" : "Backend down"}
    </motion.div>
  );
}
