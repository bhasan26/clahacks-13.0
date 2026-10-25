import React, { useEffect, useRef, useState } from "react";
import { analyzeIntake, uploadPatientFile } from "../api";
import { IntakeAnalysisResult, ReviewedIntakeClaim, RulesRefreshResult } from "../types";
import clsx from "clsx";
import { CheckCircle2, ChevronRight, Loader2, Plus, RefreshCw, RotateCcw, Save, UploadCloud, X } from "lucide-react";
import { ClaimFindingsPanel, timeAgo } from "./ClaimFindingsPanel";
import { Button, Card, CardHeader, Field, Notice, Tag, fieldClass } from "./ui";

// One intake flow: drop a file or paste text → fields fill in → findings
// re-check as you edit → save. The policy environment follows the plan ID
// (DEMO-* plans use simulated rules), so there is nothing to pick by hand.
// Reading a file and "Check latest insurer rules" first re-check the insurer
// sources for this claim, so a rule changed this week is caught before filing.

const INSURERS: Array<[string, string]> = [
  ["", "Select insurer"],
  ["uhc", "UnitedHealthcare"],
  ["aetna", "Aetna"],
  ["bcbs-anthem-ca", "Anthem Blue Cross — CA"],
  ["bcbs", "BCBS — affiliate unknown"],
  ["cms", "Original Medicare"],
];
const CODE_SYSTEMS = ["", "CPT", "HCPCS", "NDC"];
const blankItem = { type: "procedure", code: "", name: "", code_system: "", quantity: 1 };
const blank: ReviewedIntakeClaim = {
  insurer_id: "",
  insurer_name: "",
  plan_id: "",
  member_ref: "",
  group_number: "",
  jurisdiction: "",
  service_date: "",
  specialty: "",
  prior_approval_ref: "",
  diagnosis_code: "",
  diagnosis_desc: "",
  documents: [],
  items: [{ ...blankItem }],
};

const readFile = (file: File): Promise<string> => {
  if (file.size > 10 * 1024 * 1024)
    return Promise.reject(new Error("File exceeds the 10 MB limit."));
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Unable to read file. Choose it again."));
    reader.readAsDataURL(file);
  });
};

// The analyzed claim carries diagnoses as a list; the form edits the primary one.
type AnalyzedClaim = Partial<ReviewedIntakeClaim> & { diagnoses?: Array<{ code: string; description?: string | null }> };

const normalize = (claim: AnalyzedClaim): ReviewedIntakeClaim => {
  const { diagnoses, ...fields } = claim;
  const next = { ...blank, ...fields } as ReviewedIntakeClaim;
  for (const key of Object.keys(blank) as Array<keyof ReviewedIntakeClaim>) {
    if (next[key] == null) Object.assign(next, { [key]: blank[key] });
  }
  if (diagnoses?.length && !next.diagnosis_code) {
    next.diagnosis_code = diagnoses[0].code;
    next.diagnosis_desc = diagnoses[0].description || "";
  }
  next.items = (next.items.length ? next.items : [{ ...blankItem }]).map((item) => ({
    ...item,
    name: item.name || "",
    code_system: item.code_system || "",
  }));
  return next;
};

function describeRefresh(row: RulesRefreshResult) {
  switch (row.status) {
    case "succeeded":
    case "partial":
      return `${row.name}: checked just now — ${row.changed ? `${row.changed} new or changed rule(s) found` : "no changes"}`;
    case "recently_checked":
      return `${row.name}: checked ${timeAgo(row.checked_at)} (official sources are re-checked at most every 10 min)`;
    case "authorization_required":
      return `${row.name}: this insurer doesn't allow automatic checks, so the latest rules can't be confirmed`;
    case "already_running":
      return `${row.name}: a scheduled check is running; results appear shortly`;
    default:
      return `${row.name}: check failed${row.error ? ` — ${row.error}` : ""}`;
  }
}

const MISSING_LABELS: Record<string, string> = {
  insurer_id: "Insurance company",
  plan_id: "Plan ID",
  member_ref: "Member ID",
  jurisdiction: "State",
  service_date: "Date of service",
  items: "Procedure / medicine",
  "items.code": "Code",
  "items.code_system": "Code type",
  "items.type": "Kind of item",
};

// The code's format identifies its system (CPT: 5 digits or 4 digits + F/T; HCPCS: letter + 4 digits).
// This never guesses a code from a procedure name.
const inferCodeSystem = (code: string) => {
  const clean = code.trim().toUpperCase();
  if (/^\d{5}$/.test(clean) || /^\d{4}[FT]$/.test(clean)) return "CPT";
  if (/^[A-V]\d{4}$/.test(clean)) return "HCPCS";
  return "";
};

