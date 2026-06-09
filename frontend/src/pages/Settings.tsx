import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Plus, Trash2, Power, GitBranch, Sparkles, ShieldCheck, MessageSquare } from "lucide-react";
import { motion } from "framer-motion";
import { api } from "../lib/api";
import { useAtlasStore } from "../store/useAtlasStore";
import { Button, Card, CardHead, EmptyState, PageHeader, Skeleton } from "../components/ui";
import { cn, copyToClipboard, relativeTime } from "../lib/utils";
import type { Repo } from "../lib/types";

export default function Settings() {
  return (
    <div className="animate-fade-in">
      <PageHeader title="Settings" subtitle="Onboard repositories · view webhook configuration" />
      <WebhookCard />
      <div className="mt-5">
        <ReposCard />
      </div>
    </div>
  );
}

// ─── 1 · Webhook setup ─────────────────────────────────────
function WebhookCard() {
  const { pushToast } = useAtlasStore();
  const { data, isLoading } = useQuery({ queryKey: ["webhook-config"], queryFn: api.webhookCfg });

  const copy = async (text: string, label: string) => {
    await copyToClipboard(text);
    pushToast(`${label} copied`, "success");
  };

  return (
    <Card>
      <CardHead
        title={<span className="inline-flex items-center gap-2"><Sparkles className="w-4 h-4 text-brand-500" /> Webhook setup</span>}
        hint="Configure once per GitHub repo"
      />
      <div className="p-5 space-y-4">
        <p className="text-sm text-ink-600">
          In each GitHub repository → <b>Settings</b> → <b>Webhooks</b> → <b>Add webhook</b>:
        </p>

        <Box label="Payload URL" hint="Click the URL to copy. If running behind a router, swap the host for your public URL (smee.io or ngrok)." copyable>
          {isLoading ? <Skeleton className="h-5 w-full" /> : (
            <code
              onClick={() => copy(data!.url_template, "Webhook URL")}
              className="block break-all text-amber-300 hover:text-amber-200 cursor-pointer"
            >{data?.url_template}</code>
          )}
        </Box>

        <Box label="Content type" mono>application/json</Box>

        <Box label="Secret"
          hint={`Must match GITHUB_WEBHOOK_SECRET in your .env · ${data?.secret_set ? "currently set" : "NOT SET"}`}
          mono>
          {data?.secret_set ? "(the same string in your .env file)" : "⚠ NOT SET — review will reject webhooks"}
        </Box>

        <Box label="Which events" mono>
          Let me select individual events → ✓ Pull requests<br />
          <span className="text-ink-400">(opened · synchronize · reopened · ready_for_review)</span>
        </Box>

        <div className="grid grid-cols-3 gap-3">
          <Stat icon={<ShieldCheck className="w-3.5 h-3.5" />} label="Auto-post threshold" value={isLoading ? "…" : `${data!.auto_post_threshold}%`} />
          <Stat icon={<Power className="w-3.5 h-3.5" />} label="Block on BLOCKER" value={isLoading ? "…" : (data!.block_on_blocker ? "ON" : "off")} active={data?.block_on_blocker} />
          <Stat icon={<MessageSquare className="w-3.5 h-3.5" />} label="Run on draft PRs" value={isLoading ? "…" : (data!.run_on_draft_prs ? "ON" : "off")} active={data?.run_on_draft_prs} />
        </div>
      </div>
    </Card>
  );
}

function Box({ label, hint, mono, copyable, children }: {
  label: string; hint?: string; mono?: boolean; copyable?: boolean; children: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-[11.5px] font-semibold text-ink-600 mb-1.5 flex items-center gap-1.5">
        <span>{label}</span>
        {copyable && <Copy className="w-3 h-3 text-ink-400" />}
      </div>
      <div className={cn(
        "rounded-md border px-3 py-2.5 text-[12.5px] leading-relaxed",
        mono ? "font-mono bg-ink-900 text-ink-100 border-ink-800" : "bg-ink-900 text-ink-100 border-ink-800",
      )}>
        {children}
      </div>
      {hint && <div className="text-[11px] text-ink-500 mt-1">{hint}</div>}
    </div>
  );
}

function Stat({ icon, label, value, active }: { icon: React.ReactNode; label: string; value: string; active?: boolean }) {
  return (
    <div className={cn("rounded-md border px-3 py-2.5", active ? "bg-emerald-50 border-emerald-200" : "bg-ink-50 border-ink-200")}>
      <div className={cn("text-[10.5px] uppercase font-bold tracking-wider flex items-center gap-1.5",
        active ? "text-emerald-700" : "text-ink-500")}>
        {icon}{label}
      </div>
      <div className={cn("text-sm font-bold mt-0.5", active ? "text-emerald-700" : "text-ink-900")}>{value}</div>
    </div>
  );
}

