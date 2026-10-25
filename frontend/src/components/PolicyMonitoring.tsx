import React, { useEffect, useState } from "react";
import {
  workflowRequest,
  fetchPolicyProposals,
  approvePolicyProposal,
} from "../api";
import { ProposedPolicyChange } from "../types";
const panel =
  "bg-white border border-[#D8E5DC] rounded-2xl p-5 space-y-3 shadow-sm";
const button =
  "px-4 py-2 rounded-xl bg-[#092328] text-white text-xs font-bold disabled:opacity-50 cursor-pointer";
const time = (value?: string) =>
  value ? new Date(value).toLocaleString() : "Not yet recorded";

export function PolicyMonitoring({
  onReview,
  onChanged,
}: {
  onReview: (documentId: string) => void;
  onChanged: () => void;
}) {
  const [sources, setSources] = useState<any[]>([]),
    [catalog, setCatalog] = useState<any[]>([]),
    [runs, setRuns] = useState<any[]>([]);
  const [proposals, setProposals] = useState<ProposedPolicyChange[]>([]),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [search, setSearch] = useState("");
  const [schedule, setSchedule] = useState<any>({});
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
  };
  useEffect(() => {
    let active = true;
    const refresh = () =>
      load(() => active).catch((e) => active && setMessage(e.message));
    const debounce = setTimeout(refresh, 200);
    const timer = setInterval(refresh, 5000);
    return () => {
      active = false;
      clearTimeout(debounce);
      clearInterval(timer);
    };
  }, [search]);
  const action = async (fn: () => Promise<any>) => {
    setBusy(true);
    setMessage("");
    try {
      const result = await fn();
      setMessage(
        result.status === "already_running"
          ? "A backend sync is already running."
          : JSON.stringify(
              result.runs
                ? result.runs.map((r: any) => ({
                    source: r.source_id,
                    status: r.status,
                    discovered: r.discovered,
                    changed: r.changed,
                    failed: r.failed,
                  }))
                : result,
            ),
      );
      await load();
      onChanged();
    } catch (e: any) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  };
  const pending = proposals.filter(
    (p) =>
      p.review_state === "pending_review" ||
      p.review_state === "needs_correction",
  );
  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-5">
      <div className="flex justify-between gap-4">
        <div>
          <h1 className="text-xl font-black">Policy Monitoring</h1>
          <p className="text-xs text-[#698579]">
            Read-only insurer policy discovery, source freshness and human
            review. Patient data stays on the hospital side.
          </p>
        </div>
        <button
          className={button}
          disabled={busy}
          onClick={() => action(() => workflowRequest("/policy-sync/run", {}))}
        >
          Sync All Sources
        </button>
      </div>
      <p className="text-xs">
        Backend schedule:{" "}
        {schedule.scheduler_enabled
          ? `enabled, every ${schedule.interval_seconds} seconds`
          : "off — enable explicitly on the server"}
        . Source access and exact plan applicability are separate checks.
      </p>
      {message && (
        <div
          role="status"
          className="p-4 bg-amber-50 rounded-xl text-xs break-words"
        >
          {message}
        </div>
      )}
      <div className="grid md:grid-cols-2 gap-4">
        {sources.map((s) => (
          <section className={panel} key={s.source_id}>
            <div className="flex justify-between">
              <h2 className="font-bold text-sm">{s.name}</h2>
              <span className="text-xs uppercase">
                {s.is_synthetic ? "DEMO / SIMULATED" : s.status}
              </span>
            </div>
            <a
              className="text-xs text-[#2A835F] underline break-all"
              href={s.index_url}
              target="_blank"
              rel="noreferrer"
            >
              {s.index_url}
            </a>
            <p className="text-xs">
              {s.source_type} · Last attempt: {time(s.last_attempt_at)}
              <br />
              Last successful sync: {time(s.last_success_at)}
              <br />
              Next backend sync:{" "}
              {schedule.scheduler_enabled &&
              (!schedule.scheduler_sources?.length ||
                schedule.scheduler_sources.includes(s.source_id))
                ? time(s.next_sync_at)
                : "Schedule disabled for this source"}
            </p>
            <div className="flex flex-wrap gap-3 text-xs">
              {[
                "discovered",
                "changed",
                "unchanged",
                "pending_review",
                "failed",
              ].map((k) => (
                <span key={k}>
                  {k.replace("_", " ")}: <strong>{s.counts?.[k] || 0}</strong>
                </span>
              ))}
            </div>
            {s.last_error && (
              <p className="text-xs text-red-700">{s.last_error}</p>
            )}
            <ul className="text-xs text-[#698579] list-disc pl-4">
              {s.limitations.map((x: string) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
            <button
              className={button}
              disabled={busy}
              onClick={() =>
                action(() =>
                  workflowRequest("/policy-sync/run", {
                    source_id: s.source_id,
                  }),
                )
              }
            >
              Sync Now
            </button>
          </section>
        ))}
      </div>
      <section className={panel}>
        <h2 className="font-bold">
          Independent synthetic integration demonstration
        </h2>
        <p className="text-xs">
          Start the separate hospital and insurer simulator services first.
          Import 40 claims, sync policies, review the five baseline
          representations, then publish and review a restriction and a delay.
          These are fictional examples; no insurer partnership is implied.
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            className={button}
            disabled={busy}
            onClick={() =>
              action(() => workflowRequest("/demo/import-hospital", {}))
            }
          >
            1. Import 40 hospital claims
          </button>
          <button
            className={button}
            disabled={busy}
            onClick={() =>
              action(() =>
                workflowRequest("/policy-sync/run", {
                  source_id: "demo-insurer-api",
                }),
              )
            }
          >
            2. Sync DEMO insurer
          </button>
          <button
            className={button}
            disabled={busy}
            onClick={() =>
              action(() =>
                workflowRequest("/demo/publish-insurer", {
                  scenario: "restriction",
                }),
              )
            }
          >
            Publish DEMO UHC restriction
          </button>
          <button
            className={button}
            disabled={busy}
            onClick={() =>
              action(() =>
                workflowRequest("/demo/publish-insurer", { scenario: "delay" }),
              )
            }
          >
            Publish DEMO UHC delay
          </button>
        </div>
      </section>
      <section className={panel}>
        <h2 className="font-bold">
          Pending policy representations ({pending.length})
        </h2>
        <p className="text-xs">
          Approval activates a checked policy representation; it never approves
          a patient claim.
        </p>
        {pending.map((p) => (
          <div
            key={p.proposal_id}
            className="border-t border-[#D8E5DC] pt-3 flex flex-wrap items-center gap-3 text-xs"
          >
            <div className="flex-1">
              <strong>
                {p.insurer_name || "Unknown insurer"} ·{" "}
                {p.policy_reference || p.proposal_id}
              </strong>
              <p>
                {p.plan_ids.join(", ") || "Plan scope unknown"} ·{" "}
                {p.target_code || "Code unknown"} ·{" "}
                {p.proposed_effect || "Effect unknown"} ·{" "}
                {p.effective_from || "Date unknown"}
              </p>
              <blockquote className="mt-1 text-[#698579]">
                {p.supporting_quote}
              </blockquote>
            </div>
            <button className={button} onClick={() => onReview(p.document_id)}>
              Inspect / correct evidence
            </button>
            {p.extraction_method === "structured_simulator" && (
              <button
                className={button}
                disabled={busy}
                onClick={() =>
                  action(() =>
                    approvePolicyProposal(
                      p.proposal_id,
                      "Reviewed synthetic simulator schema, exact plan, CA jurisdiction, code, effective date and source evidence.",
                    ),
                  )
                }
              >
                Approve DEMO representation
              </button>
            )}
          </div>
        ))}
      </section>
      <section className={panel}>
        <div className="flex gap-3 items-center">
          <h2 className="font-bold">Policy catalog ({catalog.length} shown)</h2>
          <input
            aria-label="Search policy catalog"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Title, code, insurer"
            className="p-2 border rounded-xl text-xs"
          />
        </div>
        <div className="max-h-96 overflow-auto">
          <table className="w-full text-xs text-left">
            <thead>
              <tr>
                <th>Insurer / jurisdiction</th>
                <th>Policy / version</th>
                <th>Plan / codes</th>
                <th>Verification</th>
              </tr>
            </thead>
            <tbody>
              {catalog.map((c) => (
                <tr className="border-t border-[#D8E5DC]" key={c.catalog_id}>
                  <td className="py-3">
                    {c.insurer_name}
                    <br />
                    {c.jurisdictions.join(", ") || "Unknown jurisdiction"}
                  </td>
                  <td>
                    <a
                      className="underline"
                      href={c.source_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {c.title}
                    </a>
                    <br />
                    {c.policy_id} · {c.revision || "Revision unknown"}
                  </td>
                  <td>
                    {c.plan_ids.join(", ") || "Unverified plan"}
                    <br />
                    {c.codes.join(", ") || "Codes not indexed"}
                  </td>
                  <td>
                    {c.is_synthetic ? "SIMULATED · " : ""}
                    {c.status}
                    {c.requires_billing_articles && (
                      <p>
                        LCD: associated billing articles and MAC jurisdiction
                        require review.
                      </p>
                    )}
                    <br />
                    {c.scope_verified
                      ? "Scope stated in structured source"
                      : "Human scope verification required"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className={panel}>
        <h2 className="font-bold">Recent sync history</h2>
        {runs.slice(0, 10).map((r) => (
          <p className="text-xs" key={r.run_id}>
            {time(r.started_at)} · {r.source_id} · {r.status} · discovered{" "}
            {r.discovered}, changed {r.changed}, failed {r.failed}
            {r.gaps.length > 0 && (
              <span className="block text-[#698579]">{r.gaps.join(" ")}</span>
            )}
          </p>
        ))}
      </section>
    </div>
  );
}
