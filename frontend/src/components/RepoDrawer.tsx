import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAtlasStore } from "../store/useAtlasStore";
import { api } from "../lib/api";
import { Button, Drawer, Field, inputCls, textareaCls } from "./ui";

export function RepoDrawer() {
  const { repoDrawerOpen, setRepoDrawerOpen, pushToast } = useAtlasStore();
  const qc = useQueryClient();
  const [fullName, setFullName] = useState("");
  const [branch, setBranch] = useState("main");
  const [threshold, setThreshold] = useState<string>("");
  const [slack, setSlack] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!/^[^/\s]+\/[^/\s]+$/.test(fullName.trim())) { pushToast("Use owner/name format", "warning"); return; }
    setBusy(true);
    try {
      await api.createRepo({
        full_name: fullName.trim(),
        enabled: true,
        default_branch: branch || "main",
        threshold_override: threshold ? parseInt(threshold, 10) : null,
        slack_url: slack || null,
        notes: notes || null,
      });
      pushToast("Connected " + fullName, "success");
      qc.invalidateQueries({ queryKey: ["repos"] });
      reset(); setRepoDrawerOpen(false);
    } catch (e: any) {
      pushToast("Failed: " + e.message, "error");
    } finally { setBusy(false); }
  };

  const reset = () => { setFullName(""); setBranch("main"); setThreshold(""); setSlack(""); setNotes(""); };
  const close = () => { reset(); setRepoDrawerOpen(false); };

  return (
    <Drawer
      open={repoDrawerOpen}
      onClose={close}
      title="Connect a repository"
      footer={<>
        <Button variant="secondary" onClick={close}>Cancel</Button>
        <Button variant="primary" onClick={submit} disabled={busy}>{busy ? "Connecting…" : "Connect"}</Button>
      </>}
    >
      <p className="text-sm text-ink-600 mb-4">
        ChangePilot auto-registers repos the first time a webhook fires, but you can also pre-register
        them here to set per-repo overrides before any PR opens.
      </p>

      <Field label="Repository · owner/name" required hint="Must match GitHub's full name exactly">
        <input className={inputCls} value={fullName} onChange={e => setFullName(e.target.value)} placeholder="fiserv/dcs-pipelines" />
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Default branch">
          <input className={inputCls} value={branch} onChange={e => setBranch(e.target.value)} />
        </Field>
        <Field label="Auto-post threshold override" hint="Leave blank to use workspace default">
          <input className={inputCls} type="number" min={0} max={100} value={threshold} onChange={e => setThreshold(e.target.value)} placeholder="e.g. 75" />
        </Field>
      </div>

      <Field label="Slack webhook (optional)">
        <input className={inputCls} value={slack} onChange={e => setSlack(e.target.value)} placeholder="https://hooks.slack.com/services/…" />
      </Field>

      <Field label="Notes">
        <textarea className={textareaCls} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Who owns it · what it does · any quirks" />
      </Field>
    </Drawer>
  );
}
