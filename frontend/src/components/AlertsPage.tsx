import React, { useEffect, useState } from "react";
import { ArrowRight, BellOff, ChevronRight, Eye } from "lucide-react";
import { fetchAlerts } from "../api";
import { Alert, Case, InsurerUpdateEntry } from "../types";
import { Button, Card, CardHeader, PageHeader, StatusBadge, Tag, type Tone } from "./ui";

// Alerts: which saved claims a rule change affected, and the rule changes themselves.

const toneFromText = (text = ""): Tone =>
  /not covered|excluded/i.test(text)
    ? "rejected"
    : /prior approval|document|missing|value wrong/i.test(text)
      ? "action"
      : /no rule|unable|verify with the insurer/i.test(text)
        ? "unknown"
        : "ok";

const plainInsurer = (name?: string | null) => (name || "").replace(" (SIMULATED)", "");

const CHANGE_WORDS: Record<string, string> = {
  new_rule: "rule added",
  modification: "rule changed",
  delayed: "change postponed",
  cancelled: "rule cancelled",
};

function describeUpdate(headline: string) {
  // "Aetna (SIMULATED): Pembrolizumab injection policy new_rule" → insurer + plain sentence.
  const [insurer, rest = ""] = headline.split(": ");
  const match = rest.match(/^(.*) policy (\w+)$/);
  return {
    insurer: plainInsurer(insurer),
    item: match ? match[1] : rest,
    change: match ? CHANGE_WORDS[match[2]] || match[2].replace(/_/g, " ") : "",
    demo: insurer.includes("SIMULATED"),
  };
}

const UPDATE_STATUS: Record<string, [Tone, string]> = {
  Effective: ["ok", "In effect"],
  Announced: ["action", "Coming soon"],
  Delayed: ["unknown", "Postponed"],
  Cancelled: ["unknown", "Cancelled"],
};

// ISO dates are formatted; anything else (alerts already say "1 Nov 2026") is shown as given.
const formatDate = (value?: string | null) =>
  !value
    ? "–"
    : /^\d{4}-\d{2}-\d{2}/.test(value)
      ? new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
      : value;

export function AlertsPage({
  cases,
  updates,
  onSelect,
  onViewAffectedCases,
}: {
  cases: Case[];
  updates: InsurerUpdateEntry[];
  onSelect: (id: string) => void;
  onViewAffectedCases: (caseIds: string[]) => void;
}) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  useEffect(() => {
    const refresh = () => fetchAlerts().then(setAlerts).catch(() => {});
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, []);

  const open = alerts.filter((a) => a.status === "open");
  const closed = alerts.filter((a) => a.status !== "open");
  const insurerOf = (caseId: string) => {
    const c = cases.find((x) => x.case_id === caseId);
    return plainInsurer(c?.insurer_name || c?.insurer_id);
  };
  const changes = updates.filter((u) => u.affected_cases_count > 0 || !u.headline.endsWith("new_rule"));

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-8 py-8">
      <PageHeader
        title="Alerts"
        description="Saved claims affected by an insurer rule change. An alert is advice; it never denies or sends a claim."
      />

      <Card>
        <CardHeader
          title={`Open alerts (${open.length})`}
          description="Each one is a saved claim whose result changed because an insurer rule changed."
        />
        {open.length ? (
          <ul className="divide-y divide-line">
            {open.map((a) => (
              <li key={a.alert_id} className="flex flex-wrap items-center gap-4 px-6 py-4">
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs text-ink">{a.case_id}</span>
                    <span className="text-xs text-subtle">{insurerOf(a.case_id)}</span>
                    <StatusBadge tone={toneFromText(a.headline)}>{(a.headline || "").split(": ").pop()}</StatusBadge>
                  </div>
                  <p className="text-sm font-semibold text-ink">{(a.headline || "Rule change").split(": ")[0]}</p>
                  <p className="text-sm text-muted">{a.suggested_action || a.explanation}</p>
                  {a.rule_id && a.rule_id !== "NO_RULE" && (
                    <p className="text-xs text-subtle">
                      Rule <span className="font-mono">{a.rule_id}</span> · version {a.change?.to_version ?? "–"} · effective{" "}
                      {formatDate(a.effective_date)}
                    </p>
                  )}
                </div>
                <Button size="sm" icon={Eye} onClick={() => onSelect(a.case_id)}>
                  View claim
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="flex items-center gap-2 px-6 py-8 text-sm text-muted">
            <BellOff className="size-4 text-subtle" aria-hidden="true" />
            No open alerts. Saved claims are not affected by any recent rule change.
          </p>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Recent rule changes"
          description="Approved insurer rule changes and how many saved claims each one changed."
        />
        {changes.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-sunken text-xs font-semibold uppercase tracking-wide text-subtle">
                <tr>
                  <th className="px-6 py-3">Change</th>
                  <th className="px-3 py-3">Effective</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-6 py-3 text-right">Claims affected</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {changes.map((u) => {
                  const d = describeUpdate(u.headline);
                  const [tone, label] = UPDATE_STATUS[u.status] || ["unknown", u.status];
                  return (
                    <tr key={u.update_id} className="hover:bg-sunken">
                      <td className="px-6 py-3.5">
                        <p className="flex items-center gap-2 font-medium text-ink">
                          {d.item} {d.demo && <Tag>Demo</Tag>}
                        </p>
                        <p className="text-xs text-subtle">
                          {d.insurer}
                          {d.change ? ` · ${d.change}` : ""} · rule <span className="font-mono">{u.rule_id}</span> v{u.rule_version}
                        </p>
                      </td>
                      <td className="px-3 py-3.5 text-ink-2">{formatDate(u.effective_date)}</td>
                      <td className="px-3 py-3.5">
                        <StatusBadge tone={tone}>{label}</StatusBadge>
                      </td>
                      <td className="px-6 py-3.5 text-right">
                        {u.affected_cases_count > 0 ? (
                          <Button size="sm" variant="ghost" onClick={() => onViewAffectedCases(u.affected_case_ids)}>
                            Show {u.affected_cases_count} claim{u.affected_cases_count === 1 ? "" : "s"}
                            <ArrowRight className="size-3.5" aria-hidden="true" />
                          </Button>
                        ) : (
                          <span className="text-xs text-subtle">None</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="px-6 py-8 text-sm text-muted">No rule changes have affected saved claims yet.</p>
        )}
      </Card>

      {closed.length > 0 && (
        <Card>
          <details className="group">
            <summary className="flex cursor-pointer list-none items-center gap-2 px-6 py-4 text-sm font-semibold text-ink">
              <ChevronRight className="size-4 text-subtle transition-transform group-open:rotate-90" aria-hidden="true" />
              Closed alerts <span className="font-normal tabular-nums text-subtle">({closed.length})</span>
            </summary>
            <ul className="divide-y divide-line border-t border-line">
              {closed.map((a) => (
                <li key={a.alert_id} className="flex flex-wrap items-center gap-3 px-6 py-2.5 text-xs text-muted">
                  <span className="font-mono text-ink-2">{a.case_id}</span>
                  <span className="flex-1">{a.headline}</span>
                  <span>{a.closed_reason || a.status}</span>
                </li>
              ))}
            </ul>
          </details>
        </Card>
      )}
    </div>
  );
}
