import React, { useEffect, useState } from "react";
import {
  workflowRequest,
  fetchPolicyProposals,
  approvePolicyProposal,
} from "../api";
import clsx from "clsx";
import {
  CheckCheck,
  CheckCircle2,
  ChevronRight,
  Clock,
  Database,
  ExternalLink,
  FileText,
  FlaskConical,
  RefreshCw,
  ShieldAlert,
  WifiOff,
  X,
  type LucideIcon,
} from "lucide-react";
import { ProposedPolicyChange } from "../types";
import { Button, Card, CardHeader, Notice, PageHeader, Tag } from "./ui";

// "Insurer rules": where rules come from, which ones wait for approval, and demo controls.
const DEMO_APPROVAL_NOTE =
  "Reviewed synthetic simulator schema, exact plan, CA jurisdiction, code, effective date and source evidence.";

const time = (value?: string) => (value ? new Date(value).toLocaleString() : "never");

const EFFECT_WORDS: Record<string, string> = {
  covered: "covered",
  excluded: "not covered",
  requires_prior_approval: "needs prior approval",
  requires_documents: "needs documents",
};

function sourceStatus(source: any): { icon: LucideIcon; tone: string; label: string } {
  if (source.is_synthetic) return { icon: FlaskConical, tone: "text-demo", label: "Demo insurer with made-up rules — working" };
  if (source.status === "authorization_required")
    return { icon: ShieldAlert, tone: "text-bad", label: "Blocked — the insurer doesn't allow automatic checks without permission" };
  if (source.status === "unavailable" || (source.last_error && !source.last_success_at))
    return { icon: WifiOff, tone: "text-bad", label: "Not reachable right now" };
  if (!source.last_success_at) return { icon: Clock, tone: "text-subtle", label: "Not checked yet" };
  if (source.source_id === "anthem-ca-public")
    return { icon: FileText, tone: "text-warn", label: "Policy titles only — the policy files are blocked" };
  if (source.status === "partial")
    return { icon: CheckCircle2, tone: "text-ok", label: "Working — some documents need a licence or are restricted" };
  return { icon: CheckCircle2, tone: "text-ok", label: "Working" };
}

function describeRuns(result: any) {
  if (result?.status === "already_running") return "A check is already running. Try again in a moment.";
  if (!result?.runs) return "Done.";
  return result.runs
    .map((r: any) => {
      const found = r.changed ? `${r.changed} new or changed rule(s) found` : "no changes";
      return `${r.source_id}: ${r.failed ? `${found}, ${r.failed} could not be read` : found}`;
    })
    .join(" · ");
}

