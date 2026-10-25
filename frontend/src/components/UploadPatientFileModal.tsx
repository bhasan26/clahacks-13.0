import React, { useState } from "react";
import { analyzeIntake, uploadPatientFile } from "../api";
import { Case, IntakeAnalysisResult, ReviewedIntakeClaim } from "../types";
import { ClaimFindingsPanel } from "./ClaimFindingsPanel";

interface UploadPatientFileModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCaseCreated: (newCase: Case) => void;
}
const input =
  "w-full px-3 py-2 text-xs rounded-lg border border-[#D5E2D9] bg-white text-[#092328] focus:outline-none focus:border-[#2A835F]";
const button =
  "px-4 py-2.5 rounded-xl bg-[#2A835F] text-white text-xs font-bold hover:bg-[#1F6347] disabled:opacity-50 cursor-pointer";
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
  items: [],
};

export const UploadPatientFileModal: React.FC<UploadPatientFileModalProps> = ({
  isOpen,
  onClose,
  onCaseCreated,
}) => {
  const [environment, setEnvironment] = useState<"official" | "demo">(
    "official",
  );
  const [cardFile, setCardFile] = useState<File | null>(null),
    [clinicalFile, setClinicalFile] = useState<File | null>(null);
  const [cardText, setCardText] = useState(""),
    [clinicalText, setClinicalText] = useState("");
  const [result, setResult] = useState<IntakeAnalysisResult | null>(null),
    [draft, setDraft] = useState<ReviewedIntakeClaim>(blank);
  const [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  if (!isOpen) return null;

  const invalidate = () => {
    setDirty(true);
    setResult(null);
    setError("");
  };
  const setField = (key: keyof ReviewedIntakeClaim, value: unknown) => {
    setDraft((previous) => ({ ...previous, [key]: value }));
    setDirty(true);
  };
  const readFile = (file: File | null): Promise<string | undefined> => {
    if (!file) return Promise.resolve(undefined);
    if (file.size > 10 * 1024 * 1024)
      return Promise.reject(new Error("File exceeds the 10 MB limit."));
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () =>
        reject(new Error("Unable to read file. Choose it again."));
      reader.readAsDataURL(file);
    });
  };
  const analyze = async (reviewed = false) => {
    setBusy(true);
    setError("");
    try {
      const data = reviewed
        ? { policy_environment: environment, reviewed_claim: draft }
        : {
            policy_environment: environment,
            clinical_doc_b64: await readFile(clinicalFile),
            card_image_b64: await readFile(cardFile),
            clinical_text: clinicalText,
            card_text: cardText,
          };
      const response = await analyzeIntake(data);
      const normalized = { ...blank, ...response.claim };
      for (const key of Object.keys(blank) as Array<
        keyof ReviewedIntakeClaim
      >) {
        if (normalized[key] == null)
          Object.assign(normalized, { [key]: blank[key] });
      }
      setDraft(normalized);
      setResult(response);
      setDirty(false);
    } catch (exception: any) {
      setError(
        exception.message ||
          "Local extraction failed. Correct or paste the claim details.",
      );
    } finally {
      setBusy(false);
    }
  };
  const fileCase = async () => {
    if (!result || dirty || result.missing_fields.length) return;
    setBusy(true);
    setError("");
    try {
      const saved = await uploadPatientFile({
        ...draft,
        specialty: draft.specialty || "Unspecified",
        policy_environment: environment,
        items: draft.items,
      });
      onCaseCreated(saved.case);
      setResult(null);
      setDraft(blank);
      setCardFile(null);
      setClinicalFile(null);
      setCardText("");
      setClinicalText("");
      setEnvironment("official");
      onClose();
    } catch (exception: any) {
      setError(exception.message || "Unable to file claim.");
    } finally {
      setBusy(false);
    }
  };
  const fields: Array<[keyof ReviewedIntakeClaim, string, string?]> = [
    ["insurer_id", "Insurer ID"],
    ["insurer_name", "Insurer name"],
    ["plan_id", "Exact plan ID"],
    ["member_ref", "Member ID"],
    ["jurisdiction", "State / jurisdiction"],
    ["service_date", "Service date", "date"],
    ["prior_approval_ref", "Prior authorization reference"],
    ["group_number", "Group number"],
    ["specialty", "Specialty"],
    ["diagnosis_code", "Diagnosis code"],
    ["diagnosis_desc", "Diagnosis description"],
  ];
  return (
    <div
      onClick={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#092328]/50 backdrop-blur-xs"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="patient-intake-title"
        className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden border border-[#D5E2D9]"
      >
        <div className="px-6 py-4 border-b border-[#E8EFEA] flex items-center justify-between bg-[#F8FAF9]">
          <div>
            <h2
              id="patient-intake-title"
              className="text-base font-bold text-[#092328]"
            >
              File Patient Case &amp; Real-Time Coverage Audit
            </h2>
            <p className="text-xs text-[#698579]">
              Local extraction · Editable claim details · Approved policy
              evidence
            </p>
          </div>
          <button
            aria-label="Close patient intake"
            disabled={busy}
            onClick={onClose}
            className="p-2 cursor-pointer"
          >
            ✕
          </button>
        </div>
        <div className="p-6 overflow-y-auto space-y-5 flex-1 text-sm">
          <p className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900">
            Synthetic patient data only. Clinical PDFs, card images and
            identifiers stay local. Selectable PDF text is extracted locally.
            Scanned images require manual entry because local OCR is
            unavailable.
          </p>
          <div
            className={`p-4 rounded-xl border ${environment === "demo" ? "bg-purple-50 border-purple-200" : "bg-[#EBF4EE] border-[#D5E2D9]"}`}
          >
            <label className="text-xs font-bold block">
              Policy environment
              <select
                aria-label="Patient policy environment"
                className={`${input} mt-2`}
                value={environment}
                disabled={busy}
                onChange={(event) => {
                  setEnvironment(event.target.value as "official" | "demo");
                  setDirty(true);
                }}
              >
                <option value="official">Official / verified policies</option>
                <option value="demo">DEMO / SIMULATED policies</option>
              </select>
            </label>
            <p className="text-xs font-bold mt-2">
              {environment === "demo"
                ? "DEMO / SIMULATED — fictional rules; exact DEMO plan, state and codes must match."
                : "OFFICIAL / VERIFIED — no simulated policy fallback. Missing approved evidence remains unable to verify."}
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <section className="p-4 rounded-xl border border-[#D5E2D9] bg-[#FAFBFB] space-y-3">
              <h3 className="font-bold text-xs uppercase">
                1. Insurance details (optional card)
              </h3>
              <label className="text-xs block">
                Insurance card PDF, text or image
                <input
                  aria-label="Insurance card upload"
                  type="file"
                  accept="application/pdf,text/plain,image/png,image/jpeg,image/webp,.txt"
                  className={`${input} mt-1`}
                  disabled={busy}
                  onChange={(event) => {
                    setCardFile(event.target.files?.[0] || null);
                    invalidate();
                  }}
                />
              </label>
              <label className="text-xs block">
                Insurance details text
                <textarea
                  aria-label="Insurance details text"
                  value={cardText}
                  onChange={(event) => {
                    setCardText(event.target.value);
                    invalidate();
                  }}
                  className={`${input} mt-1`}
                  placeholder="Insurance Company: UnitedHealthcare&#10;Plan ID: DEMO-UHC-PPO&#10;Member ID: SYNTHETIC-001"
                />
              </label>
            </section>
            <section className="p-4 rounded-xl border border-[#D5E2D9] bg-[#FAFBFB] space-y-3">
              <h3 className="font-bold text-xs uppercase">
                2. Clinical order / prescription
              </h3>
              <label className="text-xs block">
                Patient PDF, text or image
                <input
                  aria-label="Clinical document upload"
                  type="file"
                  accept="application/pdf,text/plain,image/png,image/jpeg,image/webp,.txt"
                  className={`${input} mt-1`}
                  disabled={busy}
                  onChange={(event) => {
                    setClinicalFile(event.target.files?.[0] || null);
                    invalidate();
                  }}
                />
              </label>
              <label className="text-xs block">
                Clinical document text
                <textarea
                  aria-label="Clinical document text"
                  value={clinicalText}
                  onChange={(event) => {
                    setClinicalText(event.target.value);
                    invalidate();
                  }}
                  className={`${input} mt-1`}
                  placeholder="Procedure: Total Knee Replacement&#10;CPT Code: 27447&#10;State: CA&#10;Service Date: 2026-11-12"
                />
              </label>
            </section>
          </div>
          <button
            className={button}
            disabled={busy}
            onClick={() => analyze(false)}
          >
            {busy ? "Processing locally…" : "Extract locally & check policies"}
          </button>
          {error && (
            <p
              role="alert"
              className="p-3 rounded-xl bg-red-50 text-red-800 text-xs"
            >
              {error}
            </p>
          )}
          {result && (
            <section className="space-y-4 border-t border-[#D5E2D9] pt-4">
              <h3 className="font-bold text-sm">
                Review and correct extracted claim details
              </h3>
              <p className="text-xs text-[#698579]">
                Missing values remain blank. Edit any field, then recheck before
                filing. No code is guessed from a procedure name.
              </p>
              {!!result.validation_warnings.length && (
                <ul
                  role="status"
                  className="p-3 rounded-xl bg-amber-50 text-amber-900 text-xs list-disc list-inside"
                >
                  {result.validation_warnings.map((message, index) => (
                    <li key={index}>{message}</li>
                  ))}
                </ul>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {fields.map(([key, label, type]) => (
                  <label className="text-xs font-medium" key={key}>
                    {label}
                    <input
                      aria-label={`Reviewed ${label}`}
                      className={`${input} mt-1`}
                      type={type || "text"}
                      value={String(draft[key] || "")}
                      onChange={(event) => setField(key, event.target.value)}
                      disabled={busy}
                    />
                  </label>
                ))}
              </div>
              {draft.items.map((item, index) => (
                <div
                  className="p-3 border border-[#D5E2D9] rounded-xl space-y-2"
                  key={index}
                >
                  <div className="flex justify-between text-xs font-bold">
                    <span>Requested item {index + 1}</span>
                    <button
                      onClick={() =>
                        setField(
                          "items",
                          draft.items.filter((_, current) => current !== index),
                        )
                      }
                      disabled={busy}
                      className="underline"
                    >
                      Remove item
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    {(
                      [
                        ["name", "Procedure / medication"],
                        ["code", "Billing code"],
                        ["code_system", "Code system"],
                      ] as const
                    ).map(([key, label]) => (
                      <label className="text-xs" key={key}>
                        {label}
                        <input
                          aria-label={`Item ${index + 1} ${label}`}
                          className={`${input} mt-1`}
                          value={item[key] || ""}
                          disabled={busy}
                          onChange={(event) =>
                            setField(
                              "items",
                              draft.items.map((current, row) =>
                                row === index
                                  ? { ...current, [key]: event.target.value }
                                  : current,
                              ),
                            )
                          }
                        />
                      </label>
                    ))}
                    <label className="text-xs">
                      Item type
                      <select
                        aria-label={`Item ${index + 1} type`}
                        className={`${input} mt-1`}
                        value={item.type}
                        disabled={busy}
                        onChange={(event) =>
                          setField(
                            "items",
                            draft.items.map((current, row) =>
                              row === index
                                ? { ...current, type: event.target.value }
                                : current,
                            ),
                          )
                        }
                      >
                        <option value="procedure">Procedure</option>
                        <option value="drug">Medication</option>
                        <option value="service">Service</option>
                      </select>
                    </label>
                  </div>
                </div>
              ))}
              <button
                className="text-xs underline text-[#2A835F]"
                disabled={busy}
                onClick={() =>
                  setField("items", [
                    ...draft.items,
                    {
                      type: "procedure",
                      code: "",
                      name: "",
                      code_system: "",
                      quantity: 1,
                    },
                  ])
                }
              >
                Add requested item
              </button>
              <label className="text-xs block">
                Attached documents (comma separated)
                <input
                  aria-label="Reviewed attached documents"
                  className={`${input} mt-1`}
                  value={draft.documents.join(", ")}
                  disabled={busy}
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
              </label>
              <button
                className={button}
                disabled={busy}
                onClick={() => analyze(true)}
              >
                Recheck corrected details
              </button>
              {dirty ? (
                <p role="status" className="p-3 bg-amber-50 rounded-xl text-xs">
                  Claim details or policy environment changed. Recheck to update
                  findings before filing.
                </p>
              ) : (
                <ClaimFindingsPanel report={result.findings} />
              )}
            </section>
          )}
        </div>
        <div className="px-6 py-4 border-t border-[#E8EFEA] bg-[#F8FAF9] flex items-center justify-between gap-3">
          <p className="text-xs text-[#698579]">
            Findings are advisory; no claim is approved or submitted to an
            insurer.
          </p>
          <button
            className={button}
            disabled={
              busy || !result || dirty || !!result.missing_fields.length
            }
            onClick={fileCase}
          >
            File reviewed case to caseload
          </button>
        </div>
      </div>
    </div>
  );
};
