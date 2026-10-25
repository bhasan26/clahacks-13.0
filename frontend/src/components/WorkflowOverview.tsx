import React, { useEffect, useState } from "react";
import { workflowRequest, fetchAlerts } from "../api";
export function WorkflowOverview() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    const refresh = () =>
      workflowRequest("/workflow/summary")
        .then(setData)
        .catch(() => {});
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, []);
  if (!data) return null;
  return (
    <section className="px-6 pt-8 max-w-7xl mx-auto space-y-4">
      <div>
        <h1 className="text-xl font-black">
          Hospital claims and policy synchronization
        </h1>
        <p className="text-xs text-[#698579]">
          Check pending claims before submission. Track policy changes and
          notify employees. Synthetic patient data only.
        </p>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {[
          ["pending_claims", "Pending claims"],
          ["needs_attention", "Claims needing attention"],
          ["newly_affected_claims", "Claims with open alerts"],
          ["policies_indexed", "Policies indexed"],
          ["sync_failures", "Sources with failures"],
        ].map(([key, label]) => (
          <div key={key} className="p-4 border border-[#D8E5DC] rounded-2xl">
            <p className="text-xs">{label}</p>
            <p className="text-2xl font-black">{data[key]}</p>
          </div>
        ))}
      </div>
      <p className="text-xs">
        {data.unable_to_verify} claims unable to verify · {data.pending_reviews}{" "}
        policy representations pending review · {data.sources_healthy} sources
        healthy or explicitly simulated.
      </p>
    </section>
  );
}
export function ClaimAlerts({
  cases,
  onSelect,
}: {
  cases: any[];
  onSelect: (id: string) => void;
}) {
  const [alerts, setAlerts] = useState<any[]>([]);
  useEffect(() => {
    const refresh = () =>
      fetchAlerts()
        .then(setAlerts)
        .catch(() => {});
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, []);
  return (
    <section className="mx-6 mt-8 p-5 border border-[#D8E5DC] rounded-2xl space-y-3">
      <h1 className="text-xl font-black">Alerts and employee follow-up</h1>
      <p className="text-xs">
        Policy findings are advisory. An alert does not deny or submit a claim.
      </p>
      {alerts.map((a) => (
        <article
          key={a.alert_id}
          className="border-t border-[#D8E5DC] pt-3 text-xs space-y-1"
        >
          <div className="flex justify-between">
            <strong>
              {a.headline} · {a.status}
            </strong>
            <button className="underline" onClick={() => onSelect(a.case_id)}>
              Open claim {a.case_id}
            </button>
          </div>
          <p>
            {cases.find((c) => c.case_id === a.case_id)?.insurer_name ||
              cases.find((c) => c.case_id === a.case_id)?.insurer_id}{" "}
            · Policy {a.rule_id} v{a.change.to_version} · effective{" "}
            {a.effective_date || "unknown"}
          </p>
          <p>{a.explanation}</p>
          <blockquote className="text-[#698579]">
            {a.evidence_quote ||
              "No source quotation available; verify before acting."}
          </blockquote>
          <p>Follow-up: {a.suggested_action}</p>
          {a.closed_reason && <p>{a.closed_reason}</p>}
        </article>
      ))}
      {!alerts.length && (
        <p className="text-xs">
          No policy findings alerts have been generated.
        </p>
      )}
    </section>
  );
}