const hasContent = (claim: ReviewedIntakeClaim) =>
  !!(claim.insurer_id || claim.plan_id || claim.member_ref || claim.items.some((i) => i.code));

export function ClaimIntake({ onSaved }: { onSaved: (caseId: string, updated: boolean) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<ReviewedIntakeClaim>(blank);
  const [result, setResult] = useState<IntakeAnalysisResult | null>(null);
  const [editVersion, setEditVersion] = useState(0);
  const [checkedVersion, setCheckedVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refresh, setRefresh] = useState<RulesRefreshResult[] | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const draftRef = useRef(draft);
  const requestRef = useRef(0);
  draftRef.current = draft;

  // Only the newest request may update the screen.
  const run = async (data: Parameters<typeof analyzeIntake>[0], version: number, replaceDraft: boolean) => {
    const request = ++requestRef.current;
    setBusy(true);
    setRefreshing(!!data.refresh_sources);
    setError("");
    try {
      const response = await analyzeIntake(data);
      if (request !== requestRef.current) return;
      if (replaceDraft) setDraft(normalize(response.claim));
      // A backend without source refresh omits the field; show nothing rather than "no source".
      if (data.refresh_sources) setRefresh(response.rules_refresh ?? null);
      setResult(response);
      setCheckedVersion(version);
    } catch (exception: any) {
      if (request === requestRef.current)
        setError(exception.message || "Local extraction failed. Enter the claim details below.");
    } finally {
      if (request === requestRef.current) {
        setBusy(false);
        setRefreshing(false);
      }
    }
  };
  const checkLatest = () => run({ reviewed_claim: draftRef.current, refresh_sources: true }, editVersion, false);

  const extract = async (source: File | null, pasted: string) => {
    if (!source && !pasted.trim()) return;
    try {
      const encoded = source ? await readFile(source) : undefined;
      await run({ clinical_doc_b64: encoded, clinical_text: pasted, refresh_sources: true }, editVersion, true);
    } catch (exception: any) {
      setError(exception.message);
    }
  };

  // Pasted text is read shortly after typing stops.
  useEffect(() => {
    if (!text.trim()) return;
    const timer = setTimeout(() => extract(file, text), 700);
    return () => clearTimeout(timer);
  }, [text]);

  // Field edits re-check findings automatically; no recheck button.
  useEffect(() => {
    if (editVersion === 0) return;
    const timer = setTimeout(() => {
      if (hasContent(draftRef.current))
        run({ reviewed_claim: draftRef.current }, editVersion, false);
    }, 500);
    return () => clearTimeout(timer);
  }, [editVersion]);

  const chooseFile = (chosen: File | null) => {
    setFile(chosen);
    if (chosen) extract(chosen, text);
  };
  const setField = (key: keyof ReviewedIntakeClaim, value: unknown) => {
    setDraft((previous) => ({
      ...previous,
      [key]: value,
      // A stale display name would contradict a newly chosen insurer.
      ...(key === "insurer_id" ? { insurer_name: "" } : {}),
    }));
    setEditVersion((version) => version + 1);
  };
  const setItem = (index: number, key: string, value: string) =>
    setField(
      "items",
      draft.items.map((item, row) => {
        if (row !== index) return item;
        const next = { ...item, [key]: value };
        // Keep the code type in step with the code unless someone chose it by hand.
        if (key === "code" && (!item.code_system || item.code_system === inferCodeSystem(item.code)))
          next.code_system = inferCodeSystem(value);
        return next;
      }),
    );
  const reset = () => {
    requestRef.current++;
    setFile(null);
    setText("");
    setDraft(blank);
    setResult(null);
    setEditVersion(0);
    setCheckedVersion(0);
    setBusy(false);
    setRefreshing(false);
    setRefresh(null);
    setError("");
  };
  const save = async () => {
    setBusy(true);
    setError("");
    try {
      const saved = await uploadPatientFile({
        ...draft,
        specialty: draft.specialty || "Unspecified",
        policy_environment: "auto",
      });
      reset();
      onSaved(saved.case.case_id, saved.updated);
    } catch (exception: any) {
      setError(exception.message || "Unable to save claim.");
      setBusy(false);
    }
  };

  const pending = editVersion !== checkedVersion;
  const missing = new Set((result?.missing_fields || []).map((row) => row.field));
  const invalid = (field: string) => !!result && missing.has(field);
  const canSave = !!result && !busy && !pending && !result.missing_fields.length;
  const environment = result?.policy_environment;
  const insurerOptions = INSURERS.some(([id]) => id === draft.insurer_id)
    ? INSURERS
    : [...INSURERS, [draft.insurer_id, draft.insurer_name || draft.insurer_id] as [string, string]];
  const missingLabels = [...new Set((result?.missing_fields || []).map((row) => MISSING_LABELS[row.field.replace(/^items\.\d+\./, "items.")] || "Item details"))];
  // Open "More details" when something required is hidden inside it.
  const hiddenMissing = [...missing].some((field) => /code_system|type/.test(field));

  const field = (key: keyof ReviewedIntakeClaim, label: string, type = "text") => (
    <Field label={label} key={key}>
      <input
        aria-label={label}
        type={type}
        className={fieldClass(invalid(key))}
        value={String(draft[key] || "")}
        onChange={(event) => setField(key, event.target.value)}
      />
    </Field>
  );
  const step = (n: number, title: string) => (
    <p className="flex items-center gap-2 text-sm font-medium text-ink">
      <span className="flex size-5 items-center justify-center rounded-full bg-brand-soft text-xs font-semibold text-brand">{n}</span>
      {title}
    </p>
  );

  return (
    <Card>
      <CardHeader
        title="Check a claim"
        description="Upload the claim, confirm the details, and see whether the insurer's current rules allow it."
        actions={
          (result || file || text) && (
            <Button size="sm" variant="ghost" icon={RotateCcw} onClick={reset} disabled={busy}>
              Start over
            </Button>
          )
        }
      />
      <div className="space-y-6 p-5">
        <div className="space-y-3">
          {step(1, "Add the claim")}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                chooseFile(event.dataTransfer.files?.[0] || null);
              }}
              className={clsx(
                "flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-xl border border-dashed p-5 text-center transition-colors duration-150",
                dragging ? "border-brand bg-brand-soft" : "border-line-strong bg-sunken hover:border-brand hover:bg-brand-soft/50",
              )}
            >
              <UploadCloud className="size-6 text-brand" aria-hidden="true" />
              <span className="text-sm font-medium text-ink">{file ? file.name : "Drop a PDF or text file"}</span>
              <span className="text-xs text-subtle">{file ? "Click to choose another file" : "or click to browse · read on this computer only"}</span>
              <input
                aria-label="Claim file upload"
                type="file"
                className="sr-only"
                accept="application/pdf,text/plain,image/png,image/jpeg,image/webp,.txt"
                onChange={(event) => {
                  chooseFile(event.target.files?.[0] || null);
                  event.target.value = "";
                }}
              />
            </label>
            <textarea
              aria-label="Paste claim details"
              value={text}
              onChange={(event) => setText(event.target.value)}
              className={clsx(fieldClass(), "h-auto min-h-28 py-2 font-mono text-xs")}
              placeholder={"…or paste the claim text here\nInsurance Company: …\nPlan ID: …\nCPT Code: …"}
            />
          </div>
        </div>

        {error && <Notice tone="rejected">{error}</Notice>}

        <div className="space-y-3">
          {step(2, "Confirm the details")}
          <div className="grid grid-cols-2 gap-x-4 gap-y-3 md:grid-cols-4">
            <Field label="Insurance company">
              <select
                aria-label="Insurer"
                className={fieldClass(invalid("insurer_id"))}
                value={draft.insurer_id}
                onChange={(event) => setField("insurer_id", event.target.value)}
              >
                {insurerOptions.map(([id, name]) => (
                  <option key={id} value={id}>
                    {name}
                  </option>
                ))}
              </select>
            </Field>
            {field("plan_id", "Plan ID")}
            {field("member_ref", "Member ID")}
            {field("jurisdiction", "State")}
            {field("service_date", "Date of service", "date")}
            {field("diagnosis_code", "Diagnosis code (ICD-10)")}
            {draft.items.map((item, index) => (
              <React.Fragment key={index}>
                <Field label={draft.items.length > 1 ? `Procedure / medicine ${index + 1}` : "Procedure / medicine"}>
                  <input
                    aria-label={`Item ${index + 1} name`}
                    className={fieldClass()}
                    value={item.name || ""}
                    onChange={(event) => setItem(index, "name", event.target.value)}
                  />
                </Field>
                <Field label="Code (CPT / HCPCS)">
                  <input
                    aria-label={`Item ${index + 1} billing code`}
                    className={clsx(fieldClass(invalid(`items.${index}.code`)), "font-mono")}
                    value={item.code}
                    onChange={(event) => setItem(index, "code", event.target.value)}
                  />
                </Field>
              </React.Fragment>
            ))}
          </div>

          <details open={hiddenMissing || undefined} className="group">
            <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-sm font-medium text-brand hover:underline">
              <ChevronRight className="size-4 transition-transform group-open:rotate-90" aria-hidden="true" />
              More details (optional)
            </summary>
            <div className="mt-3 space-y-3 rounded-xl border border-line bg-sunken p-4">
              <div className="grid grid-cols-2 gap-x-4 gap-y-3 md:grid-cols-4">
                {field("prior_approval_ref", "Prior authorization number")}
                <Field label="Attached documents (comma separated)">
                  <input
                    aria-label="Attached documents"
                    className={fieldClass()}
                    value={draft.documents.join(", ")}
                    onChange={(event) =>
                      setField(
                        "documents",
                        event.target.value
                          .split(",")
                          .map((value) => value.trim())
                          .filter(Boolean),
                      )
                    }
                  />
                </Field>
                {field("diagnosis_desc", "Diagnosis description")}
                {field("group_number", "Group number")}
                {field("specialty", "Specialty")}
              </div>
              {draft.items.map((item, index) => (
                <div key={index} className="grid grid-cols-2 items-end gap-x-4 gap-y-3 md:grid-cols-4">
                  <Field label={`Code type${draft.items.length > 1 ? ` (item ${index + 1})` : ""}`}>
                    <select
                      aria-label={`Item ${index + 1} code system`}
                      className={fieldClass(invalid(`items.${index}.code_system`))}
                      value={item.code_system || ""}
                      onChange={(event) => setItem(index, "code_system", event.target.value)}
                    >
                      {[...new Set([...CODE_SYSTEMS, item.code_system || ""])].map((system) => (
                        <option key={system} value={system}>
                          {system || "Select"}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Kind of item">
                    <select
                      aria-label={`Item ${index + 1} type`}
                      className={fieldClass()}
                      value={item.type}
                      onChange={(event) => setItem(index, "type", event.target.value)}
                    >
                      <option value="procedure">Procedure</option>
                      <option value="drug">Medicine</option>
                      <option value="service">Service</option>
                    </select>
                  </Field>
                  {draft.items.length > 1 && (
                    <Button
                      size="sm"
                      variant="ghost"
                      icon={X}
                      onClick={() => setField("items", draft.items.filter((_, row) => row !== index))}
                    >
                      Remove item {index + 1}
                    </Button>
                  )}
                </div>
              ))}
              <Button size="sm" variant="ghost" icon={Plus} onClick={() => setField("items", [...draft.items, { ...blankItem }])}>
                Add another procedure or medicine
              </Button>
            </div>
          </details>
        </div>

        {result && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              {step(3, "Result")}
              {environment === "demo" ? <Tag>Demo rules</Tag> : <Tag tone="brand">Real insurer rules</Tag>}
              <span className="inline-flex items-center gap-1 text-xs text-subtle">
                {busy || pending ? (
                  <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="size-3.5 text-ok" aria-hidden="true" />
                )}
                {refreshing ? "Getting the latest insurer rules…" : busy || pending ? "Checking…" : "Up to date"}
              </span>
              <Button size="sm" variant="ghost" icon={RefreshCw} className="ml-auto" disabled={busy || pending} onClick={checkLatest}>
                Check latest insurer rules
              </Button>
            </div>
            {refresh && (
              <ul className="space-y-0.5 text-xs text-muted" aria-label="Insurer rule check">
                {refresh.length ? (
                  refresh.map((row) => <li key={row.source_id}>{describeRefresh(row)}</li>)
                ) : (
                  <li>No rule source is connected for this insurer, so the latest rules can't be confirmed.</li>
                )}
              </ul>
            )}
            {!!missingLabels.length && (
              <Notice tone="action">Please fill in the highlighted fields: {missingLabels.join(", ")}.</Notice>
            )}
            <div className={clsx("transition-opacity", (busy || pending) && "opacity-50")}>
              <ClaimFindingsPanel report={result.findings} />
            </div>
          </div>
        )}
      </div>
      <div className="flex items-center justify-between gap-3 border-t border-line bg-sunken px-5 py-3">
        <p className="text-xs text-subtle">Saved claims are re-checked automatically when insurer rules change.</p>
        <Button variant="primary" icon={Save} disabled={!canSave} loading={busy && !pending && !!result} onClick={save}>
          Save claim
        </Button>
      </div>
    </Card>
  );
}
