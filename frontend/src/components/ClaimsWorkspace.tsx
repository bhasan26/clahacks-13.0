import React, { useEffect, useState } from "react";
import clsx from "clsx";
import { Eye, FileStack, FileUp, History, RefreshCw, Trash2, X, type LucideIcon } from "lucide-react";
import { clearUploadedClaims, workflowRequest } from "../api";
import { ClaimFindingsReport } from "../types";
import { claimVerdict, hasNewerRule } from "./ClaimFindingsPanel";
import { ClaimIntake } from "./ClaimIntake";
import { Button, Card, CardHeader, Notice, PageHeader, StatusBadge, Tag, TONE, type Tone } from "./ui";

type ResultFilter = "all" | "problems" | "ok" | "unknown";
const FILTERS: Array<[ResultFilter, string]> = [
  ["all", "All"],
  ["problems", "Problems"],
  ["ok", "No problems"],
  ["unknown", "Can't check"],
];

const matchesFilter = (report: ClaimFindingsReport, filter: ResultFilter) => {
  const tone = claimVerdict(report).tone;
  if (filter === "all") return true;
  if (filter === "problems") return tone === "rejected" || tone === "action";
  return tone === filter;
};

const STAT_STYLE: Record<Tone | "all", { icon: LucideIcon; circle: string; bar: string }> = {
  all: { icon: FileStack, circle: "bg-brand-soft text-brand", bar: "bg-brand" },
  ok: { icon: TONE.ok.icon, circle: "bg-ok-soft text-ok", bar: "bg-ok" },
  action: { icon: TONE.action.icon, circle: "bg-warn-soft text-warn", bar: "bg-warn" },
  rejected: { icon: TONE.rejected.icon, circle: "bg-bad-soft text-bad", bar: "bg-bad" },
  unknown: { icon: TONE.unknown.icon, circle: "bg-unknown-soft text-unknown", bar: "bg-subtle" },
};

function Stat({ label, value, total, kind, onClick, active }: { label: string; value: number; total: number; kind: Tone | "all"; onClick: () => void; active: boolean }) {
  const { icon: Icon, circle, bar } = STAT_STYLE[kind];
  const share = total ? Math.round((value / total) * 100) : 0;
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={clsx(
        "rounded-card bg-surface p-5 text-left shadow-card transition-all duration-150 cursor-pointer hover:-translate-y-px",
        active ? "ring-2 ring-cta/60" : "ring-1 ring-line/70",
      )}
    >
      <span className="flex items-center gap-3">
        <span className={clsx("flex size-10 items-center justify-center rounded-full", circle)}>
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <span className="text-sm font-semibold text-ink-2">{label}</span>
      </span>
      <span className="mt-4 block text-3xl font-semibold tabular-nums tracking-tight text-ink">{value}</span>
      <span className="mt-3 block h-1.5 overflow-hidden rounded-full bg-sunken ring-1 ring-inset ring-line">
        <span className={clsx("block h-full rounded-full", bar)} style={{ width: `${kind === "all" ? 100 : share}%` }} />
      </span>
      <span className="mt-1.5 block text-xs text-subtle">{kind === "all" ? "all saved claims" : `${share}% of claims`}</span>
    </button>
  );
}