// ─── 2 · Connected repos ───────────────────────────────────
function ReposCard() {
  const setRepoDrawerOpen = useAtlasStore(s => s.setRepoDrawerOpen);
  const { data: repos, isLoading } = useQuery({ queryKey: ["repos"], queryFn: api.listRepos, refetchInterval: 30_000 });

  return (
    <Card>
      <CardHead
        title={<span className="inline-flex items-center gap-2"><GitBranch className="w-4 h-4 text-brand-500" /> Connected repositories</span>}
        actions={<Button variant="primary" onClick={() => setRepoDrawerOpen(true)}><Plus className="w-3.5 h-3.5" /> Connect a repo</Button>}
      />
      {isLoading ? (
        <div className="p-5 space-y-3">{[...Array(2)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}</div>
      ) : !repos || repos.length === 0 ? (
        <EmptyState
          icon={<GitBranch className="w-5 h-5" />}
          title="No repos connected yet"
          subtitle="Either pre-register one with + Connect a repo, or just point a webhook at the URL above — Atlas auto-registers on first webhook."
          action={<Button variant="primary" onClick={() => setRepoDrawerOpen(true)}><Plus className="w-3.5 h-3.5" /> Connect a repo</Button>}
        />
      ) : (
        <ul className="divide-y divide-ink-100">
          {repos.map(r => <RepoRow key={r.id} repo={r} />)}
        </ul>
      )}
    </Card>
  );
}

function RepoRow({ repo }: { repo: Repo }) {
  const qc = useQueryClient();
  const { pushToast } = useAtlasStore();

  const toggle = useMutation({
    mutationFn: () => api.updateRepo(repo.id, { enabled: !repo.enabled }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["repos"] }); pushToast(repo.enabled ? "Repo disabled" : "Repo enabled", "success"); },
    onError: e => pushToast("Failed: " + (e as Error).message, "error"),
  });
  const remove = useMutation({
    mutationFn: () => api.deleteRepo(repo.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["repos"] }); pushToast("Repo removed", "success"); },
    onError: e => pushToast("Failed: " + (e as Error).message, "error"),
  });

  return (
    <motion.li
      layout
      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      className="px-5 py-3.5 grid grid-cols-[1fr_120px_140px_120px_180px] gap-3 items-center"
    >
      <div className="min-w-0">
        <div className="text-sm font-semibold text-ink-900 truncate inline-flex items-center gap-2">
          {repo.full_name}
          {repo.auto_registered && (
            <span className="pill bg-brand-50 text-brand-700 border-brand-200 text-[10px] px-2 py-0.5">
              auto-registered
            </span>
          )}
        </div>
        <div className="text-[12px] text-ink-500 mt-0.5">
          {repo.default_branch} · {repo.review_count} review{repo.review_count === 1 ? "" : "s"} · last event {repo.last_event_at ? relativeTime(repo.last_event_at) : "never"}
        </div>
      </div>
      <span className={cn("pill", repo.enabled
        ? "bg-emerald-50 text-emerald-700 border-emerald-200"
        : "bg-rose-50 text-rose-700 border-rose-200")}>
        <span className={cn("w-1.5 h-1.5 rounded-full", repo.enabled ? "bg-emerald-500" : "bg-rose-500")} />
        {repo.enabled ? "enabled" : "disabled"}
      </span>
      <div className="text-[12px] text-ink-600 font-mono">
        threshold: {repo.threshold_override === null ? <i className="text-ink-400">default</i> : `${repo.threshold_override}%`}
      </div>
      <div className="text-[12px]">
        {repo.slack_url ? <span className="text-emerald-700 font-semibold">Slack ✓</span> : <span className="text-ink-400">no Slack</span>}
      </div>
      <div className="flex gap-2 justify-end">
        <Button variant={repo.enabled ? "danger" : "success"} disabled={toggle.isPending} onClick={() => toggle.mutate()}>
          <Power className="w-3.5 h-3.5" /> {repo.enabled ? "Disable" : "Enable"}
        </Button>
        <Button variant="secondary" disabled={remove.isPending} onClick={() => {
          if (confirm(`Remove ${repo.full_name}?\n\nAtlas will stop processing its webhooks unless re-registered.`)) remove.mutate();
        }}>
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>
    </motion.li>
  );
}
