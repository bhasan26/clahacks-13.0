import React, { useEffect, useState } from "react";
import { workflowRequest } from "../api";
const field = "w-full border border-[#D8E5DC] rounded-xl p-2 text-xs";
const button =
  "px-4 py-2 rounded-xl bg-[#092328] text-white text-xs font-bold disabled:opacity-50 cursor-pointer";
export function ClaimsWorkspace({
  onSelect,
  onClinicalUpload,
  onChanged,
  initialStatusFilter = "All",
  initialSpecialtyFilter = "All",
  caseIds = [],
}: {
  onSelect: (id: string) => void;
  onClinicalUpload: () => void;
  onChanged: () => void;
  initialStatusFilter?: string;
  initialSpecialtyFilter?: string;
  caseIds?: string[];
}) {
  const [statusFilter, setStatusFilter] = useState(initialStatusFilter),
    [specialtyFilter, setSpecialtyFilter] = useState(initialSpecialtyFilter),
    [insurerFilter, setInsurerFilter] = useState("All");
  const [reports, setReports] = useState<any[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [selected, setSelected] = useState<any>(null);
  const [form, setForm] = useState({
    insurer_id: "uhc",
    plan_id: "",
    jurisdiction: "CA",
    code: "27447",
    code_system: "CPT",
    name: "Total knee arthroplasty",
    member_ref: "",
    service_date: "2026-11-10",
    demo: false,
    documents: "",
    prior_approval_ref: "",
  });
  const load = async () =>
    setReports(await workflowRequest("/claims/findings"));
  useEffect(() => {
    load().catch((e) => setError(e.message));
    const timer = setInterval(() => load().catch(() => {}), 5000);
    return () => clearInterval(timer);
  }, []);
  const action = async (fn: () => Promise<any>) => {
    setBusy(true);
    setError("");
    try {
      const result = await fn();
      await load();
      onChanged();
      if (result.findings?.length) setSelected(result.findings[0]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const shown = reports.filter(
    (r) =>
      (statusFilter === "All" || r.engine_status === statusFilter) &&
      (specialtyFilter === "All" || r.specialty === specialtyFilter) &&
      (insurerFilter === "All" || r.insurer_id === insurerFilter) &&
      (!caseIds.length || caseIds.includes(r.case_id)),
  );
  const set = (key: string, value: any) => setForm({ ...form, [key]: value });
  const uploadJSON = async (file?: File) => {
    if (!file) return;
    if (file.size > 1024 * 1024) {
      setError("Claim JSON exceeds 1 MB.");
      return;
    }
    try {
      const data = JSON.parse(await file.text());
      await action(() =>
        workflowRequest("/claims/import", { claims: data.claims || [data] }),
      );
    } catch (e: any) {
      setError(e.message);
    }
  };
  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-5">
      <div className="flex justify-between">
        <div>
          <h1 className="text-xl font-black">Claims</h1>
          <p className="text-xs text-[#698579]">
            Pre-submission findings for hospital employees. No claims are
            approved, rejected, changed or submitted by CoverageGuard.
          </p>
        </div>
        <button className={button} onClick={onClinicalUpload}>
          Local clinical file / card intake
        </button>
      </div>
      {error && (
        <p role="alert" className="bg-amber-50 p-3 rounded-xl text-xs">
          {error}
        </p>
      )}
      <section className="border border-[#D8E5DC] rounded-2xl p-5 space-y-4">
        <h2 className="font-bold">Upload or enter a synthetic pending claim</h2>
        <p className="text-xs">
          Missing insurer, plan, region, codes or policy evidence remains unable
          to verify. Clinical files are processed locally. Public policy
          requests never include patient/member identifiers or clinical notes.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <label className="text-xs">
            Insurer
            <select
              className={field}
              value={form.insurer_id}
              onChange={(e) => set("insurer_id", e.target.value)}
            >
              <option value="uhc">UnitedHealthcare</option>
              <option value="aetna">Aetna</option>
              <option value="bcbs-anthem-ca">Anthem Blue Cross — CA</option>
              <option value="bcbs">BCBS — affiliate unknown</option>
              <option value="cms">Original Medicare</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          {[
            ["plan_id", "Exact plan ID"],
            ["jurisdiction", "State / jurisdiction"],
            ["member_ref", "Synthetic member reference"],
            ["code", "Billing code"],
            ["code_system", "Code system"],
            ["name", "Procedure / medication"],
            ["service_date", "Service date"],
            ["documents", "Attached documents (comma separated)"],
            ["prior_approval_ref", "Prior authorization reference"],
          ].map(([key, label]) => (
            <label key={key} className="text-xs">
              {label}
              <input
                aria-label={label}
                type={key === "service_date" ? "date" : "text"}
                className={field}
                value={(form as any)[key]}
                onChange={(e) => set(key, e.target.value)}
              />
            </label>
          ))}
        </div>
        <label className="flex gap-2 text-xs">
          <input
            type="checkbox"
            checked={form.demo}
            onChange={(e) => set("demo", e.target.checked)}
          />
          Use SIMULATED insurer rules for this synthetic claim (requires exact
          DEMO plan)
        </label>
        <div className="flex flex-wrap gap-3 items-center">
          <button
            className={button}
            disabled={busy}
            onClick={() =>
              action(() =>
                workflowRequest("/claims/import", {
                  claims: [
                    {
                      case_id: `UPLOAD-${crypto.randomUUID()}`,
                      insurer_id: form.insurer_id,
                      plan_id: form.plan_id,
                      jurisdiction: form.jurisdiction,
                      member_ref: form.member_ref,
                      service_date: form.service_date || null,
                      policy_environment: form.demo ? "demo" : "official",
                      is_synthetic: true,
                      items: [
                        {
                          type:
                            form.code_system === "CPT" ? "procedure" : "drug",
                          code: form.code,
                          code_system: form.code_system,
                          name: form.name,
                        },
                      ],
                      documents: form.documents
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean),
                      prior_approval_ref: form.prior_approval_ref || null,
                    },
                  ],
                }),
              )
            }
          >
            Import and verify synthetic claim
          </button>
          <label className="text-xs">
            Import synthetic JSON file
            <input
              aria-label="Import synthetic claim JSON"
              className="block"
              type="file"
              accept="application/json,.json"
              onChange={(e) => uploadJSON(e.target.files?.[0])}
            />
          </label>
        </div>
      </section>
      <section className="border border-[#D8E5DC] rounded-2xl p-5 overflow-auto">
        <h2 className="font-bold mb-3">Pending claims ({reports.length})</h2>
        <div className="flex gap-3 mb-3 text-xs">
          <label>
            Status
            <select
              aria-label="Filter claims by status"
              className={field}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              {[
                ["All", "All findings"],
                ["Approved", "No checked issue"],
                ["Needs attention", "Needs attention"],
                ["Missing or wrong info", "Unable to verify / missing info"],
              ].map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label>
            Insurer
            <select
              aria-label="Filter claims by insurer"
              className={field}
              value={insurerFilter}
              onChange={(e) => setInsurerFilter(e.target.value)}
            >
              {["All", ...new Set(reports.map((r) => r.insurer_id))].map(
                (v) => (
                  <option key={v}>{v}</option>
                ),
              )}
            </select>
          </label>
          <label>
            Specialty
            <select
              aria-label="Filter claims by specialty"
              className={field}
              value={specialtyFilter}
              onChange={(e) => setSpecialtyFilter(e.target.value)}
            >
              {["All", ...new Set(reports.map((r) => r.specialty))].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
        </div>
        <table className="w-full text-xs text-left">
          <thead>
            <tr>
              <th>Claim</th>
              <th>Insurer / plan</th>
              <th>Requested items</th>
              <th>Verification findings</th>
              <th>Follow-up</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.case_id} className="border-t border-[#D8E5DC]">
                <td className="py-3">
                  <button className="underline" onClick={() => setSelected(r)}>
                    {r.case_id}
                  </button>
                  <br />
                  {r.policy_environment === "demo"
                    ? "SIMULATED policies"
                    : "Official policy evidence"}
                </td>
                <td>
                  {r.insurer_name || r.insurer_id || "Unknown insurer"}
                  <br />
                  {r.plan_id || "Plan unknown"} ·{" "}
                  {r.jurisdiction || "Region unknown"}
                </td>
                <td>{r.findings.map((f: any) => f.item.code).join(", ")}</td>
                <td>
                  {r.status}
                  <br />
                  {r.issues_count} issue(s)
                </td>
                <td>
                  <button
                    className="underline"
                    disabled={busy}
                    onClick={() =>
                      action(() =>
                        workflowRequest("/policy-sync/run", {
                          claim_id: r.case_id,
                        }),
                      )
                    }
                  >
                    Targeted source refresh
                  </button>
                  <br />
                  <button
                    className="underline"
                    onClick={() => onSelect(r.case_id)}
                  >
                    Open record / actions
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!reports.length && (
          <p className="text-xs py-4">
            No pending claims. Import a synthetic file or the independent
            hospital simulator.
          </p>
        )}
      </section>
      {selected && (
        <section className="border border-[#D8E5DC] rounded-2xl p-5 space-y-3">
          <div className="flex justify-between">
            <h2 className="font-bold">Findings: {selected.case_id}</h2>
            <button onClick={() => setSelected(null)}>Close</button>
          </div>
          <p className="text-sm font-bold">{selected.status}</p>
          <p className="text-xs">{selected.notice}</p>
          {selected.coverage_gaps.map((g: string) => (
            <p className="text-xs text-amber-900" key={g}>
              {g}
            </p>
          ))}
          {selected.findings.map((f: any, i: number) => (
            <div key={i} className="border-t pt-3 text-xs space-y-1">
              <strong>
                {f.item.name || f.item.code} · {f.result}
              </strong>
              <p>
                {f.policy_reference || "No verified policy"} · version{" "}
                {f.policy_version ?? "unknown"} · effective{" "}
                {f.effective_date || "unknown"}{" "}
                {f.policy_is_synthetic ? "· SIMULATED" : ""}
              </p>
              <blockquote>
                {f.source_evidence || "Source evidence is unavailable."}
              </blockquote>
              {f.source_url && (
                <a
                  className="underline text-[#2A835F]"
                  href={f.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Policy source
                </a>
              )}
              <p>
                Required documents:{" "}
                {f.required_documents.join(", ") ||
                  "No verified document requirement found"}
              </p>
              <p>Follow-up: {f.follow_up}</p>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
