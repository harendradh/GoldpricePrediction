import { AnimatePresence, motion } from "framer-motion";
import { useAtlasStore } from "../store/useAtlasStore";
import { CheckCircle2, AlertTriangle, XCircle, Info } from "lucide-react";
import { cn } from "../lib/utils";

const variantMap = {
  default: { Icon: Info,         cls: "bg-ink-900 text-white border-ink-800" },
  success: { Icon: CheckCircle2, cls: "bg-emerald-600 text-white border-emerald-700" },
  warning: { Icon: AlertTriangle, cls: "bg-amber-500 text-white border-amber-600" },
  error:   { Icon: XCircle,      cls: "bg-rose-600 text-white border-rose-700" },
} as const;

export function Toaster() {
  const toasts = useAtlasStore(s => s.toasts);
  return (
    <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50 pointer-events-none flex flex-col items-center gap-2">
      <AnimatePresence>
        {toasts.map(t => {
          const { Icon, cls } = variantMap[t.variant];
          return (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 12, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.96 }}
              transition={{ duration: 0.22, ease: [0.2, 0.8, 0.4, 1] }}
              className={cn(
                "pointer-events-auto inline-flex items-center gap-2 px-4 py-2.5 rounded-lg shadow-lift border min-w-[260px]",
                cls,
              )}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="text-sm font-medium">{t.text}</span>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
