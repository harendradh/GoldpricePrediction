import { useState } from "react";
import { useAtlasStore } from "../store/useAtlasStore";
import { api } from "../lib/api";
import { copyToClipboard, cn } from "../lib/utils";
import { Button, Drawer, Field, inputCls, textareaCls } from "./ui";
import { Copy, Check } from "lucide-react";

// ── Language option definitions ───────────────────────────────
type LangOption = { id: string; label: string; badge: string; color: string };

const LANG_OPTIONS: LangOption[] = [
  { id: "python",         label: "Python",         badge: "PY",  color: "bg-blue-500" },
  { id: "pyspark",        label: "PySpark",         badge: "PS",  color: "bg-amber-500" },
  { id: "spark",          label: "Spark",           badge: "SP",  color: "bg-orange-500" },
  { id: "java",           label: "Java Spring App", badge: "JS",  color: "bg-red-500" },
  { id: "sql",            label: "SQL",             badge: "SQL", color: "bg-emerald-500" },
  { id: "other",          label: "Other",           badge: "···", color: "bg-ink-400" },
];

const DEFAULT_LANGS = new Set(["python", "pyspark"]);

export function QuickReviewDrawer() {
  const { quickReviewOpen, setQuickReviewOpen, pushToast } = useAtlasStore();
  const [reviewId, setReviewId] = useState("");
  const [title, setTitle] = useState("");
  const [files, setFiles] = useState("");
  const [selectedLangs, setSelectedLangs] = useState<Set<string>>(new Set(DEFAULT_LANGS));
  const [ctx, setCtx] = useState("");
  const [invocation, setInvocation] = useState<string>("");

  const toggleLang = (id: string) => {
    setSelectedLangs(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const generate = async () => {
    if (!reviewId.trim()) { pushToast("Enter a review ID", "warning"); return; }
    if (selectedLangs.size === 0) { pushToast("Select at least one language", "warning"); return; }
    try {
      const r = await api.quickReview({
        review_id: reviewId.trim(),
        title: title || reviewId,
        files: files.split("\n").map(s => s.trim()).filter(Boolean),
        languages: Array.from(selectedLangs),
        context: ctx,
        priorities: {},
      });
      setInvocation(r.invocation);
      pushToast("Spec written: " + r.spec_path.split(/[\\/]/).pop(), "success");
    } catch (e: any) {
      pushToast("Failed: " + e.message, "error");
    }
  };

  const close = () => { setQuickReviewOpen(false); setInvocation(""); };

  return (
    <Drawer
      open={quickReviewOpen}
      onClose={close}
      title="Quick review · Copilot Chat path"
      footer={<>
        <Button variant="secondary" onClick={close}>Cancel</Button>
        <Button variant="primary" onClick={generate}>
          Generate &amp; Review
        </Button>
      </>}
    >
      <p className="text-sm text-ink-600 mb-4">
        For pre-commit local checks. ChangePilot writes the spec.md to your project and gives you a one-line
        invocation. You paste in Copilot Chat in VS Code — the agent runs locally. For real PRs, ChangePilot runs
        automatically via webhook — see Inbox.
      </p>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Review ID" required>
          <input className={inputCls} value={reviewId} onChange={e => setReviewId(e.target.value)} placeholder="PR-4521 or hotfix-x" />
        </Field>
        <Field label="PR title (optional)">
          <input className={inputCls} value={title} onChange={e => setTitle(e.target.value)} placeholder="Customer enrichment…" />
        </Field>
      </div>

      <Field label="Files · one per line" required>
        <textarea className={textareaCls} value={files} onChange={e => setFiles(e.target.value)} placeholder={"apps/etl/jobs/customer_enrichment.py\napps/etl/lib/Enrichment.scala"} />
      </Field>

      {/* ── Language picker · intentionally NOT wrapped in <Field>/<label>
            because <button> inside <label> causes the label click to
            activate the first chip unexpectedly. ── */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs font-semibold text-ink-700">Languages</span>
          <span className="text-[11px] text-ink-500">
            {selectedLangs.size === 0
              ? "Select at least one"
              : `${selectedLangs.size} selected`}
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {LANG_OPTIONS.map(opt => {
            const active = selectedLangs.has(opt.id);
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => toggleLang(opt.id)}
                className={cn(
                  "inline-flex items-center gap-1.5 h-8 px-3 rounded-lg border text-sm font-semibold transition-all select-none",
                  active
                    ? "bg-brand-50 border-brand-400 text-brand-700 shadow-glow"
                    : "bg-white border-ink-200 text-ink-600 hover:border-brand-300 hover:text-brand-600",
                )}
              >
                <span className={cn("w-2 h-2 rounded-full flex-shrink-0", opt.color)} />
                {opt.label}
                {active && <Check className="w-3 h-3 text-brand-500 ml-0.5" />}
              </button>
            );
          })}
        </div>
        {selectedLangs.size > 0 && (
          <p className="mt-1.5 text-[11px] text-ink-500">
            Active:&nbsp;
            <span className="font-medium text-brand-600">
              {LANG_OPTIONS.filter(o => selectedLangs.has(o.id)).map(o => o.label).join(", ")}
            </span>
          </p>
        )}
      </div>

      <Field label="Business context">
        <textarea className={textareaCls} value={ctx} onChange={e => setCtx(e.target.value)} placeholder="Hot path · 240M rows · runs every 4h" />
      </Field>

      {invocation && (
        <Field label="Copilot invocation" hint="Click to copy">
          <pre
            onClick={async () => { await copyToClipboard(invocation); pushToast("Invocation copied", "success"); }}
            className="code-chunk whitespace-pre-wrap break-words"
          >{invocation}</pre>
          <button
            onClick={async () => { await copyToClipboard(invocation); pushToast("Invocation copied", "success"); }}
            className="mt-2 inline-flex items-center gap-1.5 text-xs text-brand-600 font-semibold hover:text-brand-700"
          ><Copy className="w-3.5 h-3.5" /> Copy invocation</button>
        </Field>
      )}
    </Drawer>
  );
}
