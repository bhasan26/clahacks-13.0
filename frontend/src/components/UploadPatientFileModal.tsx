import React, { useState } from 'react';
import { analyzeIntake, uploadPatientFile } from '../api';
import { Case, IntakeAnalysisResult, PolicyBulletin } from '../types';
import { PolicyBulletinModal } from './PolicyBulletinModal';

interface UploadPatientFileModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCaseCreated: (newCase: Case) => void;
}

export const UploadPatientFileModal: React.FC<UploadPatientFileModalProps> = ({
  isOpen,
  onClose,
  onCaseCreated,
}) => {
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

  // Quick 1-Click Real Presets
  const handleSelectPreset = async (sampleId: 'aetna_keytruda' | 'bcbs_ozempic' | 'uhc_ortho') => {
    setIsAnalyzing(true);
    setAnalysisError(null);
    setAnalysisResult(null);

    if (sampleId === 'aetna_keytruda') {
      setCardFileName('aetna_open_choice_card.png');
      setClinicalFileName('dr_evans_oncology_rx_keytruda.pdf');
    } else if (sampleId === 'bcbs_ozempic') {
      setCardFileName('bcbs_fep_card.png');
      setClinicalFileName('endocrinology_ozempic_order.pdf');
    } else {
      setCardFileName('uhc_choice_plus_card.png');
      setClinicalFileName('orthopedic_knee_surgery_order.pdf');
    }

    try {
      const res = await analyzeIntake({ sample_id: sampleId });
      setAnalysisResult(res);
    } catch (err: any) {
      setAnalysisError(err?.message || 'Failed to analyze intake sample.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Run Real AI Analysis
  const handleRunAnalysis = async () => {
    if (!cardBase64 && !cardText.trim() && !clinicalBase64 && !clinicalText.trim()) {
      alert('Please upload an insurance card or clinical note, or select one of the 1-click presets.');
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
      });
      setAnalysisResult(res);
    } catch (err: any) {
      setAnalysisError(err?.message || 'AI extraction failed. Please try again or test a sample preset.');
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
      const firstItem = clinical.items[0] || { type: 'drug', code: 'DRUG-A', name: 'Prescribed Care' };

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
          {/* Header */}
          <div className="px-6 py-4 border-b border-[#E8EFEA] flex items-center justify-between bg-[#F8FAF9]">
            <div className="flex items-center gap-3">
              <span className="w-9 h-9 rounded-xl bg-[#EBF4EE] text-[#2A835F] flex items-center justify-center text-lg font-bold border border-[#D5E2D9]">
                ⚡
              </span>
              <div>
                <h2 className="text-base font-bold text-[#092328]">
                  File Patient Case & Real-Time Coverage Audit
                </h2>
                <p className="text-xs text-[#698579]">
                  Upload insurance card + clinical order. Our AI Agent extracts billing entities and verifies active rules.
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg text-[#698579] hover:text-[#092328] hover:bg-[#E8EFEA] flex items-center justify-center transition-colors text-lg"
            >
              ✕
            </button>
          </div>

          {/* Quick Presets Bar */}
          <div className="px-6 py-2.5 bg-[#F4F7F5] border-b border-[#E8EFEA] flex flex-wrap items-center gap-2 text-xs">
            <span className="font-bold text-[#698579] uppercase tracking-wider text-[11px] mr-1">
              1-Click Verified Tests:
            </span>
            <button
              type="button"
              onClick={() => handleSelectPreset('aetna_keytruda')}
              className="px-3 py-1.5 rounded-lg bg-white border border-[#D5E2D9] text-[#092328] font-semibold hover:border-[#2A835F] hover:bg-[#EBF4EE] transition-all flex items-center gap-1.5 shadow-2xs"
            >
              <span className="text-purple-600 font-bold">🧬 Aetna</span>
              <span>· Keytruda (Prior Auth Missing)</span>
            </button>
            <button
              type="button"
              onClick={() => handleSelectPreset('bcbs_ozempic')}
              className="px-3 py-1.5 rounded-lg bg-white border border-[#D5E2D9] text-[#092328] font-semibold hover:border-[#2A835F] hover:bg-[#EBF4EE] transition-all flex items-center gap-1.5 shadow-2xs"
            >
              <span className="text-blue-600 font-bold">💊 BCBS</span>
              <span>· Ozempic (Formulary Excluded)</span>
            </button>
            <button
              type="button"
              onClick={() => handleSelectPreset('uhc_ortho')}
              className="px-3 py-1.5 rounded-lg bg-white border border-[#D5E2D9] text-[#092328] font-semibold hover:border-[#2A835F] hover:bg-[#EBF4EE] transition-all flex items-center gap-1.5 shadow-2xs"
            >
              <span className="text-emerald-600 font-bold">🏥 UHC</span>
              <span>· Knee Surgery (Compliant & Approved)</span>
            </button>
          </div>

          {/* Main Body */}
          <div className="p-6 overflow-y-auto space-y-6 flex-1 text-sm">
            {/* Upload Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Box 1: Insurance Card */}
              <div className="p-4 rounded-xl border border-[#D5E2D9] bg-[#FAFBFB] space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-base">💳</span>
                    <h3 className="font-bold text-xs uppercase tracking-wider text-[#092328]">
                      1. Insurance Card (Photo / PDF)
                    </h3>
                  </div>
                  {cardFileName && (
                    <span className="text-[11px] font-bold text-[#2A835F] bg-[#EBF4EE] px-2 py-0.5 rounded">
                      File Attached
                    </span>
                  )}
                </div>

                <label className="block p-4 border-2 border-dashed border-[#C5D5CB] rounded-xl text-center hover:border-[#2A835F] hover:bg-white transition-colors cursor-pointer group">
                  <input
                    type="file"
                    accept="image/*,application/pdf"
                    onChange={handleCardFileChange}
                    className="hidden"
                  />
                  <div className="space-y-1">
                    <span className="text-2xl block group-hover:scale-110 transition-transform">📷</span>
                    <p className="text-xs font-semibold text-[#092328]">
                      {cardFileName || 'Drop insurance card photo or click to browse'}
                    </p>
                    <p className="text-[11px] text-[#698579]">Reads Insurer, Member ID, Group #, Plan Type</p>
                  </div>
                </label>

                <div>
                  <label className="block text-[11px] font-semibold text-[#698579] mb-1">
                    Or paste card details / Member ID:
                  </label>
                  <input
                    type="text"
                    value={cardText}
                    onChange={(e) => setCardText(e.target.value)}
                    placeholder="e.g. Aetna Choice POS II, Member: W92837482, Group: 881290"
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-[#D5E2D9] focus:outline-none focus:border-[#2A835F] bg-white text-[#092328]"
                  />
                </div>
              </div>

              {/* Box 2: Clinical File / Order */}
              <div className="p-4 rounded-xl border border-[#D5E2D9] bg-[#FAFBFB] space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-base">📋</span>
                    <h3 className="font-bold text-xs uppercase tracking-wider text-[#092328]">
                      2. Clinical Order / Prescription
                    </h3>
                  </div>
                  {clinicalFileName && (
                    <span className="text-[11px] font-bold text-[#2A835F] bg-[#EBF4EE] px-2 py-0.5 rounded">
                      File Attached
                    </span>
                  )}
                </div>

                <label className="block p-4 border-2 border-dashed border-[#C5D5CB] rounded-xl text-center hover:border-[#2A835F] hover:bg-white transition-colors cursor-pointer group">
                  <input
                    type="file"
                    accept="image/*,application/pdf,.txt,.doc"
                    onChange={handleClinicalFileChange}
                    className="hidden"
                  />
                  <div className="space-y-1">
                    <span className="text-2xl block group-hover:scale-110 transition-transform">📄</span>
                    <p className="text-xs font-semibold text-[#092328]">
                      {clinicalFileName || 'Drop clinical summary, order or Rx'}
                    </p>
                    <p className="text-[11px] text-[#698579]">Extracts Diagnosis, Drugs, Procedures & Docs</p>
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
                    placeholder="e.g. Pembrolizumab 200mg IV for Non-Small Cell Lung Cancer Stage IV"
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-[#D5E2D9] focus:outline-none focus:border-[#2A835F] bg-white text-[#092328]"
                  />
                </div>
              </div>
            </div>

            {/* Run Analysis Trigger Button */}
            <div className="flex items-center justify-between p-3.5 rounded-xl bg-[#F0F5F2] border border-[#D5E2D9]">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#2A835F] animate-pulse" />
                <span className="text-xs font-bold text-[#092328]">
                  Gemini 3 Flash Vision & Rule Engine Ready
                </span>
              </div>
              <button
                type="button"
                onClick={handleRunAnalysis}
                disabled={isAnalyzing}
                className="px-5 py-2.5 rounded-xl bg-[#2A835F] text-white text-xs font-bold hover:bg-[#1F6347] transition-all shadow-sm flex items-center gap-2 disabled:opacity-50"
              >
                {isAnalyzing ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Extracting & Auditing Rules...</span>
                  </>
                ) : (
                  <>
                    <span>⚡ Run AI Coverage Check</span>
                  </>
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
                    ● Status: {analysisResult.check_result.status}
                  </span>
                </div>

                {/* Split Extracted Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  {/* Extracted Card Data */}
                  <div className="p-3.5 rounded-xl bg-white border border-[#D5E2D9] space-y-2">
                    <span className="font-bold text-[#698579] uppercase tracking-wider text-[11px] block">
                      Extracted Payer & Plan Details
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

                          {verdict.rule_id && (
                            <button
                              type="button"
                              onClick={() => openBulletinReview(verdict.rule_id, analysisResult.bulletin)}
                              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white border border-[#D5E2D9] text-[#2A835F] text-xs font-bold hover:bg-[#EBF4EE] transition-colors shadow-2xs"
                            >
                              <span>📄 Review Policy Bulletin {verdict.rule_id}</span>
                              <span>↗</span>
                            </button>
                          )}
                        </div>

                        {/* Plain single sentence citation */}
                        <p className="text-xs text-[#092328] font-medium leading-relaxed mb-2">
                          {verdict.full_issue_text}
                        </p>

                        {/* Why not approved breakdown */}
                        {isIssue && verdict.why_not_approved && (
                          <div className="mt-2.5 p-3 rounded-lg bg-white/80 border border-amber-200/60 text-xs text-[#92400E] space-y-1.5">
                            <div className="flex items-center gap-1.5 font-bold">
                              <span>⚠️</span>
                              <span>Why It's Not Approved Under Active Rules:</span>
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
                className="px-4 py-2 rounded-xl text-xs font-semibold text-[#698579] hover:bg-[#E8EFEA] transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleFileCase}
                disabled={!analysisResult || isSubmitting}
                className="px-5 py-2.5 rounded-xl bg-[#092328] text-white text-xs font-bold hover:bg-[#133E46] transition-colors shadow-sm disabled:opacity-40 flex items-center gap-2"
              >
                {isSubmitting ? 'Saving to Caseload...' : 'File Case to Hospital Caseload →'}
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
