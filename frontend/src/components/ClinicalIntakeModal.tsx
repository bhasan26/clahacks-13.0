import React, { useState } from 'react';
import { X, Upload, Sparkles, ShieldCheck, Check, ArrowRight, FileText } from 'lucide-react';
import { extractCaseFromText, createCase } from '../api';
import { Case } from '../types';

interface ClinicalIntakeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCaseCreated: (createdCase: Case) => void;
}

const SAMPLE_1_CLEAN = `PATIENT CLINICAL VISIT & SUBMISSION FILE (CLEAN & COMPLETE)
Patient Encounter Date: 2026-10-25
Plan: PLAN-GOLD
Patient ID: PT-10042 (Member Ref: M-CLEAN-FILE)
Visit Type: Outpatient Specialty Follow-up
Prior Authorization Ref: PA-CARDIO-8891 (VERIFIED & ATTACHED)
Attached Documents: DOC-CHART-NOTES-2026, DOC-LAB-PANEL

DIAGNOSES:
- DX-401 (Essential Hypertension with controlled cardiovascular risk)
- DX-500 (Annual Routine Cardiometabolic Evaluation)

ORDERED MEDICATIONS & PROCEDURES:
1. DRUG-B 30-day supply (Drug B Cardiovascular oral tablet)
2. STD-CARE (Standard Consultation & Comprehensive Review)

STATUS: All diagnostic criteria satisfied. Complete patient history, attached clinical documentation, and prior approval on file. File is complete and ready to submit.`;

const SAMPLE_2_REJECTION_RISK = `PATIENT CLINICAL VISIT & SUBMISSION FILE (REJECTION RISK / GAPS)
Patient Encounter Date: 2026-11-10
Plan: PLAN-GOLD
Patient ID: PT-99214 (Member Ref: M-FLAGGED-FILE)
Visit Type: Outpatient Specialty Clinic
Prior Authorization Ref: NONE (MISSING - Procedure requires prior authorization)
Attached Documents: NONE (MISSING REQUIRED CLINICAL CHART NOTE)

DIAGNOSES:
- DX-100 (Rheumatoid arthritis with systemic joint involvement)
- DX-201 (Severe knee osteoarthritis degradation)

ORDERED MEDICATIONS & PROCEDURES:
1. DRUG-A 30-day supply (Prescribed oral biologic tablet)
   * Note: Insurer update excludes DRUG-A effective Nov 1, 2026 (Rule R-101 v2).
2. PROC-1 (Major Joint Surgical Procedure)
   * Note: Requires prior approval under Rule R-202. Prior approval reference is missing.

CLINICAL STAFF INSTRUCTION:
Do NOT submit file in current state. Take file to treating physician to choose a covered formulary alternative drug and submit prior approval documentation for the procedure before claim submission.`;