export function PolicyMonitoring({
  onReview,
  onChanged,
}: {
  onReview: (documentId: string) => void;
  onChanged: () => void;
}) {
  const [sources, setSources] = useState<any[]>([]);
  const [catalog, setCatalog] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [proposals, setProposals] = useState<ProposedPolicyChange[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [search, setSearch] = useState("");
  const [schedule, setSchedule] = useState<any>({});
  const [loaded, setLoaded] = useState(false);

  const load = async (isActive: () => boolean = () => true) => {
    const [a, b, c, d] = await Promise.all([
      workflowRequest("/policy-sync/sources"),
      workflowRequest(`/policies/catalog?q=${encodeURIComponent(search)}`),
      workflowRequest("/policy-sync/history"),
      fetchPolicyProposals(),
    ]);
    if (!isActive()) return;
    setSources(a.sources);
    setSchedule(a);
    setCatalog(b);
    setRuns(c);
    setProposals(d);
    setLoaded(true);
  };
  useEffect(() => {
    let active = true;
    const refresh = () => load(() => active).catch((e) => active && setMessage(e.message));
    const debounce = setTimeout(refresh, 200);
    const timer = setInterval(refresh, 5000);
    return () => {
      active = false;
      clearTimeout(debounce);
      clearInterval(timer);
    };
  }, [search]);

  const action = async (fn: () => Promise<any>, describe: (result: any) => string = describeRuns) => {
    setBusy(true);
    setMessage("");
    try {
      setMessage(describe(await fn()));
      await load();
      onChanged();
    } catch (e: any) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  };

  const pending = proposals.filter(
    (p) => p.review_state === "pending_review" || p.review_state === "needs_correction",
  );
  // Bulk approval is limited to structured synthetic rules; real policies are reviewed one by one.
  const demoPending = pending.filter(
    (p) => p.extraction_method === "structured_simulator" && p.review_state === "pending_review",
  );
  // The demo insurer publishes a change, then we check it so the new rule appears for approval.
  const publishAndCheck = async (scenario: "restriction" | "delay") => {
    const result = await workflowRequest("/demo/publish-insurer", { scenario });
    await workflowRequest("/policy-sync/run", { source_id: "demo-insurer-api" });
    return result;
  };
  const approveDemo = (items: ProposedPolicyChange[]) =>
    action(
      async () => {
        for (const p of items) await approvePolicyProposal(p.proposal_id, DEMO_APPROVAL_NOTE);
      },
      () => `Approved ${items.length} demo rule(s). Claims were re-checked.`,
    );
  const setUpDemo = () =>
    action(
      async () => {
        await workflowRequest("/demo/import-hospital", {});
        await workflowRequest("/policy-sync/run", { source_id: "demo-insurer-api" });
        const latest = await fetchPolicyProposals();
        for (const p of latest)
          if (p.extraction_method === "structured_simulator" && p.review_state === "pending_review")
            await approvePolicyProposal(p.proposal_id, DEMO_APPROVAL_NOTE);
      },
      () => "Demo ready: 40 test claims loaded and the demo rules approved. Open Claims to see the results.",
    );

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-8 py-8">
      <PageHeader
        title="Insurer rules"
        description="Where insurer rules come from, and which new rules need your approval before claims are checked against them."
        actions={
          <Button icon={RefreshCw} disabled={busy} onClick={() => action(() => workflowRequest("/policy-sync/run", {}))}>
            Check all sources
          </Button>
        }
      />

      {message && (
        <Notice
          tone="brand"
          action={
            <button className="text-muted hover:text-ink cursor-pointer" aria-label="Dismiss" onClick={() => setMessage("")}>
              <X className="size-4" />
            </button>
          }
        >
          {message}
        </Notice>
      )}

      <Card>
        <CardHeader
          title={!loaded ? "Loading rules…" : pending.length ? `Waiting for your approval (${pending.length})` : "No rules waiting for approval"}
          description="A rule only affects claim checks after a person approves it. Approving a rule never approves a patient claim."
          actions={
            demoPending.length > 0 && (
              <Button variant="primary" icon={CheckCheck} disabled={busy} onClick={() => approveDemo(demoPending)}>
                Approve all demo rules ({demoPending.length})
              </Button>
            )
          }
        />
        {loaded && !pending.length && (
          <p className="flex items-center gap-2 px-5 py-4 text-sm text-muted">
            <CheckCircle2 className="size-4 text-ok" aria-hidden="true" />
            All discovered rules have been reviewed.
          </p>
        )}
        {pending.length > 0 && (
          <ul className="divide-y divide-line">
            {pending.map((p) => {
              const demo = p.extraction_method === "structured_simulator";
              return (
                <li key={p.proposal_id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                  <div className="min-w-64 flex-1">
                    <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink">
                      {p.policy_title || p.policy_reference || "Untitled policy"}
                      {demo ? <Tag>Demo</Tag> : <Tag tone="brand">Real policy</Tag>}
                    </p>
                    <p className="text-xs text-muted">
                      {(p.insurer_name || p.insurer_id || "Insurer unknown").replace(" (SIMULATED)", "")}
                      {p.target_code && (
                        <>
                          {" · code "}
                          <span className="font-mono">{p.target_code}</span>
                        </>
                      )}
                      {p.proposed_effect ? ` · ${EFFECT_WORDS[p.proposed_effect] || p.proposed_effect}` : ""}
                      {p.effective_from ? ` · from ${p.effective_from}` : ""}
                      {p.change_type && p.change_type !== "new_rule" ? ` · ${p.change_type.replace(/_/g, " ")}` : ""}
                    </p>
                    {p.review_state === "needs_correction" && (
                      <p className="mt-0.5 text-xs text-warn">A person must fill in the code and effect before approving.</p>
                    )}
                  </div>
                  {demo && p.review_state === "pending_review" && (
                    <Button size="sm" disabled={busy} onClick={() => approveDemo([p])}>
                      Approve
                    </Button>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => onReview(p.document_id)}>
                    Review
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Rule sources"
          description={`Automatic daily check: ${schedule.scheduler_enabled ? "on" : "off"}. Medicare rules come from the official CMS API; UnitedHealthcare and Aetna require the insurer's permission.`}
        />
        <ul className="divide-y divide-line">
          {sources.map((s) => {
            const status = sourceStatus(s);
            const Icon = status.icon;
            return (
              <li key={s.source_id} className="flex flex-wrap items-center gap-4 px-5 py-3">
                <Icon className={clsx("size-5 shrink-0", status.tone)} aria-hidden="true" />
                <div className="min-w-64 flex-1">
                  <p className="flex items-center gap-2 text-sm font-medium text-ink">
                    {s.name}
                    <a className="text-subtle hover:text-brand" href={s.index_url} target="_blank" rel="noreferrer" aria-label={`Open ${s.name}`}>
                      <ExternalLink className="size-3.5" />
                    </a>
                  </p>
                  <p className="text-xs text-muted">{status.label}</p>
                </div>
                <div className="hidden text-right text-xs text-subtle sm:block">
                  <p>Last checked {time(s.last_success_at)}</p>
                  {s.counts?.discovered ? <p className="tabular-nums">{s.counts.discovered} policies found</p> : null}
                </div>
                <Button
                  size="sm"
                  icon={RefreshCw}
                  disabled={busy}
                  onClick={() => action(() => workflowRequest("/policy-sync/run", { source_id: s.source_id }))}
                >
                  Check now
                </Button>
              </li>
            );
          })}
        </ul>
      </Card>

      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              Demo: make an insurer change a rule <Tag>Demo</Tag>
            </span>
          }
          description="Uses the made-up demo insurer. After each step, approve the new rule above, then look at Claims and Alerts."
        />
        <div className="flex flex-wrap gap-2 px-5 py-4">
          <Button
            disabled={busy}
            onClick={() =>
              action(
                () => publishAndCheck("restriction"),
                (r) => (r.changed ? "UHC changed its knee replacement rule (not covered from Nov 1). It is now waiting for your approval above." : "That change was already published."),
              )
            }
          >
            1. UHC stops covering knee replacement from Nov 1
          </Button>
          <Button
            disabled={busy}
            onClick={() =>
              action(
                () => publishAndCheck("delay"),
                (r) => (r.changed ? "UHC postponed that change to Dec 1. It is now waiting for your approval above." : "That change was already published."),
              )
            }
          >
            2. UHC postpones that change to Dec 1
          </Button>
          <Button variant="ghost" icon={Database} disabled={busy} onClick={setUpDemo}>
            Load demo claims and approve demo rules
          </Button>
        </div>
      </Card>

      <Card>
        <details className="group">
          <summary className="flex cursor-pointer list-none items-center gap-2 px-5 py-4 text-sm font-semibold text-ink">
            <ChevronRight className="size-4 text-subtle transition-transform group-open:rotate-90" aria-hidden="true" />
            All policies found <span className="font-normal tabular-nums text-subtle">({catalog.length} shown)</span>
          </summary>
          <div className="space-y-3 border-t border-line px-5 py-4">
            <input
              aria-label="Search policy catalog"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search title, code, insurer"
              className="block h-9 w-full max-w-sm rounded-lg bg-surface px-3 text-sm ring-1 ring-inset ring-line-strong placeholder:text-subtle focus:outline-none focus:ring-2 focus:ring-brand"
            />
            <p className="text-xs text-muted">Titles discovered from each source. A title is not a usable rule until someone reviews and approves it.</p>
            <div className="max-h-96 overflow-auto rounded-lg border border-line">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-sunken text-muted">
                  <tr>
                    <th className="px-3 py-2 font-medium">Policy</th>
                    <th className="px-3 py-2 font-medium">Insurer</th>
                    <th className="px-3 py-2 font-medium">Codes</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {catalog.map((c) => (
                    <tr key={c.catalog_id} className="hover:bg-sunken">
                      <td className="px-3 py-2">
                        <a className="text-ink hover:text-brand hover:underline" href={c.source_url} target="_blank" rel="noreferrer">{c.title}</a>
                      </td>
                      <td className="px-3 py-2 text-muted">{c.insurer_name}{c.is_synthetic ? " (demo)" : ""}</td>
                      <td className="px-3 py-2 font-mono text-muted">{c.codes.join(", ") || "–"}</td>
                      <td className="px-3 py-2 text-muted">{c.status.replace(/_/g, " ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </details>
      </Card>

      <Card>
        <details className="group">
          <summary className="flex cursor-pointer list-none items-center gap-2 px-5 py-4 text-sm font-semibold text-ink">
            <ChevronRight className="size-4 text-subtle transition-transform group-open:rotate-90" aria-hidden="true" />
            Check history
          </summary>
          <ul className="divide-y divide-line border-t border-line text-xs text-muted">
            {runs.slice(0, 10).map((r) => (
              <li className="px-5 py-2" key={r.run_id}>
                {time(r.started_at)} · <span className="font-mono">{r.source_id}</span> · {r.status} · found {r.discovered}, changed {r.changed}, failed {r.failed}
              </li>
            ))}
          </ul>
        </details>
      </Card>
    </div>
  );
}
