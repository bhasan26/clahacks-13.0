import React, { useState } from 'react';
import { analyzeIntake, uploadPatientFile } from '../api';
import { Case, IntakeAnalysisResult, PolicyBulletin } from '../types';
import { PolicyBulletinModal } from './PolicyBulletinModal';

interface UploadPatientFileModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCaseCreated: (newCase: Case) => void;
}

const INSURER_DROPDOWN_OPTIONS = [
  { id: 'auto', name: 'Auto-detect from Clinical Order / Upload' },
  { id: 'uhc', name: 'UnitedHealthcare (UHC)' },
  { id: 'aetna', name: 'Aetna Health' },
  { id: 'bcbs', name: 'Blue Cross Blue Shield (BCBS)' },
  { id: 'cigna', name: 'Cigna Healthcare' },
  { id: 'cms', name: 'Medicare / CMS' },
];

export const UploadPatientFileModal: React.FC<UploadPatientFileModalProps> = ({
  isOpen,
  onClose,
  onCaseCreated,
}) => {
  // Payer selection (optional card, or explicit selector)
  const [selectedInsurer, setSelectedInsurer] = useState<string>('auto');

  // Uploaded files / text
  const [cardFileName, setCardFileName] = useState<string | null>(null);
  const [cardBase64, setCardBase64] = useState<string | null>(null);
  const [cardText, setCardText] = useState<string>('');

  const [clinicalFileName, setClinicalFileName] = useState<string | null>(null);
  const [clinicalBase64, setClinicalBase64] = useState<string | null>(null);
  const [clinicalText, setClinicalText] = useState<string>('');

  // Analysis State
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [analysisResult, setAnalysisResult] = useState<IntakeAnalysisResult | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // Policy Bulletin Modal
  const [bulletinModalOpen, setBulletinModalOpen] = useState<boolean>(false);
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);
  const [selectedBulletin, setSelectedBulletin] = useState<PolicyBulletin | null>(null);

  // Submitting
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  if (!isOpen) return null;

  // Convert File to Base64
  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = (error) => reject(error);
      reader.readAsDataURL(file);
    });
  };

  const handleCardFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setCardFileName(file.name);
      try {
        const b64 = await fileToBase64(file);
        setCardBase64(b64);
      } catch (err) {
        console.error('Error reading card file:', err);
      }
    }
  };

  const handleClinicalFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setClinicalFileName(file.name);
      try {
        const b64 = await fileToBase64(file);
        setClinicalBase64(b64);
      } catch (err) {
        console.error('Error reading clinical file:', err);
      }
    }
  };


  // Run Real AI Analysis
  const handleRunAnalysis = async () => {
    if (!cardBase64 && !cardText.trim() && !clinicalBase64 && !clinicalText.trim() && selectedInsurer === 'auto') {
      alert('Please upload a clinical order, enter text, or select an insurer.');
      return;
    }

    setIsAnalyzing(true);
    setAnalysisError(null);
    setAnalysisResult(null);

    try {
      const res = await analyzeIntake({
        card_image_b64: cardBase64 || undefined,
        card_text: cardText || undefined,
        clinical_doc_b64: clinicalBase64 || undefined,
        clinical_text: clinicalText || undefined,
        selected_insurer_id: selectedInsurer !== 'auto' ? selectedInsurer : undefined,
      });
      setAnalysisResult(res);
    } catch (err: any) {
      setAnalysisError(err?.message || 'AI extraction failed. Please check files or verify connection.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  // File Case to Caseload
  const handleFileCase = async () => {
    if (!analysisResult) return;
    setIsSubmitting(true);

    try {
      const card = analysisResult.card;
      const clinical = analysisResult.clinical;

      if (!clinical.items || clinical.items.length === 0) {
        alert('No clinical procedure or drug items were detected. Please ensure your clinical order contains recognizable items.');
        setIsSubmitting(false);
        return;
      }
      const firstItem = clinical.items[0];

      const res = await uploadPatientFile({
        specialty: clinical.specialty,
        patient_text: clinical.patient_name ? `Patient ${clinical.patient_name}` : 'Intake patient',
        prescription_text: firstItem.name,
        insurer_id: card.insurer_id,
        insurer_name: card.insurer_name,
        plan_id: card.plan_id,
        member_ref: card.member_ref,
        group_number: card.group_number,
        item_name: firstItem.name,
        item_type: firstItem.type,
        item_code: firstItem.code,
        service_date: clinical.service_date,
        prior_approval_ref: clinical.prior_approval_ref || undefined,
        diagnosis_code: clinical.diagnosis_code,
        diagnosis_desc: clinical.diagnosis_desc,
        documents: clinical.documents,
      });

      onCaseCreated(res.case);
      onClose();
    } catch (err: any) {
      alert('Failed to file case to caseload: ' + (err?.message || 'Unknown error'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const openBulletinReview = (ruleId?: string, bulletin?: PolicyBulletin | null) => {
    if (!ruleId) return;
    setSelectedRuleId(ruleId);
    setSelectedBulletin(bulletin || null);
    setBulletinModalOpen(true);
  };

  return (
    <>
      <div
        onClick={(e) => {
          if (e.target === e.currentTarget) onClose();
        }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#092328]/50 backdrop-blur-xs animate-in fade-in duration-150"
      >
        <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden border border-[#D5E2D9]">
          {/* Header without symbols */}
          <div className="px-6 py-4 border-b border-[#E8EFEA] flex items-center justify-between bg-[#F8FAF9]">
            <div className="flex items-center gap-3">
              <span className="px-2.5 py-1 rounded-lg bg-[#EBF4EE] text-[#2A835F] text-xs font-bold border border-[#D5E2D9] tracking-wider uppercase">
                Intake
              </span>
              <div>
                <h2 className="text-base font-bold text-[#092328]">
                  File Patient Case & Real-Time Coverage Audit
                </h2>
                <p className="text-xs text-[#698579]">
                  Upload clinical order and optional insurance details. The engine verifies coverage against versioned payer rules.
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg text-[#698579] hover:text-[#092328] hover:bg-[#E8EFEA] flex items-center justify-center transition-colors cursor-pointer"
              aria-label="Close"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>


          {/* Main Body */}
          <div className="p-6 overflow-y-auto space-y-6 flex-1 text-sm">
            {/* Privacy Safeguard Banner */}
            <div className="p-3 bg-amber-50/80 border border-amber-200 rounded-xl flex items-start gap-3">
              <svg className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div className="text-xs text-amber-900 leading-relaxed">
                <span className="font-bold">Privacy Safeguard & Synthetic Data Notice:</span> This hackathon environment processes synthetic patient test fixtures only. Text redaction is partial. Uploaded images are not de-identified and may be sent to Gemini. Synthetic review records are saved locally. Do not submit live unredacted Protected Health Information (PHI).
              </div>
            </div>

            {/* Upload Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Box 1: Insurance Details (Optional) */}
              <div className="p-4 rounded-xl border border-[#D5E2D9] bg-[#FAFBFB] space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-xs uppercase tracking-wider text-[#092328]">
                    1. Insurance Details <span className="font-normal text-[#698579] lowercase">(optional)</span>
                  </h3>
                  {cardFileName ? (
                    <span className="text-[11px] font-bold text-[#2A835F] bg-[#EBF4EE] px-2 py-0.5 rounded">
                      File Attached
                    </span>
                  ) : (
                    <span className="text-[11px] text-[#698579] bg-gray-100 px-2 py-0.5 rounded">
                      Optional
                    </span>
                  )}
                </div>

                {/* Insurer Selector Dropdown */}
                <div>
                  <label className="block text-[11px] font-semibold text-[#698579] mb-1">
                    Select Insurer or Auto-Detect:
                  </label>
                  <select
                    value={selectedInsurer}
                    onChange={(e) => setSelectedInsurer(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-lg border border-[#D5E2D9] bg-white text-[#092328] font-medium focus:outline-none focus:border-[#2A835F]"
                  >
                    {INSURER_DROPDOWN_OPTIONS.map((opt) => (
                      <option key={opt.id} value={opt.id}>
                        {opt.name}
                      </option>
                    ))}
                  </select>
                </div>

                <label className="block p-3.5 border-2 border-dashed border-[#C5D5CB] rounded-xl text-center hover:border-[#2A835F] hover:bg-white transition-colors cursor-pointer group">
                  <input
                    type="file"
                    accept="image/*,application/pdf"
                    onChange={handleCardFileChange}
                    className="hidden"
                  />
                  <div className="space-y-1">
                    <p className="text-xs font-semibold text-[#092328]">
                      {cardFileName || 'Upload insurance card photo or PDF (optional)'}
                    </p>
                    <p className="text-[11px] text-[#698579]">If omitted, insurer is detected from clinical order</p>
                  </div>
                </label>

                <div>
                  <label className="block text-[11px] font-semibold text-[#698579] mb-1">
                    Or enter Member ID / Plan Name:
                  </label>
                  <input
                    type="text"
                    value={cardText}
                    onChange={(e) => setCardText(e.target.value)}
                    placeholder="e.g. UnitedHealthcare, Member ID: UHC-9928109"
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-[#D5E2D9] focus:outline-none focus:border-[#2A835F] bg-white text-[#092328]"
                  />
                </div>
              </div>

              {/* Box 2: Clinical File / Order (Primary) */}
              <div className="p-4 rounded-xl border border-[#D5E2D9] bg-[#FAFBFB] space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-xs uppercase tracking-wider text-[#092328]">
                    2. Clinical Order / Prescription <span className="text-[#2A835F]">*</span>
                  </h3>
                  {clinicalFileName ? (
                    <span className="text-[11px] font-bold text-[#2A835F] bg-[#EBF4EE] px-2 py-0.5 rounded">
                      File Attached
                    </span>
                  ) : (
                    <span className="text-[11px] font-semibold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded">
                      Required
                    </span>
                  )}
                </div>

                <label className="block p-3.5 border-2 border-dashed border-[#C5D5CB] rounded-xl text-center hover:border-[#2A835F] hover:bg-white transition-colors cursor-pointer group">
                  <input
                    type="file"
                    accept="image/*,application/pdf,.txt,.doc"
                    onChange={handleClinicalFileChange}
                    className="hidden"
                  />
                  <div className="space-y-1">
                    <p className="text-xs font-semibold text-[#092328]">
                      {clinicalFileName || 'Drop clinical order, Rx, or encounter PDF / text'}
                    </p>
                    <p className="text-[11px] text-[#698579]">Extracts Diagnosis, Drugs, Procedures & Prior Auth</p>
                  </div>
                </label>

                <div>
                  <label className="block text-[11px] font-semibold text-[#698579] mb-1">
                    Or paste clinical note / prescription text:
                  </label>
                  <input
                    type="text"
                    value={clinicalText}
                    onChange={(e) => setClinicalText(e.target.value)}
                    placeholder="e.g. Humira 40mg IV for Rheumatoid Arthritis or Keytruda 200mg"
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-[#D5E2D9] focus:outline-none focus:border-[#2A835F] bg-white text-[#092328]"
                  />
                </div>
              </div>
            </div>

            {/* Run Analysis Trigger Button without emoji */}
            <div className="flex items-center justify-between p-3.5 rounded-xl bg-[#F0F5F2] border border-[#D5E2D9]">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#2A835F]" />
                <span className="text-xs font-bold text-[#092328]">
                  Deterministic Rules Engine Ready
                </span>
              </div>
              <button
                type="button"
                onClick={handleRunAnalysis}
                disabled={isAnalyzing}
                className="px-5 py-2.5 rounded-xl bg-[#2A835F] text-white text-xs font-bold hover:bg-[#1F6347] transition-all shadow-sm flex items-center gap-2 disabled:opacity-50 cursor-pointer"
              >
                {isAnalyzing ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Analyzing & Auditing Rules...</span>
                  </>
                ) : (
                  <span>Run AI Coverage Check</span>
                )}
              </button>
            </div>

            {/* Error banner */}
            {analysisError && (
              <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs font-medium">
                {analysisError}
              </div>
            )}

            {/* Live Audit Results View */}
            {analysisResult && (
              <div className="space-y-4 pt-2 animate-in fade-in duration-200">
                <div className="flex items-center justify-between border-b border-[#E8EFEA] pb-2">
                  <h3 className="font-bold text-xs uppercase tracking-wider text-[#698579]">
                    Coverage Pre-Check Audit Determination
                  </h3>
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-bold ${
                      analysisResult.check_result.status === 'Approved'
                        ? 'bg-[#EBF4EE] text-[#2A835F] border border-[#2A835F]/30'
                        : analysisResult.check_result.status === 'Needs attention'
                        ? 'bg-[#FEF3C7] text-[#D97706] border border-[#D97706]/30'
                        : 'bg-red-50 text-red-700 border border-red-200'
                    }`}
                  >
                    Status: {analysisResult.check_result.status}
                  </span>
                </div>

                {/* Split Extracted Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  {/* Extracted Card Data */}
                  <div className="p-3.5 rounded-xl bg-white border border-[#D5E2D9] space-y-2">
                    <span className="font-bold text-[#698579] uppercase tracking-wider text-[11px] block">
                      Payer & Plan Details
                    </span>
                    <div className="grid grid-cols-2 gap-2 text-[12px]">
                      <div>
                        <span className="text-[#698579] block text-[11px]">Insurer</span>
                        <span className="font-bold text-[#092328]">{analysisResult.card.insurer_name}</span>
                      </div>
                      <div>
                        <span className="text-[#698579] block text-[11px]">Member ID</span>
                        <span className="font-mono font-bold text-[#092328]">{analysisResult.card.member_ref}</span>
                      </div>
                      <div>
                        <span className="text-[#698579] block text-[11px]">Plan Name</span>
                        <span className="font-medium text-[#092328]">{analysisResult.card.plan_name}</span>
                      </div>
                      <div>
                        <span className="text-[#698579] block text-[11px]">Group #</span>
                        <span className="font-mono text-[#092328]">{analysisResult.card.group_number || 'Standard'}</span>
                      </div>
                    </div>
                  </div>

                  {/* Extracted Clinical Data */}
                  <div className="p-3.5 rounded-xl bg-white border border-[#D5E2D9] space-y-2">
                    <span className="font-bold text-[#698579] uppercase tracking-wider text-[11px] block">
                      Extracted Clinical Order
                    </span>
                    <div className="grid grid-cols-2 gap-2 text-[12px]">
                      <div>
                        <span className="text-[#698579] block text-[11px]">Patient / Specialty</span>
                        <span className="font-bold text-[#092328]">
                          {analysisResult.clinical.patient_name || 'Patient'} ({analysisResult.clinical.specialty})
                        </span>
                      </div>
                      <div>
                        <span className="text-[#698579] block text-[11px]">Service Date</span>
                        <span className="font-bold text-[#092328]">{analysisResult.clinical.service_date}</span>
                      </div>
                      <div className="col-span-2">
                        <span className="text-[#698579] block text-[11px]">Primary Diagnosis</span>
                        <span className="font-medium text-[#092328]">
                          <span className="font-mono font-bold mr-1">{analysisResult.clinical.diagnosis_code}</span>
                          {analysisResult.clinical.diagnosis_desc}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Item-by-item Verdict Cards */}
                <div className="space-y-3">
                  {analysisResult.check_result.results.map((verdict, idx) => {
                    const isIssue = verdict.result !== 'Covered';
                    return (
                      <div
                        key={idx}
                        className={`p-4 rounded-xl border ${
                          verdict.result === 'Covered'
                            ? 'bg-[#F8FAF9] border-[#D5E2D9]'
                            : verdict.result === 'Not covered'
                            ? 'bg-red-50/70 border-red-200'
                            : 'bg-[#FFFDF5] border-[#FDE68A]'
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-[#092328] text-sm">
                              {verdict.item.name || verdict.item.code}
                            </span>
                            <span
                              className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                                verdict.result === 'Covered'
                                  ? 'bg-[#EBF4EE] text-[#2A835F]'
                                  : verdict.result === 'Not covered'
                                  ? 'bg-red-100 text-red-700'
                                  : 'bg-amber-100 text-amber-800'
                              }`}
                            >
                              {verdict.result}
                            </span>
                          </div>

                          <div className="flex flex-wrap items-center gap-2">
                            {(verdict.official_reference_url || analysisResult.bulletin?.official_reference_url) && (
                              <a
                                href={verdict.official_reference_url || analysisResult.bulletin?.official_reference_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-[#2A835F] text-white text-xs font-bold hover:bg-[#20684b] transition-colors shadow-2xs cursor-pointer"
                              >
                                <span>Official Payer Document</span>
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                </svg>
                              </a>
                            )}

                            {verdict.rule_id && (
                              <button
                                type="button"
                                onClick={() => openBulletinReview(verdict.rule_id, analysisResult.bulletin)}
                                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white border border-[#D5E2D9] text-[#2A835F] text-xs font-bold hover:bg-[#EBF4EE] transition-colors shadow-2xs cursor-pointer"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                                <span>Review Policy Bulletin {verdict.rule_id}</span>
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Plain single sentence citation */}
                        <p className="text-xs text-[#092328] font-medium leading-relaxed mb-2">
                          {verdict.full_issue_text}
                        </p>

                        {/* Why not approved breakdown without emojis */}
                        {isIssue && verdict.why_not_approved && (
                          <div className="mt-2.5 p-3 rounded-lg bg-white/80 border border-amber-200/60 text-xs text-[#92400E] space-y-1.5">
                            <div className="font-bold text-amber-900">
                              Reason Not Approved Under Active Rules:
                            </div>
                            <p>{verdict.why_not_approved}</p>

                            {/* Action Guidance */}
                            {verdict.action_guidance && verdict.action_guidance.length > 0 && (
                              <div className="pt-2 border-t border-amber-200/50 space-y-1">
                                <span className="text-[11px] font-bold text-[#092328] uppercase tracking-wider block">
                                  Action Steps for Claims Officer:
                                </span>
                                <ul className="list-disc list-inside space-y-0.5 text-xs text-[#092328]">
                                  {verdict.action_guidance.map((step, sIdx) => (
                                    <li key={sIdx}>{step}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-[#E8EFEA] bg-[#F8FAF9] flex items-center justify-between">
            <span className="text-xs text-[#698579]">
              {analysisResult ? 'Audit verified against active payer rulebook' : 'Ready to evaluate'}
            </span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-[#698579] hover:bg-[#E8EFEA] transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleFileCase}
                disabled={!analysisResult || isSubmitting}
                className="px-5 py-2.5 rounded-xl bg-[#092328] text-white text-xs font-bold hover:bg-[#133E46] transition-colors shadow-sm disabled:opacity-40 flex items-center gap-2 cursor-pointer"
              >
                <span>{isSubmitting ? 'Saving to Caseload...' : 'File Case to Hospital Caseload'}</span>
                {!isSubmitting && (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Official Insurer Policy Bulletin Modal */}
      <PolicyBulletinModal
        isOpen={bulletinModalOpen}
        onClose={() => setBulletinModalOpen(false)}
        ruleId={selectedRuleId}
        initialBulletin={selectedBulletin}
      />
    </>
  );
};
