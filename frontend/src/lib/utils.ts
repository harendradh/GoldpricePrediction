import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Tailwind-aware class merger · cn("p-2", isActive && "bg-brand-500") */
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }

export function relativeTime(iso?: string | null): string {
  if (!iso) return "never";
  const dt = (Date.now() - new Date(iso).getTime()) / 1000;
  if (dt < 60) return "just now";
  if (dt < 3600) return Math.floor(dt / 60) + " min ago";
  if (dt < 86400) return Math.floor(dt / 3600) + "h ago";
  return Math.floor(dt / 86400) + "d ago";
}

export function initials(name: string): string {
  return name.split(/[.\s_/-]/).filter(Boolean).map(p => p[0]).join("").toUpperCase().slice(0, 2);
}

/** Stable avatar color from a string (always picks the same shade for the same input). */
export function avatarColor(seed: string): string {
  const palette = ["#0369a1", "#6d28d9", "#047857", "#b45309", "#b91c1c", "#0e7490", "#7c2d12", "#581c87"];
  let h = 0;
  for (const c of seed) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return palette[h % palette.length];
}

export async function copyToClipboard(text: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(text); return true; }
  catch {
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); document.body.removeChild(ta); return true; }
    catch { document.body.removeChild(ta); return false; }
  }
}