export function ClaimsWorkspace({
  onSelect,
  onChanged,
  onClearCaseFilter,
  caseIds = [],
}: {
  onSelect: (id: string) => void;
  onChanged: () => void;
  onClearCaseFilter: () => void;
  caseIds?: string[];
}) {
  const [filter, setFilter] = useState<ResultFilter>("all");
  const [insurerFilter, setInsurerFilter] = useState("All");
  const [reports, setReports] = useState<ClaimFindingsReport[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const latest: ClaimFindingsReport[] = await workflowRequest("/claims/findings");
    setReports(latest);
    return latest;
  };
  useEffect(() => {
    load().catch((e) => setError(e.message));
    const timer = setInterval(() => load().catch(() => {}), 5000);
    return () => clearInterval(timer);
  }, []);
  const action = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
      onChanged();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const uploadJSON = async (file?: File) => {
    if (!file) return;
    if (file.size > 1024 * 1024) {
      setError("Claim JSON exceeds 1 MB.");
      return;
    }
    try {
      const data = JSON.parse(await file.text());
      await action(() => workflowRequest("/claims/import", { claims: data.claims || [data] }));
    } catch (e: any) {
      setError(e.message);
    }
  };

  const count = (value: ResultFilter) => reports.filter((r) => matchesFilter(r, value)).length;
  const shown = reports.filter(
    (r) =>
      matchesFilter(r, filter) &&
      (insurerFilter === "All" || r.insurer_id === insurerFilter) &&
      (!caseIds.length || caseIds.includes(r.case_id)),
  );

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-8 py-8">
      <PageHeader
        title="Claims"
        description="Check a claim against the latest approved insurer rules before you send it."
        actions={
          <label className="inline-flex h-10 cursor-pointer items-center gap-1.5 rounded-xl bg-surface px-4 text-sm font-semibold text-ink-2 shadow-xs ring-1 ring-inset ring-line-strong hover:bg-sunken">
            <FileUp className="size-4" aria-hidden="true" />
            Import claims (JSON)
            <input
              aria-label="Import synthetic claim JSON"
              className="sr-only"
              type="file"
              accept="application/json,.json"
              onChange={(e) => {
                uploadJSON(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </label>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Saved claims" kind="all" value={reports.length} total={reports.length} onClick={() => setFilter("all")} active={filter === "all"} />
        <Stat label="No problems" kind="ok" value={count("ok")} total={reports.length} onClick={() => setFilter("ok")} active={filter === "ok"} />
        <Stat label="Need attention" kind="action" value={count("problems")} total={reports.length} onClick={() => setFilter("problems")} active={filter === "problems"} />
        <Stat label="Can't check yet" kind="unknown" value={count("unknown")} total={reports.length} onClick={() => setFilter("unknown")} active={filter === "unknown"} />
      </div>

      {error && <Notice tone="rejected">{error}</Notice>}
      {notice && (
        <Notice
          tone="brand"
          action={
            <button className="text-muted hover:text-ink cursor-pointer" aria-label="Dismiss" onClick={() => setNotice("")}>
              <X className="size-4" />
            </button>
          }
        >
          {notice}
        </Notice>
      )}

      <ClaimIntake
        onSaved={(caseId, updated) => {
          setNotice(`${updated ? "Updated" : "Saved"} claim ${caseId}.`);
          load().catch(() => {});
          onChanged();
        }}
      />

      <Card>
        <CardHeader
          title={`Saved claims (${reports.length})`}
          description="Re-checked automatically whenever an insurer rule is approved."
          actions={
            <>
              <div className="inline-flex rounded-xl bg-sunken p-1 ring-1 ring-inset ring-line" role="group" aria-label="Filter by result">
                {FILTERS.map(([value, label]) => (
                  <button
                    key={value}
                    aria-pressed={filter === value}
                    onClick={() => setFilter(value)}
                    className={clsx(
                      "rounded-lg px-3 py-1 text-xs font-semibold transition-colors duration-150 cursor-pointer",
                      filter === value ? "bg-surface text-ink shadow-xs ring-1 ring-line" : "text-muted hover:text-ink",
                    )}
                  >
                    {label} <span className="tabular-nums text-subtle">{count(value)}</span>
                  </button>
                ))}
              </div>
              <select
                aria-label="Filter claims by insurer"
                className="h-9 rounded-xl bg-surface px-3 text-xs text-ink-2 ring-1 ring-inset ring-line-strong focus:outline-none focus:ring-2 focus:ring-brand"
                value={insurerFilter}
                onChange={(e) => setInsurerFilter(e.target.value)}
              >
                {["All", ...new Set(reports.map((r) => r.insurer_id))].map((v) => (
                  <option key={v} value={v}>{v === "All" ? "All insurers" : v}</option>
                ))}
              </select>
            </>
          }
        />

        {caseIds.length > 0 && (
          <div className="border-b border-line px-5 py-3">
            <Notice
              tone="action"
              action={<Button size="sm" onClick={onClearCaseFilter}>Show all claims</Button>}
            >
              Showing only the {caseIds.length} claim(s) affected by a rule change.
            </Notice>
          </div>
        )}

        {shown.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-sunken text-xs font-semibold uppercase tracking-wide text-subtle">
                <tr>
                  <th className="px-6 py-3 font-semibold">Claim</th>
                  <th className="px-3 py-2.5 font-medium">Insurer · plan</th>
                  <th className="px-3 py-2.5 font-medium">Codes</th>
                  <th className="px-3 py-2.5 font-medium">Result</th>
                  <th className="px-5 py-2.5 text-right font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {shown.map((r) => {
                  const verdict = claimVerdict(r);
                  return (
                    <tr key={r.case_id} className="transition-colors duration-150 hover:bg-sunken">
                      <td className="px-6 py-3.5">
                        <span className="font-mono text-xs text-ink">{r.case_id}</span>
                        {r.policy_environment === "demo" && <span className="ml-2"><Tag>Demo</Tag></span>}
                      </td>
                      <td className="px-3 py-3">
                        <span className="block text-ink-2">{(r.insurer_name || r.insurer_id || "Unknown").replace(" (SIMULATED)", "")}</span>
                        <span className="block font-mono text-xs text-subtle">{r.plan_id || "plan missing"}</span>
                      </td>
                      <td className="px-3 py-3 font-mono text-xs text-ink-2">{r.findings.map((f) => f.item.code).join(", ")}</td>
                      <td className="px-3 py-3">
                        <StatusBadge tone={verdict.tone}>{verdict.title}</StatusBadge>
                        {hasNewerRule(r) && (
                          <span className="mt-1 flex items-center gap-1 text-xs font-medium text-warn">
                            <History className="size-3.5" aria-hidden="true" />
                            Rule changed recently
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex justify-end gap-1.5">
                          <Button
                            size="sm"
                            variant="ghost"
                            icon={RefreshCw}
                            disabled={busy}
                            title="Fetch the latest insurer rules for this claim"
                            onClick={() => action(() => workflowRequest("/policy-sync/run", { claim_id: r.case_id }))}
                          >
                            Re-check
                          </Button>
                          <Button size="sm" icon={Eye} onClick={() => onSelect(r.case_id)}>
                            View
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="px-5 py-10 text-center text-sm text-muted">
            {reports.length
              ? "No claims match this filter."
              : "No saved claims yet. Check a claim above and save it, or load the demo in Insurer rules."}
          </p>
        )}

        {reports.some((r) => r.is_uploaded) && (
          <div className="border-t border-line px-5 py-3">
            <Button
              size="sm"
              variant="ghost"
              icon={Trash2}
              disabled={busy}
              onClick={() => {
                if (!window.confirm("Remove every claim you added on this page? Imported hospital claims stay.")) return;
                action(async () => {
                  const { removed } = await clearUploadedClaims();
                  setNotice(`Removed ${removed} claim(s) you added.`);
                });
              }}
            >
              Remove claims I added
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
