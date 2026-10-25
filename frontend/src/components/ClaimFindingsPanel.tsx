import React from "react";
import clsx from "clsx";
import { ChevronRight, ExternalLink, History } from "lucide-react";
import { ClaimFindingsReport, PendingPolicyChange } from "../types";
import { Notice, Tag, TONE, type Tone } from "./ui";

// Plain-language view of a claim check: one verdict, one reason, one next step.
// Everything technical (versions, evidence, gaps) sits behind "Show details".

type Finding = ClaimFindingsReport["findings"][number];
export type VerdictTone = Tone;

const PENDING_GAP = /^Policy change detected /;
const NO_RULE = "No rule found, verify with the insurer";

export function timeAgo(iso?: string | null) {
  if (!iso) return "never";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} days ago`;
}

const formatDate = (value?: string | null) =>
  value
    ? new Date(value.length === 10 ? `${value}T00:00:00` : value).toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "unknown date";

function describeChange(change: PendingPolicyChange) {
  const effect = (change.proposed_effect || change.change_type || "change").replace(/_/g, " ");
  return `${effect}${change.effective_from ? ` from ${formatDate(change.effective_from)}` : ""}`;
}

// A first rule that is still waiting for approval is not a "change" to warn about.
const waitingForApproval = (finding: Finding) =>
  finding.result === NO_RULE && !!finding.pending_changes?.length;

/** One plain answer for the whole claim, worst problem first. */
export function claimVerdict(report: ClaimFindingsReport): { tone: Tone; title: string; reason: string; next: string } {
  const items = report.findings;
  const first = (result: string) => items.find((f) => f.result === result);
  const rejected = first("Not covered");
  if (rejected)
    return { tone: "rejected", title: "Will likely be rejected", reason: rejected.plain_sentence, next: rejected.follow_up || rejected.what_to_do };
  const action = first("Prior approval needed") || first("Document missing");
  if (action)
    return { tone: "action", title: "Needs action before sending", reason: action.plain_sentence, next: action.follow_up || action.what_to_do };
  const unclear = first("Value wrong");
  if (unclear)
    return { tone: "action", title: "Missing or unclear information", reason: unclear.plain_sentence, next: unclear.follow_up || unclear.what_to_do };
  const noRule = first(NO_RULE);
  if (noRule || !items.length)
    return {
      tone: "unknown",
      title: "Can't check yet",
      reason: noRule && waitingForApproval(noRule)
        ? "A rule for this was found and is waiting for approval."
        : "There is no approved rule on file for this insurer, plan and code.",
      next: noRule && waitingForApproval(noRule)
        ? "Approve the rule in Insurer rules, then check again."
        : "Check with the insurer before sending.",
    };
  return { tone: "ok", title: "No problems found", reason: "Every item matches the current approved rules.", next: "Review the rest of the claim as usual before sending." };
}

/** Rule changes the insurer published that would alter an existing, approved result. */
export const hasNewerRule = (report: ClaimFindingsReport) =>
  report.findings.some((f) => !!f.pending_changes?.length && !waitingForApproval(f));

function itemResult(finding: Finding): [Tone, string] {
  if (finding.result === "Covered") return ["ok", "OK"];
  if (finding.result === "Not covered") return ["rejected", "Not covered"];
  if (finding.result === "Value wrong") return ["action", "Missing info"];
  if (finding.result === "Document missing")
    return ["action", `Missing ${finding.missing_documents?.length ? finding.missing_documents.join(", ") : "documents"}`];
  if (finding.result === "Prior approval needed") return ["action", "Needs prior approval"];
  return ["unknown", waitingForApproval(finding) ? "Rule awaiting approval" : "No rule yet"];
}

export function ClaimFindingsPanel({ report }: { report: ClaimFindingsReport }) {
  const verdict = claimVerdict(report);
  const VerdictIcon = TONE[verdict.tone].icon;
  const gaps = [
    ...new Set([...(report.validation_warnings || []), ...report.coverage_gaps.filter((gap) => !PENDING_GAP.test(gap))]),
  ];
  return (
    <div className="space-y-3" aria-label="Claim check result">
      <div className={clsx("flex gap-3 rounded-xl border p-4", TONE[verdict.tone].panel)}>
        <VerdictIcon className={clsx("mt-0.5 size-5 shrink-0", TONE[verdict.tone].text)} aria-hidden="true" />
        <div className="space-y-1">
          <p className={clsx("text-base font-semibold", TONE[verdict.tone].text)}>{verdict.title}</p>
          <p className="text-sm text-ink-2">{verdict.reason}</p>
          <p className="text-sm text-ink-2">
            <span className="font-medium text-ink">Next step:</span> {verdict.next}
          </p>
        </div>
      </div>

      {hasNewerRule(report) && (
        <Notice tone="action">
          <span className="font-medium text-ink">The insurer changed this rule recently.</span> The change is waiting for
          approval, so this answer may change. Check again before sending.
        </Notice>
      )}

      <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
        {report.findings.map((finding, index) => {
          const [tone, label] = itemResult(finding);
          const Icon = TONE[tone].icon;
          return (
            <li key={index} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-ink">{finding.item.name || "Item"}</p>
                <p className="text-xs text-subtle">
                  <span className="font-mono">{finding.item.code || "no code"}</span>
                  {finding.item.code_system ? ` · ${finding.item.code_system}` : ""}
                  {finding.policy_reference && (
                    <>
                      {" · rule "}
                      <span className="font-mono">{finding.policy_reference}</span>
                    </>
                  )}
                </p>
              </div>
              <div className="flex items-center gap-3">
                {finding.source_url && (
                  <a
                    className="inline-flex items-center gap-1 text-xs font-medium text-brand hover:underline"
                    href={finding.source_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {finding.policy_is_synthetic ? "Demo source" : "Policy source"}
                    <ExternalLink className="size-3" aria-hidden="true" />
                  </a>
                )}
                <span className={clsx("inline-flex items-center gap-1.5 text-sm font-medium", TONE[tone].text)}>
                  <Icon className="size-4" aria-hidden="true" />
                  {label}
                </span>
              </div>
            </li>
          );
        })}
      </ul>

      <details className="group text-sm text-muted">
        <summary className="inline-flex cursor-pointer list-none items-center gap-1 font-medium text-brand hover:underline">
          <ChevronRight className="size-4 transition-transform group-open:rotate-90" aria-hidden="true" />
          Show details
        </summary>
        <div className="mt-3 space-y-3 rounded-xl border border-line bg-sunken p-4 text-xs">
          <p className="flex flex-wrap items-center gap-2">
            {report.policy_environment === "demo" ? <Tag>Demo rules</Tag> : <Tag tone="brand">Real insurer rules</Tag>}
            {report.insurer_name || report.insurer_id || "Insurer missing"} · plan {report.plan_id || "missing"} · state{" "}
            {report.jurisdiction || "missing"} · member {report.member_ref || "missing"} · service date {report.service_date || "missing"}
          </p>
          {gaps.map((message) => (
            <p className="text-warn" key={message}>{message}</p>
          ))}
          {report.findings.map((finding, index) => (
            <div key={index} className="space-y-1 rounded-lg border border-line bg-surface p-3">
              <p className="font-medium text-ink">
                {finding.item.name || finding.item.code} · <span className="font-mono">{finding.item.code}</span>
                {finding.item.code_system ? ` (${finding.item.code_system})` : ""}
              </p>
              <p>{finding.full_issue_text}</p>
              <p>
                Rule <span className="font-mono">{finding.policy_reference || "none matched"}</span> · version{" "}
                {finding.policy_version ?? "–"} · effective {finding.effective_date || "–"}
              </p>
              {finding.policy_reference && <p>Rule source last confirmed current: {timeAgo(finding.policy_checked_at)}</p>}
              {finding.policy_missing_reason && <p className="text-warn">{finding.policy_missing_reason}</p>}
              {finding.source_evidence && (
                <blockquote className="border-l-2 border-line-strong pl-3 italic text-ink-2">{finding.source_evidence}</blockquote>
              )}
              <p>
                Required documents: {finding.required_documents.join(", ") || (finding.policy_reference ? "none" : "unknown")} · prior
                authorization: {finding.policy_reference ? (finding.requires_prior_authorization ? "required" : "not required by this rule") : "unknown"}
                {finding.prior_authorization_present ? ` (reference ${finding.prior_authorization_reference} given, not validated)` : ""}
              </p>
              {finding.pending_changes?.map((change) => (
                <div key={change.proposal_id} className="flex gap-2 rounded-md border border-warn-line bg-warn-soft p-2 text-ink-2">
                  <History className="mt-0.5 size-3.5 shrink-0 text-warn" aria-hidden="true" />
                  <div>
                    <p className="font-medium text-ink">
                      Pending change{change.policy_reference ? ` to ${change.policy_reference}` : ""}: {describeChange(change)}
                    </p>
                    <p>Detected {formatDate(change.detected_at)} · not yet approved{change.is_synthetic ? " · demo" : ""}</p>
                    {change.supporting_quote && <blockquote className="italic">{change.supporting_quote}</blockquote>}
                  </div>
                </div>
              ))}
            </div>
          ))}
          <p className="text-subtle">{report.notice}</p>
        </div>
      </details>
    </div>
  );
}
