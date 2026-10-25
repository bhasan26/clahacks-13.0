import React, { useState, useRef } from 'react';
import {
  ExtractedDocumentResult,
  ProposedPolicyChange,
  PolicyDiff,
  ImpactPreviewResult,
} from '../types';
import {
  extractPolicyDocument,
  previewPolicyImpact,
  approvePolicyProposal,
  rejectPolicyProposal,
} from '../api';

interface PolicyIntelligenceProps {
  onPolicyApproved?: (affectedCaseIds: string[]) => void;
  onNavigateToCases?: (caseIds: string[]) => void;
}

export const PolicyIntelligence: React.FC<PolicyIntelligenceProps> = ({
  onPolicyApproved,
  onNavigateToCases,
}) => {
  // Input & Upload State
  const [activeInputTab, setActiveInputTab] = useState<'upload' | 'paste' | 'preset'>('preset');
  const [pastedText, setPastedText] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Processing & Loading
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionProgressStep, setExtractionProgressStep] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Extracted Document State
  const [docResult, setDocResult] = useState<ExtractedDocumentResult | null>(null);
  const [activeProposalIndex, setActiveProposalIndex] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [highlightedQuote, setHighlightedQuote] = useState<string | null>(null);

  // Editable fields for human review
  const [editedTitle, setEditedTitle] = useState('');
  const [editedCode, setEditedCode] = useState('');
  const [editedName, setEditedName] = useState('');
  const [editedEffect, setEditedEffect] = useState<'covered' | 'excluded' | 'requires_prior_approval' | 'requires_documents'>('excluded');
  const [editedEffectiveDate, setEditedEffectiveDate] = useState('');
  const [reviewerNotes, setReviewerNotes] = useState('');

  // What-If Simulator & Approval
  const [impactResult, setImpactResult] = useState<ImpactPreviewResult | null>(null);
  const [isPreviewingImpact, setIsPreviewingImpact] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [approvalSuccess, setApprovalSuccess] = useState<{
    ruleId: string;
    version: number;
    affectedCaseIds: string[];
    message: string;
  } | null>(null);

  // Demo Preset Texts for 1-Click presentation
  const DEMO_PRESETS = [
    {
      id: 'docA',
      title: 'Demo Notice A — Drug A Exclusion',
      subtitle: 'Excludes DRUG-A effective Nov 1, 2026',
      badge: 'New Exclusion',
      badgeColor: 'bg-red-50 text-red-700 border-red-200',
      text: `DEMO INSURANCE CO. — OFFICIAL POLICY BULLETIN
Bulletin Ref: 2026-1042-V2 | Date: October 24, 2026

TO: In-Network Hospital Providers & Claims Administration
FROM: Commercial Formulary Pharmacy & Therapeutics Committee
SUBJECT: Coverage Exclusion for Drug A (DRUG-A)

POLICY UPDATE NOTICE (SYNTHETIC TEST FIXTURE):
Beginning November 1, 2026, PLAN-GOLD will no longer cover DRUG-A.
This coverage exclusion applies to all outpatient hospital claims with date of service on or after November 1, 2026.

AFFECTED BENEFITS:
Insurer: Demo Insurance Co.
Benefit Plan: PLAN-GOLD Commercial Comprehensive
Target Drug: Drug A (HCPCS Code: DRUG-A)
Prior Coverage Status: Covered
New Coverage Status: Excluded / Non-Covered
Effective Date: November 1, 2026

CLAIMS ADJUDICATION INSTRUCTIONS:
Claims submitted for DRUG-A on or after November 1, 2026 will be rejected under adjustment reason code CO-96 (Non-covered charge). Hospital claims officers should review with the ordering physician before submitting.`,
    },
    {
      id: 'docB',
      title: 'Demo Notice B — Delayed Exclusion',
      subtitle: 'Postpones exclusion to Dec 1, 2026',
      badge: 'Delayed Rule',
      badgeColor: 'bg-amber-50 text-amber-700 border-amber-200',
      text: `DEMO INSURANCE CO. — POLICY REVISION & POSTPONEMENT
Bulletin Ref: 2026-1042-DELAY | Date: October 26, 2026

TO: Hospital Billing Departments & Clinical Claims Officers
FROM: Office of the Chief Medical Officer
SUBJECT: Temporary Delay of Coverage Exclusion for Drug A

POLICY REVISION NOTICE (SYNTHETIC TEST FIXTURE):
In response to provider network feedback and transitional care continuity, the previously announced coverage exclusion for DRUG-A is postponed until December 1, 2026.

REVISED TERMS:
Insurer: Demo Insurance Co.
Benefit Plan: PLAN-GOLD
Target Drug: Drug A (DRUG-A)
Original Effective Date: November 1, 2026 (Superseded)
New Delayed Effective Date: December 1, 2026

INTERIM COVERAGE ADJUDICATION:
Claims with service dates between November 1, 2026 and November 30, 2026 will continue to be covered under existing formulary terms. The non-coverage rule will take effect strictly on services rendered December 1, 2026 and onward.`,
    },
    {
      id: 'docC',
      title: 'Demo Notice C — Joint Prior Authorization',
      subtitle: 'Mandates prior auth for PROC-1 from Dec 15',
      badge: 'Prior Auth Mandate',
      badgeColor: 'bg-blue-50 text-blue-700 border-blue-200',
      text: `DEMO INSURANCE CO. — MEDICAL MANAGEMENT CIRCULAR
Circular Ref: 2026-202-V2 | Date: October 24, 2026

TO: Orthopedic Surgery Departments & Hospital Utilization Management
FROM: Utilization Review & Precertification Committee
SUBJECT: Mandatory Prior Authorization for Major Joint Procedures

CLINICAL POLICY UPDATE (SYNTHETIC TEST FIXTURE):
Prior authorization is mandatory for Major Joint Procedure (PROC-1) effective December 15, 2026.

CLINICAL MANDATE DETAILS:
Insurer: Demo Insurance Co.
Applicable Plans: PLAN-GOLD
Procedure Code: PROC-1 (Major Joint Procedure)
New Requirement: Pre-service clinical authorization from insurer
Effective Date: December 15, 2026

REQUIRED DOCUMENTATION:
1. Clinical notes documenting conservative therapy trial.
2. Diagnostic radiology report (X-ray or MRI).
3. Prior authorization confirmation reference code.
Submissions without an approved authorization reference will be rejected under code CO-197.`,
    },
  ];

  // Helper to initialize edit fields from proposal
  const loadProposalIntoForm = (p: ProposedPolicyChange) => {
    setEditedTitle(p.policy_title);
    setEditedCode(p.target_code);
    setEditedName(p.target_name || p.target_code);
    setEditedEffect(p.proposed_effect);
    setEditedEffectiveDate(p.effective_from || '2026-11-01');
    setReviewerNotes(p.reviewer_notes || '');
    setHighlightedQuote(p.supporting_quote);
    setCurrentPage(p.source_page || 1);
  };

  // Run Extraction
  const handleRunExtraction = async (options: { file?: File; text?: string; filename?: string }) => {
    setIsExtracting(true);
    setErrorMessage(null);
    setApprovalSuccess(null);
    setImpactResult(null);

    try {
      setExtractionProgressStep('Validating document format and extracting selectable text...');
      await new Promise((r) => setTimeout(r, 200));

      setExtractionProgressStep('Executing Gemini multimodal policy extraction and citation grounding...');
      const result = await extractPolicyDocument(options);

      setExtractionProgressStep('Verifying supporting quotations and computing policy diff...');
      await new Promise((r) => setTimeout(r, 250));

      setDocResult(result);
      if (result.proposals && result.proposals.length > 0) {
        setActiveProposalIndex(0);
        loadProposalIntoForm(result.proposals[0]);
      }
      if (result.impact_preview) {
        setImpactResult(result.impact_preview);
      }
    } catch (err: any) {
      console.error('Extraction failed:', err);
      setErrorMessage(err.message || 'Failed to extract policy rules from document.');
    } finally {
      setIsExtracting(false);
      setExtractionProgressStep('');
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setSelectedFile(file);
      handleRunExtraction({ file });
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      handleRunExtraction({ file });
    }
  };

  // What-If Simulation
  const handlePreviewImpact = async () => {
    if (!docResult || !docResult.proposals[activeProposalIndex]) return;
    setIsPreviewingImpact(true);
    setErrorMessage(null);
    try {
      const currentProp = {
        ...docResult.proposals[activeProposalIndex],
        policy_title: editedTitle,
        target_code: editedCode,
        target_name: editedName,
        proposed_effect: editedEffect,
        effective_from: editedEffectiveDate,
      };
      const preview = await previewPolicyImpact([currentProp]);
      setImpactResult(preview);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to calculate claim impact preview.');
    } finally {
      setIsPreviewingImpact(false);
    }
  };

  // Human Approval
  const handleApprove = async () => {
    if (!docResult || !docResult.proposals[activeProposalIndex]) return;
    const prop = docResult.proposals[activeProposalIndex];
    setIsApproving(true);
    setErrorMessage(null);
    try {
      const editedFields = {
        policy_title: editedTitle,
        target_code: editedCode,
        target_name: editedName,
        proposed_effect: editedEffect,
        effective_from: editedEffectiveDate,
      };

      const res = await approvePolicyProposal(prop.proposal_id, reviewerNotes, editedFields);
      setApprovalSuccess({
        ruleId: res.rule.rule_id,
        version: res.rule.version,
        affectedCaseIds: res.affected_case_ids,
        message: res.message,
      });

      if (onPolicyApproved) {
        onPolicyApproved(res.affected_case_ids);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to approve policy proposal.');
    } finally {
      setIsApproving(false);
    }
  };

  // Human Rejection
  const handleReject = async () => {
    if (!docResult || !docResult.proposals[activeProposalIndex]) return;
    const prop = docResult.proposals[activeProposalIndex];
    try {
      await rejectPolicyProposal(prop.proposal_id, reviewerNotes || 'Rejected by hospital claims reviewer.');
      const updated = { ...docResult };
      updated.proposals[activeProposalIndex].review_state = 'rejected';
      setDocResult(updated);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to reject proposal.');
    }
  };

  const activeProposal = docResult?.proposals[activeProposalIndex];
  const activeDiff = docResult?.diffs.find((d) => d.proposal_id === activeProposal?.proposal_id);

  return (
    <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E8EFEA]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full bg-[#EBF4EE] text-[#2A835F] text-[11px] font-black uppercase tracking-wider border border-[#D5E2D9]">
              Multimodal Policy Intelligence
            </span>
            <span className="text-xs text-[#698579] font-medium">AI Extracts · Code Decides · Humans Approve</span>
          </div>
          <h1 className="text-2xl font-black text-[#092328] tracking-tight">
            Autonomous Policy Ingestion & Claim Impact Sentinel
          </h1>
          <p className="text-xs text-[#698579] mt-0.5 max-w-3xl">
            Upload an insurer circular, scanned letter, or clinical policy notice. Gemini extracts proposed coverage rules
            with verifiable evidence citations. Preview which pending hospital claims are at risk before explicitly approving changes.
          </p>
        </div>

        {docResult && (
          <button
            onClick={() => {
              setDocResult(null);
              setSelectedFile(null);
              setApprovalSuccess(null);
              setImpactResult(null);
            }}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl border border-[#D5E2D9] text-[#092328] text-xs font-bold hover:bg-[#F0F5F2] transition-colors cursor-pointer shrink-0"
          >
            <svg className="w-4 h-4 text-[#698579]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>Upload Another Document</span>
          </button>
        )}
      </div>

      {/* Error Message Alert */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-900 text-xs flex items-start gap-3">
          <svg className="w-5 h-5 text-red-600 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <div className="font-bold">Extraction or Processing Warning</div>
            <p className="mt-0.5">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Approval Success Banner */}
      {approvalSuccess && (
        <div className="p-4 rounded-xl bg-[#EBF4EE] border border-[#2A835F]/40 text-[#092328] text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-in fade-in duration-200">
          <div className="flex items-center gap-3">
            <span className="w-8 h-8 rounded-full bg-[#2A835F] text-white flex items-center justify-center font-bold text-sm shrink-0">
              ✓
            </span>
            <div>
              <div className="font-bold text-sm text-[#2A835F]">
                Policy Activated: Rule {approvalSuccess.ruleId} v{approvalSuccess.version}
              </div>
              <p className="text-[#12544F] mt-0.5">
                {approvalSuccess.message} ({approvalSuccess.affectedCaseIds.length} open claims transitioned to Needs attention).
              </p>
            </div>
          </div>
          {onNavigateToCases && approvalSuccess.affectedCaseIds.length > 0 && (
            <button
              onClick={() => onNavigateToCases(approvalSuccess.affectedCaseIds)}
              className="px-4 py-2 rounded-xl bg-[#092328] hover:bg-[#133E46] text-white text-xs font-bold transition-colors cursor-pointer shrink-0"
            >
              View Affected Claims ({approvalSuccess.affectedCaseIds.length}) →
            </button>
          )}
        </div>
      )}

      {/* SECTION 1: DOCUMENT INPUT WORKSPACE (When no document is active) */}
      {!docResult && (
        <div className="bg-white rounded-2xl border border-[#D5E2D9] p-6 shadow-sm space-y-6">
          {/* Navigation Tabs between Presets, File Upload, Text Paste */}
          <div className="flex items-center gap-2 border-b border-[#E8EFEA] pb-3">
            <button
              onClick={() => setActiveInputTab('preset')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeInputTab === 'preset'
                  ? 'bg-[#092328] text-white shadow-xs'
                  : 'text-[#698579] hover:bg-[#F0F5F2]'
              }`}
            >
              Synthetic Demo Documents (1-Click)
            </button>
            <button
              onClick={() => setActiveInputTab('upload')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeInputTab === 'upload'
                  ? 'bg-[#092328] text-white shadow-xs'
                  : 'text-[#698579] hover:bg-[#F0F5F2]'
              }`}
            >
              Upload PDF or Image
            </button>
            <button
              onClick={() => setActiveInputTab('paste')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeInputTab === 'paste'
                  ? 'bg-[#092328] text-white shadow-xs'
                  : 'text-[#698579] hover:bg-[#F0F5F2]'
              }`}
            >
              Paste Policy Circular Text
            </button>
          </div>

          {/* TAB 1: 1-Click Demo Presets */}
          {activeInputTab === 'preset' && (
            <div className="space-y-4">
              <div className="text-xs text-[#698579]">
                Select one of the 3 hackathon synthetic policy documents to test the complete end-to-end workflow:
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {DEMO_PRESETS.map((p) => (
                  <div
                    key={p.id}
                    className="p-4 rounded-xl border border-[#D5E2D9] bg-[#F8FAF9] hover:border-[#2A835F] hover:bg-white transition-all flex flex-col justify-between space-y-3 cursor-pointer group"
                    onClick={() => handleRunExtraction({ text: p.text, filename: `${p.id}.txt` })}
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${p.badgeColor}`}>
                          {p.badge}
                        </span>
                        <span className="text-[11px] text-[#698579] font-mono">demo</span>
                      </div>
                      <h4 className="font-bold text-sm text-[#092328] group-hover:text-[#2A835F] transition-colors">
                        {p.title}
                      </h4>
                      <p className="text-xs text-[#698579] leading-relaxed">
                        {p.subtitle}
                      </p>
                    </div>
                    <button
                      type="button"
                      disabled={isExtracting}
                      className="w-full py-2 px-3 rounded-lg bg-[#092328] text-white text-xs font-bold group-hover:bg-[#2A835F] transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <span>Ingest & Extract</span>
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 2: File Upload (Drag & Drop, PDF, PNG, JPG, WebP) */}
          {activeInputTab === 'upload' && (
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleFileDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`p-10 border-2 border-dashed rounded-2xl flex flex-col items-center justify-center text-center transition-all cursor-pointer ${
                isDragging
                  ? 'border-[#2A835F] bg-[#EBF4EE]'
                  : 'border-[#D5E2D9] bg-[#F8FAF9] hover:bg-[#F2F7F4] hover:border-[#2A835F]'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,image/png,image/jpeg,image/webp,text/plain"
                onChange={handleFileSelect}
                className="hidden"
              />
              <div className="w-14 h-14 rounded-2xl bg-white border border-[#D5E2D9] text-[#2A835F] flex items-center justify-center shadow-xs mb-3">
                <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <div className="font-bold text-sm text-[#092328]">
                {selectedFile ? selectedFile.name : 'Drag & drop insurance policy document here'}
              </div>
              <p className="text-xs text-[#698579] mt-1 max-w-sm">
                Supports PDF (selectable or scanned), PNG, JPEG, and WebP up to 10 MB.
              </p>
              <button
                type="button"
                className="mt-4 px-4 py-2 rounded-xl bg-white border border-[#D5E2D9] text-[#092328] text-xs font-bold hover:bg-[#E8EFEA] transition-colors"
              >
                Browse Files
              </button>
            </div>
          )}

          {/* TAB 3: Text Paste */}
          {activeInputTab === 'paste' && (
            <div className="space-y-3">
              <label className="block text-xs font-bold text-[#092328]">
                Paste Policy Circular or Insurer Letter Text
              </label>
              <textarea
                rows={8}
                value={pastedText}
                onChange={(e) => setPastedText(e.target.value)}
                placeholder="Paste insurer policy notice, coverage circular, or formulary announcement text here..."
                className="w-full p-3.5 rounded-xl border border-[#D5E2D9] font-mono text-xs focus:ring-2 focus:ring-[#2A835F] focus:outline-hidden"
              />
              <button
                type="button"
                disabled={!pastedText.trim() || isExtracting}
                onClick={() => handleRunExtraction({ text: pastedText, filename: 'pasted_notice.txt' })}
                className="px-5 py-2.5 rounded-xl bg-[#092328] text-white text-xs font-bold hover:bg-[#133E46] transition-colors disabled:opacity-50 cursor-pointer"
              >
                Run AI Extraction
              </button>
            </div>
          )}

          {/* Extraction Loading Overlay */}
          {isExtracting && (
            <div className="p-8 rounded-xl bg-[#F8FAF9] border border-[#D5E2D9] flex flex-col items-center justify-center space-y-3 text-center">
              <div className="w-8 h-8 border-3 border-[#2A835F] border-t-transparent rounded-full animate-spin" />
              <div className="text-sm font-bold text-[#092328]">Processing Policy Document...</div>
              <p className="text-xs text-[#698579] max-w-md">{extractionProgressStep}</p>
            </div>
          )}
        </div>
      )}

      {/* SECTION 2: TWO-COLUMN REVIEW WORKSPACE (When document is extracted) */}
      {docResult && activeProposal && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* LEFT COLUMN: ORIGINAL DOCUMENT & EVIDENCE VIEWER (5 cols) */}
          <div className="lg:col-span-5 bg-white rounded-2xl border border-[#D5E2D9] p-5 shadow-sm space-y-4 sticky top-6">
            <div className="flex items-center justify-between border-b border-[#E8EFEA] pb-3">
              <div className="flex items-center gap-2">
                <span className="w-7 h-7 rounded-lg bg-[#EBF4EE] text-[#2A835F] flex items-center justify-center font-bold text-xs">
                  📄
                </span>
                <div>
                  <h3 className="font-bold text-xs text-[#092328] truncate max-w-[220px]">
                    {docResult.filename}
                  </h3>
                  <span className="text-[11px] text-[#698579]">
                    Page {currentPage} of {docResult.page_count} · {docResult.file_type.toUpperCase()}
                  </span>
                </div>
              </div>

              {/* Page Navigation */}
              {docResult.page_count > 1 && (
                <div className="flex items-center gap-1.5 text-xs">
                  <button
                    disabled={currentPage <= 1}
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    className="p-1 rounded bg-[#F0F5F2] disabled:opacity-40"
                  >
                    ‹
                  </button>
                  <span className="font-bold text-xs text-[#092328]">{currentPage}</span>
                  <button
                    disabled={currentPage >= docResult.page_count}
                    onClick={() => setCurrentPage((p) => Math.min(docResult.page_count, p + 1))}
                    className="p-1 rounded bg-[#F0F5F2] disabled:opacity-40"
                  >
                    ›
                  </button>
                </div>
              )}
            </div>

            {/* Document Preview (Rendered Image or Selectable Text) */}
            <div className="rounded-xl border border-[#D5E2D9] bg-[#F8FAF9] p-4 max-h-[460px] overflow-y-auto font-mono text-xs leading-relaxed text-[#092328]">
              {docResult.pages_text[currentPage - 1]?.preview_image ? (
                <div className="space-y-3">
                  <img
                    src={docResult.pages_text[currentPage - 1].preview_image!}
                    alt={`Page ${currentPage}`}
                    className="w-full rounded shadow-xs border border-gray-200"
                  />
                  {docResult.pages_text[currentPage - 1].text && (
                    <div className="pt-2 border-t border-gray-200 text-[11px] whitespace-pre-wrap">
                      {docResult.pages_text[currentPage - 1].text}
                    </div>
                  )}
                </div>
              ) : (
                <div className="whitespace-pre-wrap text-[11.5px] leading-relaxed">
                  {docResult.pages_text[currentPage - 1]?.text || docResult.raw_text}
                </div>
              )}
            </div>

            {/* Verified Quotation Highlight Callout */}
            {highlightedQuote && (
              <div className="p-3.5 rounded-xl bg-[#FFFDF5] border border-[#FDE68A] space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800 flex items-center gap-1">
                    <span>Supporting Evidence Quotation</span>
                  </span>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800">
                    Source Page {activeProposal.source_page || 1}
                  </span>
                </div>
                <blockquote className="text-xs text-amber-950 font-medium italic border-l-2 border-amber-400 pl-2.5">
                  "{highlightedQuote}"
                </blockquote>
              </div>
            )}
          </div>

          {/* RIGHT COLUMN: POLICY DIFFERENCE & HUMAN REVIEW FORM (7 cols) */}
          <div className="lg:col-span-7 bg-white rounded-2xl border border-[#D5E2D9] p-6 shadow-sm space-y-5">
            {/* Policy Diff Banner */}
            {activeDiff && (
              <div
                className={`p-4 rounded-xl border flex items-start gap-3 ${
                  activeDiff.is_delay
                    ? 'bg-amber-50/70 border-amber-300 text-amber-900'
                    : activeDiff.change_category === 'coverage_restriction'
                    ? 'bg-red-50/70 border-red-300 text-red-900'
                    : 'bg-[#EBF4EE] border-[#2A835F]/40 text-[#092328]'
                }`}
              >
                <div className="w-8 h-8 rounded-lg bg-white/90 border border-current/20 flex items-center justify-center font-bold text-sm shrink-0">
                  {activeDiff.is_delay ? '⏳' : activeDiff.is_cancellation ? '✕' : '⚠️'}
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold uppercase tracking-wider">
                      Policy Difference Engine
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-white/80 border border-current/30">
                      {activeDiff.change_category.replace('_', ' ').toUpperCase()}
                    </span>
                  </div>
                  <p className="text-xs font-semibold leading-relaxed">
                    {activeDiff.diff_summary}
                  </p>
                </div>
              </div>
            )}

            {/* Validation Warnings */}
            {activeProposal.validation_warnings.length > 0 && (
              <div className="p-3.5 rounded-xl bg-[#FFFDF5] border border-amber-200 space-y-1 text-xs text-amber-900">
                <div className="font-bold flex items-center gap-1.5">
                  <svg className="w-4 h-4 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <span>Verification Warnings (Human Confirmation Required):</span>
                </div>
                <ul className="list-disc pl-5 space-y-0.5 text-[11px]">
                  {activeProposal.validation_warnings.map((w, idx) => (
                    <li key={idx}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Editable Form Fields for Reviewer Approval */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-black uppercase tracking-wider text-[#092328]">
                  Extracted Policy Details (Review & Correct Before Approval)
                </h3>
                <span className="text-[11px] text-[#698579]">
                  Proposal ID: <span className="font-mono font-bold">{activeProposal.proposal_id}</span>
                </span>
              </div>

              {/* Title & Ref */}
              <div>
                <label className="block text-[11px] font-bold text-[#698579] mb-1">
                  Policy Title
                </label>
                <input
                  type="text"
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-[#D5E2D9] text-xs font-bold text-[#092328] focus:ring-2 focus:ring-[#2A835F] focus:outline-hidden"
                />
              </div>

              {/* Insurer & Plan */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-[#698579] mb-1">
                    Insurer
                  </label>
                  <input
                    type="text"
                    disabled
                    value={activeProposal.insurer_name}
                    className="w-full px-3 py-2 rounded-xl border border-[#E8EFEA] bg-[#F8FAF9] text-xs text-[#092328] font-semibold"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-[#698579] mb-1">
                    Plan Scope
                  </label>
                  <input
                    type="text"
                    disabled
                    value={activeProposal.plan_ids.join(', ') || 'All Commercial (*)'}
                    className="w-full px-3 py-2 rounded-xl border border-[#E8EFEA] bg-[#F8FAF9] text-xs text-[#092328] font-semibold"
                  />
                </div>
              </div>

              {/* Clinical Target & Code */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-[#698579] mb-1">
                    Target Code (CPT/HCPCS/ID)
                  </label>
                  <input
                    type="text"
                    value={editedCode}
                    onChange={(e) => setEditedCode(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-[#D5E2D9] text-xs font-mono font-bold text-[#092328] focus:ring-2 focus:ring-[#2A835F] focus:outline-hidden"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-[#698579] mb-1">
                    Clinical Target Name
                  </label>
                  <input
                    type="text"
                    value={editedName}
                    onChange={(e) => setEditedName(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-[#D5E2D9] text-xs font-bold text-[#092328] focus:ring-2 focus:ring-[#2A835F] focus:outline-hidden"
                  />
                </div>
              </div>

              {/* Proposed Coverage Effect & Effective Date */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-[#698579] mb-1">
                    Proposed Coverage Mandate
                  </label>
                  <select
                    value={editedEffect}
                    onChange={(e) => setEditedEffect(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-xl border border-[#D5E2D9] text-xs font-bold text-[#092328] focus:ring-2 focus:ring-[#2A835F] focus:outline-hidden"
                  >
                    <option value="excluded">Non-Covered / Excluded</option>
                    <option value="requires_prior_approval">Requires Prior Authorization</option>
                    <option value="requires_documents">Requires Clinical Documentation</option>
                    <option value="covered">Covered Standard Benefit</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-[#698579] mb-1">
                    Effective Date
                  </label>
                  <input
                    type="date"
                    value={editedEffectiveDate}
                    onChange={(e) => setEditedEffectiveDate(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-[#D5E2D9] text-xs font-bold text-[#092328] focus:ring-2 focus:ring-[#2A835F] focus:outline-hidden"
                  />
                </div>
              </div>

              {/* Reviewer Notes */}
              <div>
                <label className="block text-[11px] font-bold text-[#698579] mb-1">
                  Claims Officer Review Notes (Recorded in Audit Trail)
                </label>
                <input
                  type="text"
                  value={reviewerNotes}
                  onChange={(e) => setReviewerNotes(e.target.value)}
                  placeholder="e.g. Verified against Payer Bulletin 2026-1042; reviewed with pharmacy committee."
                  className="w-full px-3 py-2 rounded-xl border border-[#D5E2D9] text-xs text-[#092328] focus:ring-2 focus:ring-[#2A835F] focus:outline-hidden"
                />
              </div>
            </div>

            {/* Action Bar: What-If Preview vs Approve */}
            <div className="pt-4 border-t border-[#E8EFEA] flex flex-wrap items-center justify-between gap-3">
              <button
                type="button"
                disabled={isPreviewingImpact}
                onClick={handlePreviewImpact}
                className="px-4 py-2.5 rounded-xl border border-[#2A835F] bg-[#EBF4EE] hover:bg-[#DDF0E3] text-[#2A835F] text-xs font-bold transition-colors flex items-center gap-2 cursor-pointer shadow-2xs"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <span>{isPreviewingImpact ? 'Simulating...' : 'Preview Claim Impact (What-If)'}</span>
              </button>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleReject}
                  className="px-3.5 py-2.5 rounded-xl border border-[#D5E2D9] text-[#698579] hover:text-red-700 hover:bg-red-50 text-xs font-bold transition-colors cursor-pointer"
                >
                  Reject
                </button>
                <button
                  type="button"
                  disabled={isApproving || activeProposal.review_state === 'approved'}
                  onClick={handleApprove}
                  className="px-5 py-2.5 rounded-xl bg-[#092328] hover:bg-[#2A835F] text-white text-xs font-black transition-all shadow-md cursor-pointer disabled:opacity-50 flex items-center gap-2"
                >
                  {isApproving ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Activating...</span>
                    </>
                  ) : activeProposal.review_state === 'approved' ? (
                    <span>✓ Policy Approved</span>
                  ) : (
                    <span>Approve & Apply Policy →</span>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 3: WHAT-IF IMPACT PREVIEW BREAKDOWN (When impactResult is available) */}
      {impactResult && (
        <div className="bg-white rounded-2xl border border-[#D5E2D9] p-6 shadow-sm space-y-5 animate-in fade-in duration-150">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E8EFEA] pb-4">
            <div>
              <span className="text-[11px] font-black uppercase tracking-wider text-[#2A835F]">
                Deterministic Simulation Result
              </span>
              <h3 className="text-base font-bold text-[#092328]">
                Hospital Caseload What-If Claim Impact
              </h3>
            </div>
            <span className="text-xs text-[#698579]">
              Evaluated across <span className="font-bold text-[#092328]">{impactResult.total_cases_checked} open hospital claims</span>
            </span>
          </div>

          {/* KPI Summary Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3.5 rounded-xl bg-[#F8FAF9] border border-[#E8EFEA]">
              <span className="block text-[11px] text-[#698579] font-medium">Claims Evaluated</span>
              <span className="text-xl font-black text-[#092328]">{impactResult.total_cases_checked}</span>
            </div>
            <div className={`p-3.5 rounded-xl border ${impactResult.affected_cases > 0 ? 'bg-amber-50 border-amber-200 text-amber-900' : 'bg-[#EBF4EE] border-[#2A835F]/30 text-[#2A835F]'}`}>
              <span className="block text-[11px] font-medium">Potentially Affected</span>
              <span className="text-xl font-black">{impactResult.affected_cases}</span>
            </div>
            <div className={`p-3.5 rounded-xl border ${impactResult.new_risks > 0 ? 'bg-red-50 border-red-200 text-red-900' : 'bg-[#F8FAF9] border-[#E8EFEA] text-[#092328]'}`}>
              <span className="block text-[11px] font-medium">New Denial Risks</span>
              <span className="text-xl font-black">{impactResult.new_risks}</span>
            </div>
            <div className="p-3.5 rounded-xl bg-[#EBF4EE] border border-[#2A835F]/30 text-[#2A835F]">
              <span className="block text-[11px] font-medium">Unchanged Clean Claims</span>
              <span className="text-xl font-black">{impactResult.unchanged_cases}</span>
            </div>
          </div>

          {/* Affected Cases Table */}
          {impactResult.cases.length > 0 ? (
            <div className="overflow-x-auto rounded-xl border border-[#E8EFEA]">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-[#F8FAF9] border-b border-[#E8EFEA] text-[#698579] font-bold text-[11px] uppercase tracking-wider">
                    <th className="py-2.5 px-3">Case ID</th>
                    <th className="py-2.5 px-3">Specialty</th>
                    <th className="py-2.5 px-3">Service Date</th>
                    <th className="py-2.5 px-3">Prescribed Item</th>
                    <th className="py-2.5 px-3">Prior Status</th>
                    <th className="py-2.5 px-3">Simulated Status</th>
                    <th className="py-2.5 px-3">Adjudication Rationale</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E8EFEA]">
                  {impactResult.cases.map((c) => (
                    <tr key={c.case_id} className="hover:bg-[#F8FAF9] transition-colors">
                      <td className="py-2.5 px-3 font-mono font-bold text-[#092328]">
                        {c.case_id}
                      </td>
                      <td className="py-2.5 px-3 text-[#698579]">{c.specialty}</td>
                      <td className="py-2.5 px-3 font-medium text-[#092328]">
                        <span className="px-1.5 py-0.5 rounded bg-gray-100 font-mono text-[11px]">
                          {c.service_date}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-[#092328]">{c.item_name}</td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-[#EBF4EE] text-[#2A835F]">
                          {c.previous_verdict}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-900 border border-amber-300">
                          {c.simulated_verdict}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-[#698579] max-w-xs leading-relaxed">
                        {c.reason}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-6 text-center text-xs text-[#2A835F] font-bold bg-[#EBF4EE] rounded-xl border border-[#2A835F]/20">
              ✓ Clean Simulation: No open hospital claims are affected by this policy change.
            </div>
          )}
        </div>
      )}
    </div>
  );
};
