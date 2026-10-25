import React from "react";
import { ClaimFindingsReport } from "../types";

export function ClaimFindingsPanel({
  report,
}: {
  report: ClaimFindingsReport;
}) {
  return (
    <div className="space-y-3 text-xs" aria-label="Pre-submission findings">
      <div
        className={`p-3 rounded-xl border ${report.policy_environment === "demo" ? "bg-purple-50 border-purple-200" : "bg-[#EBF4EE] border-[#D5E2D9]"}`}
      >
        <p className="font-bold">
          {report.policy_environment === "demo"
            ? "DEMO / SIMULATED policies — fictional insurer rules"
            : "OFFICIAL / VERIFIED policies — approved applicable evidence required"}
        </p>
        <p className="mt-1 font-bold">{report.status}</p>
        <p>
          {report.insurer_name || report.insurer_id || "Insurer missing"} ·
          Plan: {report.plan_id || "missing"} · State:{" "}
          {report.jurisdiction || "missing"}
        </p>
        <p>
          Member: {report.member_ref || "missing"} · Service date:{" "}
          {report.service_date || "missing"}
        </p>
      </div>
      <p className="text-[#698579]">{report.notice}</p>
      {[
        ...new Set([
          ...(report.validation_warnings || []),
          ...report.coverage_gaps,
        ]),
      ].map((message) => (
        <p className="text-amber-900" key={message}>
          {message}
        </p>
      ))}
      {report.findings.map((finding, index) => (
        <article
          key={index}
          className="p-3.5 rounded-xl border border-[#D5E2D9] bg-[#FAFBFB] space-y-2"
        >
          <p className="font-bold text-sm">
            {finding.item.name || finding.item.code} ·{" "}
            {finding.item.code || "Code missing"}
            {finding.item.code_system ? ` (${finding.item.code_system})` : ""}
          </p>
          <p className="font-bold">
            {finding.result === "Covered"
              ? "No issue detected under this checked rule"
              : finding.result === "Value wrong"
                ? "Information requires correction or review"
                : finding.result}
          </p>
          <p>{finding.full_issue_text}</p>
          <p>
            Policy:{" "}
            {finding.policy_reference ||
              "No verified applicable policy matched"}{" "}
            · Version: {finding.policy_version ?? "unavailable"} · Effective:{" "}
            {finding.effective_date || "unavailable"}{" "}
            {finding.policy_is_synthetic ? "· SIMULATED" : ""}
          </p>
          {finding.policy_missing_reason && (
            <p className="text-amber-900">{finding.policy_missing_reason}</p>
          )}
          <blockquote className="text-[#698579]">
            {finding.source_evidence ||
              "Supporting policy evidence is unavailable."}
          </blockquote>
          {finding.source_url && (
            <a
              className="text-[#2A835F] underline"
              href={finding.source_url}
              target="_blank"
              rel="noreferrer"
            >
              {finding.policy_is_synthetic
                ? "Simulated policy source"
                : "Policy source"}
            </a>
          )}
          <p>
            Required documents:{" "}
            {finding.required_documents.join(", ") ||
              (finding.policy_reference
                ? "None specified by this checked rule"
                : "Unverified")}
          </p>
          {!!finding.missing_documents?.length && (
            <p className="text-amber-900">
              Missing documents: {finding.missing_documents.join(", ")}
            </p>
          )}
          <p>
            Prior authorization required:{" "}
            {finding.policy_reference
              ? finding.requires_prior_authorization
                ? "Yes"
                : "Not specified by this checked rule"
              : "Unverified"}
            . Reference:{" "}
            {finding.prior_authorization_present
              ? `${finding.prior_authorization_reference} (provided; not validated with insurer)`
              : "Not supplied"}
            .
          </p>
          <p className="font-medium">Follow-up: {finding.follow_up}</p>
        </article>
      ))}
    </div>
  );
}
