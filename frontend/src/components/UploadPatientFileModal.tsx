import React, { useState } from 'react';
import { uploadPatientFile } from '../api';
import { Case } from '../types';

interface UploadPatientFileModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCaseCreated: (newCase: Case) => void;
}

const INSURER_OPTIONS = [
  { id: 'demo-insurer', name: 'Demo Insurance Co. (Connected Live)' },
  { id: 'bcbs', name: 'Blue Cross Blue Shield' },
  { id: 'uhc', name: 'UnitedHealthcare' },
  { id: 'aetna', name: 'Aetna Health' },
  { id: 'cigna', name: 'Cigna Healthcare' },
  { id: 'kaiser', name: 'Kaiser Permanente' },
  { id: 'cms', name: 'Medicare / CMS' },
];

const PLAN_OPTIONS = [
  { id: 'PLAN-GOLD', name: 'PLAN-GOLD (Commercial Comprehensive)' },
  { id: 'PLAN-SILVER', name: 'PLAN-SILVER (Standard PPO)' },
  { id: 'PLAN-BRONZE', name: 'PLAN-BRONZE (High Deductible)' },
  { id: 'MED-ADVANTAGE', name: 'MED-ADVANTAGE (Medicare Advantage)' },
];

export const UploadPatientFileModal: React.FC<UploadPatientFileModalProps> = ({
  isOpen,
  onClose,
  onCaseCreated,
}) => {
  // Insurance input mode: 'manual' | 'card'
  const [insuranceMode, setInsuranceMode] = useState<'manual' | 'card'>('manual');
  const [insurerId, setInsurerId] = useState<string>('demo-insurer');
  const [insurerName, setInsurerName] = useState<string>('Demo Insurance Co.');
  const [planId, setPlanId] = useState<string>('PLAN-GOLD');
  const [memberRef, setMemberRef] = useState<string>('M-88219');
  const [groupNumber, setGroupNumber] = useState<string>('GRP-40291');

  // Insurance Card upload state
  const [cardFileName, setCardFileName] = useState<string | null>(null);
  const [isScanningCard, setIsScanningCard] = useState<boolean>(false);
  const [isCardScanned, setIsCardScanned] = useState<boolean>(false);

  // Clinical & item state
  const [specialty, setSpecialty] = useState<string>('Cardiology');
  const [patientText, setPatientText] = useState<string>('');
  const [prescriptionText, setPrescriptionText] = useState<string>('');
  const [itemType, setItemType] = useState<string>('drug');
  const [itemName, setItemName] = useState<string>('Drug A');
  const [itemCode, setItemCode] = useState<string>('DRUG-A');
  const [priorApprovalRef, setPriorApprovalRef] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // How it works banner toggle
  const [showHowItWorks, setShowHowItWorks] = useState<boolean>(false);

  if (!isOpen) return null;

  const handleApplySample = (type: 'approved' | 'needs_attention') => {
    if (type === 'approved') {
      setSpecialty('Cardiology');
      setItemType('drug');
      setItemName('Drug B (Cardiovascular)');
      setItemCode('DRUG-B');
      setPatientText('Patient M-904 present for routine cardiovascular follow-up. Vital signs stable.');
      setPrescriptionText('Prescribed Drug B (Cardiovascular) 30-day maintenance supply.');
      setPriorApprovalRef('');
      setMemberRef('M-904');
      setInsurerId('demo-insurer');
      setInsurerName('Demo Insurance Co.');
      setPlanId('PLAN-GOLD');
    } else {
      setSpecialty('Orthopedics');
      setItemType('procedure');
      setItemName('Major Joint Procedure');
      setItemCode('PROC-1');
      setPatientText('Patient M-905 severe right hip osteoarthritis. Scheduled for joint intervention.');
      setPrescriptionText('Major Joint Procedure PROC-1 indicated. Prior authorization pending.');
      setPriorApprovalRef('');
      setMemberRef('M-905');
      setInsurerId('demo-insurer');
      setInsurerName('Demo Insurance Co.');
      setPlanId('PLAN-GOLD');
    }
  };

  const handleSimulateCardScan = (customName?: string) => {
    setIsScanningCard(true);
    setTimeout(() => {
      setIsScanningCard(false);
      setIsCardScanned(true);
      setCardFileName(customName || 'insurance_card_front.png');
      setInsurerId('demo-insurer');
      setInsurerName('Demo Insurance Co.');
      setPlanId('PLAN-GOLD');
      setMemberRef('M-88219');
      setGroupNumber('GRP-40291');
    }, 600);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleSimulateCardScan(file.name);
    }
  };

  const handleResetCard = () => {
    setIsCardScanned(false);
    setCardFileName(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientText.trim()) return;

    setIsSubmitting(true);
    try {
      const res = await uploadPatientFile({
        specialty,
        patient_text: patientText,
        prescription_text: prescriptionText,
        insurer_id: insurerId,
        insurer_name: insurerName,
        plan_id: planId,
        member_ref: memberRef.trim() || undefined,
        group_number: groupNumber.trim() || undefined,
        item_name: itemName,
        item_type: itemType,
        item_code: itemCode,
        prior_approval_ref: priorApprovalRef.trim() || undefined,
      });
      onCaseCreated(res.case);
      onClose();
    } catch (err) {
      alert('Failed to upload patient file. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#092328]/40 backdrop-blur-xs animate-in fade-in duration-150"
    >
      <div className="bg-white border border-[#D8E5DC] rounded-3xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 shadow-2xl space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#EAEFEA] pb-3">
          <div>
            <h2 className="text-lg font-black text-[#092328] tracking-tight">
              Upload Patient File
            </h2>
            <p className="text-xs text-[#12544F]/70">
              Upload patient clinical record, prescription, and insurance details for automated coverage check.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[#12544F]/60 hover:text-[#092328] text-sm font-bold cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Top Action Bar: Prefill samples + "How it works" toggle */}
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center space-x-2">
            <span className="text-[#12544F]/70 font-semibold">Prefill sample:</span>
            <button
              type="button"
              onClick={() => handleApplySample('approved')}
              className="px-2.5 py-1 bg-[#F0F5F2] hover:bg-[#EAEFEA] text-[#092328] font-bold rounded-lg cursor-pointer transition-colors"
            >
              Sample: Covered Care
            </button>
            <button
              type="button"
              onClick={() => handleApplySample('needs_attention')}
              className="px-2.5 py-1 bg-[#F0F5F2] hover:bg-[#EAEFEA] text-[#D97706] font-bold rounded-lg cursor-pointer transition-colors"
            >
              Sample: Prior Auth Gap
            </button>
          </div>

          <button
            type="button"
            onClick={() => setShowHowItWorks(!showHowItWorks)}
            className="text-[11px] font-bold text-[#12544F] hover:underline flex items-center space-x-1 cursor-pointer"
          >
            <span>{showHowItWorks ? '▾ Hide workflow' : '▸ How it works'}</span>
          </button>
        </div>

        {/* Collapsible Explainer: "How it works" */}
        {showHowItWorks && (
          <div className="p-3.5 rounded-2xl bg-[#F0F5F2] border border-[#D8E5DC] text-xs text-[#092328] space-y-2 animate-in fade-in duration-150">
            <div className="font-bold text-[#12544F] flex items-center space-x-1.5">
              <span>Automated Verification Workflow</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 text-[11px] leading-snug">
              <div className="p-2 bg-white rounded-xl border border-[#D8E5DC]/80">
                <span className="font-bold text-[#092328] block mb-0.5">1. Intake</span>
                Ingests clinical notes, orders, and insurance card / policy details.
              </div>
              <div className="p-2 bg-white rounded-xl border border-[#D8E5DC]/80">
                <span className="font-bold text-[#092328] block mb-0.5">2. Payer Sync</span>
                Matches against the insurer’s live published rules via read-only connection.
              </div>
              <div className="p-2 bg-white rounded-xl border border-[#D8E5DC]/80">
                <span className="font-bold text-[#092328] block mb-0.5">3. Rule Check</span>
                Pure Boolean logic verifies coverage, prior approval, and required docs.
              </div>
              <div className="p-2 bg-white rounded-xl border border-[#D8E5DC]/80">
                <span className="font-bold text-[#092328] block mb-0.5">4. Verdict</span>
                Reports Approved, Needs attention, or Missing info with exact officer actions.
              </div>
            </div>
          </div>
        )}

        {/* Main Form */}
        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* SECTION 1: Insurance Details (Manual vs Card Upload) */}
          <div className="p-3.5 rounded-2xl border border-[#D8E5DC] bg-[#FBFDFB] space-y-3">
            <div className="flex items-center justify-between">
              <label className="font-black text-[#092328] tracking-tight text-xs uppercase">
                Patient Insurance Details
              </label>

              {/* Mode Switcher Tabs */}
              <div className="flex items-center bg-[#F0F5F2] p-0.5 rounded-xl border border-[#D8E5DC]">
                <button
                  type="button"
                  onClick={() => setInsuranceMode('manual')}
                  className={`px-3 py-1 rounded-lg font-bold text-xs transition-all cursor-pointer ${
                    insuranceMode === 'manual'
                      ? 'bg-white text-[#092328] shadow-xs'
                      : 'text-[#12544F]/70 hover:text-[#092328]'
                  }`}
                >
                  Enter Manually
                </button>
                <button
                  type="button"
                  onClick={() => setInsuranceMode('card')}
                  className={`px-3 py-1 rounded-lg font-bold text-xs transition-all cursor-pointer ${
                    insuranceMode === 'card'
                      ? 'bg-white text-[#092328] shadow-xs'
                      : 'text-[#12544F]/70 hover:text-[#092328]'
                  }`}
                >
                  Upload Card
                </button>
              </div>
            </div>

            {/* TAB 1: Enter Details Manually */}
            {insuranceMode === 'manual' && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                <div className="space-y-1">
                  <label className="font-bold text-[#092328]">Insurer / Issuer</label>
                  <select
                    value={insurerId}
                    onChange={(e) => {
                      setInsurerId(e.target.value);
                      const opt = INSURER_OPTIONS.find((o) => o.id === e.target.value);
                      if (opt) setInsurerName(opt.name.replace(' (Connected Live)', ''));
                    }}
                    className="w-full px-3 py-2 bg-white border border-[#D8E5DC] rounded-xl text-[#092328] font-semibold focus:outline-none focus:border-[#2A835F]"
                  >
                    {INSURER_OPTIONS.map((opt) => (
                      <option key={opt.id} value={opt.id}>
                        {opt.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-[#092328]">Insurance Plan</label>
                  <select
                    value={planId}
                    onChange={(e) => setPlanId(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-[#D8E5DC] rounded-xl text-[#092328] font-semibold focus:outline-none focus:border-[#2A835F]"
                  >
                    {PLAN_OPTIONS.map((opt) => (
                      <option key={opt.id} value={opt.id}>
                        {opt.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-[#092328]">Member / Policy ID</label>
                  <input
                    type="text"
                    value={memberRef}
                    onChange={(e) => setMemberRef(e.target.value)}
                    placeholder="e.g. M-88219"
                    className="w-full px-3 py-2 bg-white border border-[#D8E5DC] rounded-xl font-mono text-[#092328] focus:outline-none focus:border-[#2A835F]"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-[#092328]">
                    Group Number <span className="font-normal text-[#12544F]/60">(optional)</span>
                  </label>
                  <input
                    type="text"
                    value={groupNumber}
                    onChange={(e) => setGroupNumber(e.target.value)}
                    placeholder="e.g. GRP-40291"
                    className="w-full px-3 py-2 bg-white border border-[#D8E5DC] rounded-xl font-mono text-[#092328] focus:outline-none focus:border-[#2A835F]"
                  />
                </div>
              </div>
            )}

            {/* TAB 2: Upload Insurance Card */}
            {insuranceMode === 'card' && (
              <div className="space-y-3 pt-1">
                {!isCardScanned ? (
                  <div className="border-2 border-dashed border-[#D8E5DC] hover:border-[#2A835F]/60 rounded-2xl p-4 text-center bg-white transition-colors">
                    {isScanningCard ? (
                      <div className="py-4 space-y-2">
                        <div className="inline-block animate-spin h-6 w-6 border-2 border-[#12544F] border-t-transparent rounded-full" />
                        <p className="text-xs font-bold text-[#092328]">
                          Scanning insurance card OCR tokens...
                        </p>
                        <p className="text-[11px] text-[#12544F]/70">
                          Extracting Issuer, Member ID, RxBIN, and Group Number
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <div className="text-2xl text-[#12544F]/50">🪪</div>
                        <p className="text-xs font-bold text-[#092328]">
                          Upload Front of Insurance Card
                        </p>
                        <p className="text-[11px] text-[#12544F]/70">
                          Drag and drop photo or scan (PNG, JPG, PDF)
                        </p>
                        <div className="flex items-center justify-center space-x-2 pt-1">
                          <label className="px-3 py-1.5 bg-[#092328] hover:bg-[#12544F] text-white font-bold rounded-xl cursor-pointer transition-colors text-xs">
                            Browse File
                            <input
                              type="file"
                              accept="image/*,.pdf"
                              onChange={handleFileUpload}
                              className="hidden"
                            />
                          </label>
                          <span className="text-[#12544F]/50">or</span>
                          <button
                            type="button"
                            onClick={() => handleSimulateCardScan()}
                            className="px-3 py-1.5 bg-[#F0F5F2] hover:bg-[#EAEFEA] text-[#12544F] font-bold rounded-xl cursor-pointer transition-colors text-xs border border-[#D8E5DC]"
                          >
                            Scan Sample Card
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  /* Scanned Card Preview Pill */
                  <div className="p-3.5 bg-gradient-to-r from-[#F0F5F2] to-[#E8F3EC] border border-[#2A835F]/30 rounded-2xl space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className="h-2 w-2 rounded-full bg-[#2A835F] animate-pulse" />
                        <span className="text-xs font-bold text-[#2A835F]">
                          Card Scanned & Verified via OCR
                        </span>
                        <span className="text-[10px] text-[#12544F]/60">
                          ({cardFileName})
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={handleResetCard}
                        className="text-[11px] font-bold text-[#DC2626] hover:underline cursor-pointer"
                      >
                        Remove card
                      </button>
                    </div>

                    {/* Card Mockup Visual */}
                    <div className="bg-white p-3 rounded-xl border border-[#D8E5DC] shadow-xs grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                      <div>
                        <span className="text-[#12544F]/60 block text-[10px]">Issuer</span>
                        <span className="font-bold text-[#092328]">{insurerName}</span>
                      </div>
                      <div>
                        <span className="text-[#12544F]/60 block text-[10px]">Plan</span>
                        <span className="font-mono font-bold text-[#092328]">{planId}</span>
                      </div>
                      <div>
                        <span className="text-[#12544F]/60 block text-[10px]">Member ID</span>
                        <span className="font-mono font-bold text-[#092328]">{memberRef}</span>
                      </div>
                      <div>
                        <span className="text-[#12544F]/60 block text-[10px]">Group #</span>
                        <span className="font-mono font-bold text-[#092328]">{groupNumber}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* SECTION 2: Clinical Details */}
          <div className="space-y-3">
            {/* Specialty */}
            <div className="space-y-1">
              <label className="font-bold text-[#092328]">Specialty</label>
              <select
                value={specialty}
                onChange={(e) => setSpecialty(e.target.value)}
                className="w-full px-3 py-2 bg-[#F0F5F2] border border-[#D8E5DC] rounded-xl text-[#092328] font-semibold focus:outline-none"
              >
                <option value="Cardiology">Cardiology</option>
                <option value="Oncology">Oncology</option>
                <option value="Orthopedics">Orthopedics</option>
                <option value="Neurology">Neurology</option>
                <option value="Gastroenterology">Gastroenterology</option>
              </select>
            </div>

            {/* Item Name & Code */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="font-bold text-[#092328]">Item Name</label>
                <input
                  type="text"
                  value={itemName}
                  onChange={(e) => setItemName(e.target.value)}
                  placeholder="e.g. Drug A or Major Joint Procedure"
                  className="w-full px-3 py-2 border border-[#D8E5DC] rounded-xl text-[#092328] focus:outline-none focus:border-[#2A835F]"
                  required
                />
              </div>
              <div className="space-y-1">
                <label className="font-bold text-[#092328]">Item Code</label>
                <input
                  type="text"
                  value={itemCode}
                  onChange={(e) => setItemCode(e.target.value)}
                  placeholder="e.g. DRUG-A or PROC-1"
                  className="w-full px-3 py-2 border border-[#D8E5DC] rounded-xl font-mono text-[#092328] focus:outline-none focus:border-[#2A835F]"
                  required
                />
              </div>
            </div>

            {/* Patient File Text */}
            <div className="space-y-1">
              <label className="font-bold text-[#092328]">Patient Clinical File</label>
              <textarea
                rows={3}
                value={patientText}
                onChange={(e) => setPatientText(e.target.value)}
                placeholder="Paste patient clinical summary, diagnosis, or chart notes..."
                className="w-full px-3 py-2 border border-[#D8E5DC] rounded-xl text-[#092328] focus:outline-none focus:border-[#2A835F]"
                required
              />
            </div>

            {/* Prescription Notes */}
            <div className="space-y-1">
              <label className="font-bold text-[#092328]">Prescription / Orders</label>
              <textarea
                rows={2}
                value={prescriptionText}
                onChange={(e) => setPrescriptionText(e.target.value)}
                placeholder="Prescription dosage, procedure code, or required documentation notes..."
                className="w-full px-3 py-2 border border-[#D8E5DC] rounded-xl text-[#092328] focus:outline-none focus:border-[#2A835F]"
              />
            </div>

            {/* Prior Approval Reference */}
            <div className="space-y-1">
              <label className="font-bold text-[#092328]">
                Prior Approval Reference <span className="font-normal text-[#12544F]/60">(optional)</span>
              </label>
              <input
                type="text"
                value={priorApprovalRef}
                onChange={(e) => setPriorApprovalRef(e.target.value)}
                placeholder="e.g. PA-9901 or leave blank if pending"
                className="w-full px-3 py-2 border border-[#D8E5DC] rounded-xl font-mono text-[#092328] focus:outline-none focus:border-[#2A835F]"
              />
            </div>
          </div>

          {/* Action buttons */}
          <div className="pt-2 flex justify-end space-x-2 border-t border-[#EAEFEA]">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-[#12544F]/80 hover:bg-[#F0F5F2] font-semibold transition-all cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 rounded-xl bg-[#092328] hover:bg-[#12544F] text-white font-bold transition-all shadow-sm cursor-pointer disabled:opacity-50"
            >
              {isSubmitting ? 'Evaluating Coverage...' : 'Check Coverage'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
