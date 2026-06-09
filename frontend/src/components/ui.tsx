import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { cn } from "../lib/utils";
import type { Severity } from "../lib/types";
import type { ReactNode } from "react";

// ─── Page header ──────────────────────────────────────────────
export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="flex items-end justify-between mb-5">
      <div>
        <h1 className="text-[26px] font-bold tracking-tight text-ink-900 leading-tight">{title}</h1>
        {subtitle && <p className="text-sm text-ink-500 mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

// ─── Card ─────────────────────────────────────────────────────
export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("card", className)}>{children}</div>;
}
export function CardHead({ title, hint, actions }: { title: ReactNode; hint?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex items-center justify-between px-5 py-3.5 border-b border-ink-200">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-bold text-ink-900">{title}</h3>
        {hint && <span className="text-xs text-ink-500 font-normal">{hint}</span>}
      </div>
      {actions}
    </div>
  );
}

// ─── Button ──────────────────────────────────────────────────
type BtnVariant = "primary" | "secondary" | "success" | "danger" | "ghost";
const btnClass: Record<BtnVariant, string> = {
  primary:   "bg-brand-grad text-white border-brand-600 hover:shadow-glow",
  secondary: "bg-white text-ink-700 border-ink-300 hover:border-ink-400 hover:bg-ink-50",
  success:   "bg-emerald-600 text-white border-emerald-700 hover:bg-emerald-700",
  danger:    "bg-white text-rose-700 border-rose-200 hover:bg-rose-50 hover:border-rose-400",
  ghost:     "text-ink-600 hover:bg-ink-100 border-transparent",
};
export function Button(
  { children, variant = "secondary", className, ...rest }:
  { children: ReactNode; variant?: BtnVariant } & React.ButtonHTMLAttributes<HTMLButtonElement>,
) {
  return (
    <button {...rest}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 h-9 px-3.5 rounded-lg text-sm font-semibold border transition-all",
        "disabled:opacity-50 disabled:cursor-not-allowed active:scale-[.98]",
        btnClass[variant], className,
      )}>{children}</button>
  );
}