export const ClinicalIntakeModal: React.FC<ClinicalIntakeModalProps> = ({
  isOpen,
  onClose,
  onCaseCreated,
}) => {
  const [inputText, setInputText] = useState(SAMPLE_1_CLEAN);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractedData, setExtractedData] = useState<any | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleExtract = async () => {
    setIsExtracting(true);
    try {
      const res = await extractCaseFromText(inputText);
      setExtractedData(res);
    } catch (err) {
      alert('Extraction failed');
    } finally {
      setIsExtracting(false);
    }
  };

  const handleConfirmAndSave = async () => {
    if (!extractedData) return;
    setIsSubmitting(true);
    try {
      const { case: newCase } = await createCase(extractedData.extracted_case);
      onCaseCreated(newCase);
      onClose();
    } catch (err) {
      alert('Failed to save case');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white border border-slate-200/80 rounded-3xl max-w-4xl w-full max-h-[90vh] overflow-y-auto shadow-2xl flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-2xl bg-slate-900 text-lime-400 flex items-center justify-center shadow-sm">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-extrabold text-slate-900 tracking-tight">AI Clinical File Intake & Field Extraction</h2>
              <p className="text-xs text-slate-500">
                Pre-fills structured case items from uploaded notes. The AI extracts—code determines coverage.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-900 transition-colors cursor-pointer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1">
          {/* Left: Input Text / Clinical Document */}
          <div className="space-y-3 flex flex-col">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                <FileText className="h-3.5 w-3.5 text-lime-600" />
                <span>Patient Document / Clinical Text</span>
              </label>
              <div className="flex items-center space-x-1.5">
                <button
                  type="button"
                  onClick={() => {
                    setInputText(SAMPLE_1_CLEAN);
                    setExtractedData(null);
                  }}
                  className="px-2.5 py-1 rounded-xl text-[11px] font-bold bg-lime-50 hover:bg-lime-100 text-lime-800 border border-lime-300 transition-all cursor-pointer"
                >
                  ✓ Sample 1 (Complete)
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setInputText(SAMPLE_2_REJECTION_RISK);
                    setExtractedData(null);
                  }}
                  className="px-2.5 py-1 rounded-xl text-[11px] font-bold bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-300 transition-all cursor-pointer"
                >
                  ⚠ Sample 2 (Gaps)
                </button>
              </div>
            </div>

            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              rows={12}
              className="w-full flex-1 p-4 rounded-2xl bg-slate-50 border border-slate-200 font-mono text-xs text-slate-800 leading-relaxed focus:outline-none focus:border-slate-400 focus:bg-white transition-all resize-none"
              placeholder="Paste clinical progress note, discharge summary, or order sheet..."
            />

            <button
              onClick={handleExtract}
              disabled={isExtracting || !inputText.trim()}
              className="w-full py-3 rounded-2xl bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs shadow-md shadow-slate-900/10 transition-all flex items-center justify-center space-x-2 disabled:opacity-50 cursor-pointer"
            >
              <Sparkles className={`h-4 w-4 text-lime-400 ${isExtracting ? 'animate-spin' : ''}`} />
              <span>{isExtracting ? 'Extracting Fields & Redacting PII...' : 'Extract & Parse Case Fields'}</span>
            </button>
          </div>

          {/* Right: Extracted Structured Case Preview */}
          <div className="space-y-3 flex flex-col">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-lime-600" />
                <span>Extracted Schema & Source Verification</span>
              </label>
              {extractedData && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-lime-100 text-lime-800 border border-lime-200">
                  Confidence: {Math.round(extractedData.confidence * 100)}%
                </span>
              )}
            </div>

            {extractedData ? (
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-4 flex-1 overflow-y-auto max-h-[380px]">
                {/* Redaction Notice */}
                <div className="flex items-center space-x-2 p-2.5 rounded-xl bg-white border border-slate-200 text-[11px] text-slate-600">
                  <ShieldCheck className="h-4 w-4 text-lime-600 shrink-0" />
                  <span>
                    Direct PII Redacted: <strong>{extractedData.redacted_fields.join(', ')}</strong>
                  </span>
                </div>

                {/* Case Parameters */}
                <div className="grid grid-cols-2 gap-3 text-xs bg-white p-3.5 rounded-xl border border-slate-200/80">
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-bold">Case ID</span>
                    <span className="font-mono font-bold text-slate-900">
                      {extractedData.extracted_case.case_id}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-bold">Target Plan</span>
                    <span className="font-mono font-bold text-slate-900">
                      {extractedData.extracted_case.plan_id}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-bold">Service Date</span>
                    <span className="text-slate-700 font-semibold">
                      {extractedData.extracted_case.service_date}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-bold">Diagnoses</span>
                    <span className="font-mono text-slate-700 font-semibold">
                      {extractedData.extracted_case.diagnoses[0]?.code}
                    </span>
                  </div>
                </div>

                {/* Extracted Items */}
                <div className="space-y-2 pt-2 border-t border-slate-200">
                  <span className="text-slate-400 text-[11px] font-bold uppercase block">
                    Extracted Items ({extractedData.extracted_case.items.length})
                  </span>
                  {extractedData.extracted_case.items.map((item: any, i: number) => (
                    <div key={i} className="p-3.5 rounded-xl bg-white border border-slate-200 space-y-1.5 shadow-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-slate-900 text-xs">{item.code}</span>
                        <span className="text-[10px] uppercase text-slate-400 font-bold">{item.type}</span>
                      </div>
                      <p className="text-xs text-slate-800 font-semibold">{item.name}</p>
                      {item.source_text && (
                        <p className="text-[11px] text-slate-500 italic bg-slate-50 p-2 rounded-lg border border-slate-150">
                          Source text: "{item.source_text}"
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex-1 rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50/60 p-8 flex flex-col items-center justify-center text-center">
                <Upload className="h-8 w-8 text-slate-400 mb-2" />
                <h4 className="text-xs font-bold text-slate-700">No Document Extracted Yet</h4>
                <p className="text-[11px] text-slate-400 max-w-xs mt-1">
                  Click "Extract & Parse Case Fields" to review structured medical codes and citations.
                </p>
              </div>
            )}

            {/* Confirmation Action */}
            <button
              onClick={handleConfirmAndSave}
              disabled={!extractedData || isSubmitting}
              className="w-full py-3 rounded-2xl bg-lime-400 hover:bg-lime-500 text-slate-950 font-extrabold text-xs shadow-md shadow-lime-400/20 transition-all flex items-center justify-center space-x-2 disabled:opacity-50 cursor-pointer"
            >
              <Check className="h-4 w-4 text-slate-950" />
              <span>{isSubmitting ? 'Submitting Case...' : 'Confirm Fields & Run Coverage Check'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