// ─── Empty state ──────────────────────────────────────────────
export function EmptyState({ icon, title, subtitle, action }: {
  icon: ReactNode; title: string; subtitle?: string; action?: ReactNode;
}) {
  return (
    <div className="py-14 px-8 text-center">
      <div className="inline-flex w-12 h-12 rounded-full bg-brand-50 text-brand-500 items-center justify-center mb-3">
        {icon}
      </div>
      <div className="text-base font-semibold text-ink-900">{title}</div>
      {subtitle && <p className="text-sm text-ink-500 mt-1 max-w-md mx-auto">{subtitle}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// ─── Skeleton ─────────────────────────────────────────────────
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

// ─── Severity pill ────────────────────────────────────────────
const sevMap: Record<Severity, { cls: string; dot: string }> = {
  BLOCKER: { cls: "bg-rose-50 text-rose-700 border-rose-200",       dot: "bg-rose-500" },
  MAJOR:   { cls: "bg-orange-50 text-orange-700 border-orange-200", dot: "bg-orange-500" },
  MINOR:   { cls: "bg-amber-50 text-amber-700 border-amber-200",    dot: "bg-amber-500" },
  NIT:     { cls: "bg-ink-100 text-ink-600 border-ink-200",         dot: "bg-ink-400" },
};
export function SeverityPill({ severity }: { severity: Severity }) {
  const { cls, dot } = sevMap[severity];
  return (
    <span className={cn("pill font-mono text-[10.5px] tracking-wide", cls)}>
      <span className={cn("w-1.5 h-1.5 rounded-full", dot)} />
      {severity}
    </span>
  );
}

// ─── Verdict pill ────────────────────────────────────────────
const verdictMap = {
  merge:   "bg-emerald-50 text-emerald-700 border-emerald-200",
  improve: "bg-amber-50 text-amber-700 border-amber-200",
  block:   "bg-rose-50 text-rose-700 border-rose-200",
  running: "bg-blue-50 text-blue-700 border-blue-200",
};
export function VerdictPill({ verdict }: { verdict: string }) {
  const cls = (verdictMap as any)[verdict] ?? "bg-ink-100 text-ink-700 border-ink-200";
  return (
    <span className={cn("pill uppercase tracking-wider", cls)}>
      {verdict === "running" && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse-soft" />}
      {verdict}
    </span>
  );
}

// ─── Confidence bar ───────────────────────────────────────────
export function ConfidenceBar({ value }: { value: number }) {
  const color = value >= 80 ? "bg-emerald-500" : value >= 65 ? "bg-amber-500" : "bg-rose-500";
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-ink-500">
      <span>confidence</span>
      <span className="inline-block w-12 h-1.5 rounded-full bg-ink-100 overflow-hidden">
        <motion.span
          initial={{ width: 0 }} animate={{ width: `${value}%` }}
          transition={{ duration: 0.6, ease: [0.2, 0.8, 0.4, 1] }}
          className={cn("h-full rounded-full block", color)}
        />
      </span>
      <span className="font-mono">{value}</span>
    </span>
  );
}

// ─── Drawer ───────────────────────────────────────────────────
// The outer wrapper div owns the fixed position + dimensions.
// Drawer — NO Framer Motion on the panel itself.
// Plain CSS transition: transform avoids will-change:transform which corrupts
// height:100% calculations on Windows Chromium compositing layers.
export function Drawer({ open, onClose, title, children, footer }: {
  open: boolean; onClose: () => void; title: string;
  children: ReactNode; footer?: ReactNode;
}) {
  return (
    <>
      {/* Backdrop */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
            className="fixed inset-0 bg-ink-900/40 backdrop-blur-sm z-40"
          />
        )}
      </AnimatePresence>

      {/* Panel — no height prop, top+bottom pins it to viewport edges.
          No Framer Motion = no will-change:transform = bottom:0 works correctly. */}
      <div
        className="fixed top-0 bottom-0 right-0 w-[520px] max-w-full bg-white shadow-2xl z-50
                   flex flex-col overflow-hidden"
        style={{
          transform: open ? "translateX(0)" : "translateX(100%)",
          transition: "transform 0.28s cubic-bezier(0.32,0.72,0,1)",
          pointerEvents: open ? "auto" : "none",
        }}
      >
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between px-5 py-4 border-b border-ink-200">
          <h3 className="text-base font-bold text-ink-900">{title}</h3>
          <button onClick={onClose} className="w-8 h-8 rounded-md text-ink-500 hover:bg-ink-100 inline-flex items-center justify-center transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        {/* Content scrolls, footer stays pinned */}
        <div className="flex-1 min-h-0 overflow-y-auto px-5 py-5">{children}</div>
        {/* Footer — shrink-0 keeps it always visible at the bottom */}
        {footer && (
          <div className="shrink-0 px-5 py-3.5 border-t border-ink-200 flex items-center justify-end gap-2 bg-ink-50">
            {footer}
          </div>
        )}
      </div>
    </>
  );
}

// ─── Form field ──────────────────────────────────────────────
export function Field({ label, hint, children, required }: { label: string; hint?: string; children: ReactNode; required?: boolean }) {
  return (
    <label className="block mb-4">
      <span className="text-xs font-semibold text-ink-700 inline-flex items-center gap-1">
        {label}{required && <span className="text-rose-500">*</span>}
      </span>
      <div className="mt-1.5">{children}</div>
      {hint && <span className="text-[11.5px] text-ink-500 mt-1 block">{hint}</span>}
    </label>
  );
}
export const inputCls = "w-full h-10 px-3 text-sm rounded-lg bg-white border border-ink-300 placeholder:text-ink-400 focus:outline-none focus:border-brand-500 focus:shadow-glow transition-all";
export const textareaCls = "w-full min-h-[110px] px-3 py-2.5 text-[12.5px] font-mono leading-relaxed rounded-lg bg-white border border-ink-300 placeholder:text-ink-400 focus:outline-none focus:border-brand-500 focus:shadow-glow transition-all";
