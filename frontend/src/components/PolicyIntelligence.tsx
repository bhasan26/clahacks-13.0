import React, { useState, useRef, useEffect } from 'react';
import { AlertTriangle, ArrowRight, Check, Clock, FileText, X } from 'lucide-react';
import {
  ExtractedDocumentResult,
  ProposedPolicyChange,
  PolicyDiff,
  ImpactPreviewResult,
  OfficialPolicySource,
  SourceCheckHistory,
} from '../types';
import {
  extractPolicyDocument,
  previewPolicyImpact,
  approvePolicyProposal,
  rejectPolicyProposal,
  fetchOfficialSources,
  fetchSourcesStatus,
  checkOfficialSource,
  fetchDemoMode,
  setDemoMode,
  fetchPolicyProposal,
  fetchExtractedDocument,
} from '../api';

interface PolicyIntelligenceProps {
  initialDocumentId?: string | null;
  onPolicyApproved?: (affectedCaseIds: string[]) => void;
  onNavigateToCases?: (caseIds: string[]) => void;
}

export const PolicyIntelligence: React.FC<PolicyIntelligenceProps> = ({
  onPolicyApproved,
  onNavigateToCases,
  initialDocumentId,
}) => {
  // Official Policy Source Sentinel State (Feature 8)
  const [sources, setSources] = useState<OfficialPolicySource[]>([]);
  const [sourcesStatus, setSourcesStatus] = useState<any>(null);
  const [isCheckingSource, setIsCheckingSource] = useState(false);
  const [latestSourceHistory, setLatestSourceHistory] = useState<SourceCheckHistory | null>(null);

  // Demo Mode State (FIX 2)
  const [isDemoMode, setIsDemoMode] = useState<boolean>(true);
  const [isTogglingDemo, setIsTogglingDemo] = useState(false);

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
  const [editedRegions, setEditedRegions] = useState('');
  const [editedCodeSystem, setEditedCodeSystem] = useState('');
  const [articlesVerified, setArticlesVerified] = useState(false);
  const [scopeVerified, setScopeVerified] = useState(false);
  const [editedCode, setEditedCode] = useState('');
  const [editedInsurer, setEditedInsurer] = useState('');
  const [editedPlans, setEditedPlans] = useState('');
  const [editedType, setEditedType] = useState<'drug' | 'procedure' | 'service' | ''>('');
  const [evidenceConfirmed, setEvidenceConfirmed] = useState(false);
  const [reviewToken, setReviewToken] = useState(sessionStorage.getItem('coverageguard-reviewer-token') || '');
  const [editedName, setEditedName] = useState('');
  const [editedEffect, setEditedEffect] = useState<'covered' | 'excluded' | 'requires_prior_approval' | 'requires_documents' | ''>('');
  const [editedEffectiveDate, setEditedEffectiveDate] = useState('');
  const [reviewerNotes, setReviewerNotes] = useState('');
  const [editedReference, setEditedReference] = useState('');
  const [editedQuote, setEditedQuote] = useState('');
  const [editedDiagnosisPrefixes, setEditedDiagnosisPrefixes] = useState('');

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

  useEffect(() => {
    loadSourcesAndSettings();
  }, []);

  const loadSourcesAndSettings = async () => {
    try {
      const [srcList, srcStatus, demo] = await Promise.all([
        fetchOfficialSources(),
        fetchSourcesStatus(),
        fetchDemoMode(),
      ]);
      setSources(srcList);
      setSourcesStatus(srcStatus);
      if (srcStatus?.latest_check) {
        setLatestSourceHistory(srcStatus.latest_check);
      }
      setIsDemoMode(demo.demo_mode);
    } catch (e) {
      console.error('Failed to load sources or settings:', e);
    }
  };

  const handleCheckSourceNow = async (sourceId?: string) => {
    setIsCheckingSource(true);
    setErrorMessage(null);
    try {
      const res = await checkOfficialSource(sourceId);
      setLatestSourceHistory(res);
      await loadSourcesAndSettings();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to check official policy source.');
    } finally {
      setIsCheckingSource(false);
    }
  };

  const handleToggleDemoMode = async () => {
    setIsTogglingDemo(true);
    try {
      const nextMode = !isDemoMode;
      const res = await setDemoMode(nextMode);
      setIsDemoMode(res.demo_mode);
    } catch (err: any) {
      console.error('Failed to toggle demo mode:', err);
    } finally {
      setIsTogglingDemo(false);
    }
  };

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
    setEvidenceConfirmed(p.evidence_confirmed_by_reviewer || false);
    setArticlesVerified(p.billing_articles_verified || false);
    setEditedRegions((p.jurisdictions || []).join(', '));
    setEditedCodeSystem(p.code_system || '');
    setScopeVerified(p.scope_verified ?? true);
    setEditedTitle(p.policy_title || '');
    setEditedCode(p.target_code || '');
    setEditedName(p.target_name || p.target_code || '');
    setEditedEffect(p.proposed_effect || '');
    setEditedInsurer(p.insurer_id || '');
    setEditedPlans(p.plan_ids.join(', '));
    setEditedType(p.target_type || '');
    setEditedEffectiveDate(p.effective_from || '');
    setReviewerNotes(p.reviewer_notes || '');
    setEditedReference(p.policy_reference || '');
    setEditedQuote(p.supporting_quote || '');
    setEditedDiagnosisPrefixes(((p.conditions || {}).applies_to_diagnosis_prefixes || []).join(', '));
    setHighlightedQuote(p.supporting_quote || '');
    setCurrentPage(p.source_page || 1);
  };

  useEffect(() => {
    if (!initialDocumentId) return;
    fetchExtractedDocument(initialDocumentId).then(document=>{setDocResult(document);setActiveProposalIndex(0);if(document.proposals[0])loadProposalIntoForm(document.proposals[0]);setImpactResult(document.impact_preview||null);}).catch(error=>setErrorMessage(error.message));
  }, [initialDocumentId]);

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

  // Reviewer edits beyond the extracted fields: reference, verbatim evidence and diagnosis scope.
  const reviewerScopeEdits = (p: ProposedPolicyChange) => {
    const prefixes = editedDiagnosisPrefixes.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
    const { applies_to_diagnosis_prefixes: _previous, ...otherConditions } = p.conditions || {};
    const conditions = prefixes.length ? { ...otherConditions, applies_to_diagnosis_prefixes: prefixes } : otherConditions;
    return {
      policy_reference: editedReference.trim() || null,
      supporting_quote: editedQuote.trim() || p.supporting_quote,
      conditions: Object.keys(conditions).length ? conditions : null,
    };
  };

  // What-If Simulation
  const handlePreviewImpact = async () => {
    if (!docResult || !docResult.proposals[activeProposalIndex]) return;
    setIsPreviewingImpact(true);
    setErrorMessage(null);
    try {
      const currentProp = {
        ...docResult.proposals[activeProposalIndex],
        evidence_confirmed_by_reviewer: evidenceConfirmed,
        billing_articles_verified: articlesVerified,
        scope_verified: scopeVerified,
        jurisdictions: editedRegions.split(',').map(s=>s.trim()).filter(Boolean),
        code_system: editedCodeSystem || null,
        policy_title: editedTitle,
        target_code: editedCode,
        target_name: editedName,
        insurer_id: editedInsurer,
        plan_ids: editedPlans.split(',').map(p => p.trim()).filter(Boolean),
        target_type: editedType || null,
        proposed_effect: editedEffect || null,
        effective_from: editedEffectiveDate || null,
        ...reviewerScopeEdits(docResult.proposals[activeProposalIndex]),
      };
      const preview = await previewPolicyImpact(docResult.proposals.map((p, i) => i === activeProposalIndex ? currentProp : p));
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
        evidence_confirmed_by_reviewer: evidenceConfirmed,
        billing_articles_verified: articlesVerified,
        scope_verified: scopeVerified,
        jurisdictions: editedRegions.split(',').map(s=>s.trim()).filter(Boolean),
        code_system: editedCodeSystem || null,
        policy_title: editedTitle,
        target_code: editedCode,
        target_name: editedName,
        insurer_id: editedInsurer,
        plan_ids: editedPlans.split(',').map(p => p.trim()).filter(Boolean),
        target_type: editedType || null,
        proposed_effect: editedEffect || null,
        effective_from: editedEffectiveDate || null,
        ...reviewerScopeEdits(prop),
      };

      const res = await approvePolicyProposal(prop.proposal_id, reviewerNotes, editedFields);
      setDocResult({ ...docResult, proposals: docResult.proposals.map(p => p.proposal_id === prop.proposal_id ? { ...p, review_state: 'approved', resulting_rule_id: res.rule.rule_id, resulting_rule_version: res.rule.version } : p) });
      await loadSourcesAndSettings();
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
    <div className="mx-auto max-w-6xl space-y-6 px-8 py-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-bold text-ink tracking-tight">Review a rule</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Read an insurer policy, confirm what it says (code, effect, dates, evidence), and approve it. Claims are only
            checked against approved rules.
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
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl border border-line text-ink text-xs font-bold hover:bg-sunken transition-colors cursor-pointer shrink-0"
          >
            <svg className="w-4 h-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>Upload Another Document</span>
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-4 items-center text-xs">
              <label className="text-xs">Reviewer token (if configured)
                <input aria-label="Reviewer token" type="password" value={reviewToken} onChange={e => { setReviewToken(e.target.value); sessionStorage.setItem('coverageguard-reviewer-token', e.target.value); }} className="w-full p-2 border rounded-xl" />
              </label>
        <p>Synthetic documents only. Text redaction is partial; images are not de-identified.</p>
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
        <div className="p-4 rounded-xl bg-brand-soft border border-brand/40 text-ink text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-in fade-in duration-200">
          <div className="flex items-center gap-3">
            <span className="w-8 h-8 rounded-full bg-brand text-white flex items-center justify-center shrink-0">
              <Check className="size-4" aria-hidden="true" />
            </span>
            <div>
              <div className="font-bold text-sm text-brand">
                Policy Activated: Rule {approvalSuccess.ruleId} v{approvalSuccess.version}
              </div>
              <p className="text-muted mt-0.5">
                {approvalSuccess.message} ({approvalSuccess.affectedCaseIds.length} open claims transitioned to Needs attention).
              </p>
            </div>
          </div>
          {onNavigateToCases && approvalSuccess.affectedCaseIds.length > 0 && (
            <button
              onClick={() => onNavigateToCases(approvalSuccess.affectedCaseIds)}
              className="px-4 py-2 rounded-xl bg-cta hover:bg-cta-hover text-white text-xs font-bold transition-colors cursor-pointer shrink-0"
            >
              View affected claims ({approvalSuccess.affectedCaseIds.length}) <ArrowRight className="inline size-3.5 align-[-2px]" aria-hidden="true" />
            </button>
          )}
        </div>
      )}

      <p className="text-xs text-muted">New rules found automatically appear under Insurer rules. Use this page to read a policy document and approve the rule it contains.</p>

      {/* SECTION 1: DOCUMENT INPUT WORKSPACE (When no document is active) */}
      {!docResult && (
        <div className="bg-white rounded-2xl border border-line p-6 shadow-sm space-y-6">
          {/* Navigation Tabs between Presets, File Upload, Text Paste */}
          <div className="flex items-center gap-2 border-b border-line pb-3">
            <button
              onClick={() => setActiveInputTab('preset')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeInputTab === 'preset'
                  ? 'bg-cta text-white shadow-xs'
                  : 'text-muted hover:bg-sunken'
              }`}
            >
              Demo documents
            </button>
            <button
              onClick={() => setActiveInputTab('upload')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeInputTab === 'upload'
                  ? 'bg-cta text-white shadow-xs'
                  : 'text-muted hover:bg-sunken'
              }`}
            >
              Upload PDF or Image
            </button>
            <button
              onClick={() => setActiveInputTab('paste')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeInputTab === 'paste'
                  ? 'bg-cta text-white shadow-xs'
                  : 'text-muted hover:bg-sunken'
              }`}
            >
              Paste Policy Circular Text
            </button>
          </div>

          {/* TAB 1: 1-Click Demo Presets */}
          {activeInputTab === 'preset' && (
            <div className="space-y-4">
              <div className="text-xs text-muted">
                Try one of these made-up policy notices:
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {DEMO_PRESETS.map((p) => (
                  <div
                    key={p.id}
                    className="p-4 rounded-xl border border-line bg-sunken hover:border-brand hover:bg-white transition-all flex flex-col justify-between space-y-3 cursor-pointer group"
                    onClick={() => handleRunExtraction({ text: p.text, filename: `${p.id}.txt` })}
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${p.badgeColor}`}>
                          {p.badge}
                        </span>
                        <span className="text-[11px] text-muted font-mono">demo</span>
                      </div>
                      <h4 className="font-bold text-sm text-ink group-hover:text-brand transition-colors">
                        {p.title}
                      </h4>
                      <p className="text-xs text-muted leading-relaxed">
                        {p.subtitle}
                      </p>
                    </div>
                    <button
                      type="button"
                      disabled={isExtracting}
                      className="w-full py-2 px-3 rounded-lg bg-cta text-white text-xs font-bold group-hover:bg-brand transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
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
                  ? 'border-brand bg-brand-soft'
                  : 'border-line bg-sunken hover:bg-sunken hover:border-brand'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,image/png,image/jpeg,image/webp,text/plain"
                onChange={handleFileSelect}
                className="hidden"
              />
              <div className="w-14 h-14 rounded-2xl bg-white border border-line text-brand flex items-center justify-center shadow-xs mb-3">
                <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <div className="font-bold text-sm text-ink">
                {selectedFile ? selectedFile.name : 'Drag & drop insurance policy document here'}
              </div>
              <p className="text-xs text-muted mt-1 max-w-sm">
                Supports PDF (selectable or scanned), PNG, JPEG, and WebP up to 10 MB.
              </p>
              <button
                type="button"
                className="mt-4 px-4 py-2 rounded-xl bg-white border border-line text-ink text-xs font-bold hover:bg-line transition-colors"
              >
                Browse Files
              </button>
            </div>
          )}

          {/* TAB 3: Text Paste */}
          {activeInputTab === 'paste' && (
            <div className="space-y-3">
              <label className="block text-xs font-bold text-ink">
                Paste Policy Circular or Insurer Letter Text
              </label>
              <textarea
                rows={8}
                value={pastedText}
                onChange={(e) => setPastedText(e.target.value)}
                placeholder="Paste insurer policy notice, coverage circular, or formulary announcement text here..."
                className="w-full p-3.5 rounded-xl border border-line font-mono text-xs focus:ring-2 focus:ring-brand focus:outline-hidden"
              />
              <button
                type="button"
                disabled={!pastedText.trim() || isExtracting}
                onClick={() => handleRunExtraction({ text: pastedText, filename: 'pasted_notice.txt' })}
                className="px-5 py-2.5 rounded-xl bg-cta text-white text-xs font-bold hover:bg-cta-hover transition-colors disabled:opacity-50 cursor-pointer"
              >
                Run AI Extraction
              </button>
            </div>
          )}

          {/* Extraction Loading Overlay */}
          {isExtracting && (
            <div className="p-8 rounded-xl bg-sunken border border-line flex flex-col items-center justify-center space-y-3 text-center">
              <div className="w-8 h-8 border-3 border-brand border-t-transparent rounded-full animate-spin" />
              <div className="text-sm font-bold text-ink">Processing Policy Document...</div>
              <p className="text-xs text-muted max-w-md">{extractionProgressStep}</p>
            </div>
          )}
        </div>
      )}

      {/* SECTION 2: TWO-COLUMN REVIEW WORKSPACE (When document is extracted) */}
      {docResult && activeProposal && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* LEFT COLUMN: ORIGINAL DOCUMENT & EVIDENCE VIEWER (5 cols) */}
          <div className="lg:col-span-5 bg-white rounded-2xl border border-line p-5 shadow-sm space-y-4 sticky top-6">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center gap-2">
                <span className="w-7 h-7 rounded-lg bg-brand-soft text-brand flex items-center justify-center font-bold text-xs">
                  <FileText className="size-4" aria-hidden="true" />
                </span>
                <div>
                  <h3 className="font-bold text-xs text-ink truncate max-w-[220px]">
                    {docResult.filename}
                  </h3>
                  <span className="text-[11px] text-muted">
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
                    className="p-1 rounded bg-sunken disabled:opacity-40"
                  >
                    ‹
                  </button>
                  <span className="font-bold text-xs text-ink">{currentPage}</span>
                  <button
                    disabled={currentPage >= docResult.page_count}
                    onClick={() => setCurrentPage((p) => Math.min(docResult.page_count, p + 1))}
                    className="p-1 rounded bg-sunken disabled:opacity-40"
                  >
                    ›
                  </button>
                </div>
              )}
            </div>

            {/* Document Preview (Rendered Image or Selectable Text) */}
            <div className="rounded-xl border border-line bg-sunken p-4 max-h-[460px] overflow-y-auto font-mono text-xs leading-relaxed text-ink">
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
              <div className="p-3.5 rounded-xl bg-warn-soft border border-warn-line space-y-1.5">
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
          <div className="lg:col-span-7 bg-white rounded-2xl border border-line p-6 shadow-sm space-y-5">
            {/* Policy Diff Banner */}
            {activeDiff && (
              <div
                className={`p-4 rounded-xl border flex items-start gap-3 ${
                  activeDiff.is_delay
                    ? 'bg-amber-50/70 border-amber-300 text-amber-900'
                    : activeDiff.change_category === 'coverage_restriction'
                    ? 'bg-red-50/70 border-red-300 text-red-900'
                    : 'bg-brand-soft border-brand/40 text-ink'
                }`}
              >
                <div className="w-8 h-8 rounded-lg bg-white/90 border border-current/20 flex items-center justify-center font-bold text-sm shrink-0">
                  {activeDiff.is_delay ? <Clock className="size-4" aria-hidden="true" /> : activeDiff.is_cancellation ? <X className="size-4" aria-hidden="true" /> : <AlertTriangle className="size-4" aria-hidden="true" />}
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
              <div className="p-3.5 rounded-xl bg-warn-soft border border-amber-200 space-y-1 text-xs text-amber-900">
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
                <h3 className="text-xs font-black uppercase tracking-wider text-ink">
                  Extracted Policy Details (Review & Correct Before Approval)
                </h3>
                <span className="text-[11px] text-muted">
                  Proposal ID: <span className="font-mono font-bold">{activeProposal.proposal_id}</span>
                </span>
              </div>

              {/* Title & Ref */}
              <div>
                <label className="block text-[11px] font-bold text-muted mb-1">
                  Policy Title
                </label>
                <input
                  type="text"
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-line text-xs font-bold text-ink focus:ring-2 focus:ring-brand focus:outline-hidden"
                />
              </div>

              {/* Insurer & Plan */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-muted mb-1">
                    Insurer
                  </label>
                  <input
                    type="text"
                    value={editedInsurer}
                    onChange={(e) => setEditedInsurer(e.target.value)}
                    placeholder="Verified insurer ID"
                    className="w-full px-3 py-2 rounded-xl border border-line bg-sunken text-xs text-ink font-semibold"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-muted mb-1">
                    Plan Scope
                  </label>
                  <input
                    type="text"
                    value={editedPlans}
                    onChange={(e) => setEditedPlans(e.target.value)}
                    placeholder="Plan IDs; * only when all plans are verified"
                    className="w-full px-3 py-2 rounded-xl border border-line bg-sunken text-xs text-ink font-semibold"
                  />
                </div>
              </div>

              {/* Clinical Target & Code */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-muted mb-1">
                    Target Code (CPT/HCPCS/ID)
                  </label>
                  <input
                    type="text"
                    value={editedCode}
                    onChange={(e) => setEditedCode(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-line text-xs font-mono font-bold text-ink focus:ring-2 focus:ring-brand focus:outline-hidden"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-muted mb-1">
                    Clinical Target Name
                  </label>
                  <input
                    type="text"
                    value={editedName}
                    onChange={(e) => setEditedName(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-line text-xs font-bold text-ink focus:ring-2 focus:ring-brand focus:outline-hidden"
                  />
                </div>
              </div>

              {/* Proposed Coverage Effect & Effective Date */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-muted mb-1">
                    Proposed Coverage Mandate
                  </label>
                  <select
                    value={editedEffect}
                    onChange={(e) => setEditedEffect(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-xl border border-line text-xs font-bold text-ink focus:ring-2 focus:ring-brand focus:outline-hidden"
                  >
                    <option value="">Unknown — verify effect</option>
                    <option value="excluded">Non-Covered / Excluded</option>
                    <option value="requires_prior_approval">Requires Prior Authorization</option>
                    <option value="requires_documents">Requires Clinical Documentation</option>
                    <option value="covered">Covered Standard Benefit</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-muted mb-1">
                    Effective Date
                  </label>
                  <input
                    type="date"
                    value={editedEffectiveDate}
                    onChange={(e) => setEditedEffectiveDate(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-line text-xs font-bold text-ink focus:ring-2 focus:ring-brand focus:outline-hidden"
                  />
                </div>
              </div>

              {!activeProposal.evidence_verified && <label className="flex gap-2 items-start text-xs text-amber-900">
              <input type="checkbox" checked={evidenceConfirmed} onChange={e => setEvidenceConfirmed(e.target.checked)} />
              I verified the complete supporting quotation against the original document. I recorded the verification in review notes.
            </label>}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <label>Policy reference<input aria-label="Policy reference" className="w-full border rounded-xl p-2" value={editedReference} onChange={e=>setEditedReference(e.target.value)} placeholder="e.g. CMS-NCD-150.9" /></label>
              <label>Applies only to diagnoses (ICD-10 prefixes)<input aria-label="Diagnosis scope" className="w-full border rounded-xl p-2" value={editedDiagnosisPrefixes} onChange={e=>setEditedDiagnosisPrefixes(e.target.value)} placeholder="e.g. M17 — leave blank for all diagnoses" /></label>
            </div>
            <label className="block text-xs">Evidence sentence — copy it exactly from the source text; approval fails unless it appears word for word
              <textarea aria-label="Evidence sentence" className="w-full border rounded-xl p-2 mt-1 min-h-16" value={editedQuote} onChange={e=>{setEditedQuote(e.target.value);setHighlightedQuote(e.target.value);}} />
            </label>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <label>Verified jurisdiction / state<input aria-label="Policy jurisdictions" className="w-full border rounded-xl p-2" value={editedRegions} onChange={e=>setEditedRegions(e.target.value)} placeholder="CA or explicitly national US" /></label>
              <label>Code system<input aria-label="Policy code system" className="w-full border rounded-xl p-2" value={editedCodeSystem} onChange={e=>setEditedCodeSystem(e.target.value)} placeholder="CPT / HCPCS" /></label>
            </div>
            <label className="flex gap-2 text-xs"><input type="checkbox" checked={scopeVerified} onChange={e=>setScopeVerified(e.target.checked)} />I verified the exact insurer, plan and jurisdiction applicability using the source and benefit scope. This approves the policy representation only.</label>
            {activeProposal.requires_billing_articles&&<label className="flex gap-2 text-xs"><input type="checkbox" checked={articlesVerified} onChange={e=>setArticlesVerified(e.target.checked)}/>I reviewed the applicable LCD billing articles, coding instructions and jurisdiction together with this policy.</label>}
            {/* Reviewer Notes */}
              <div>
                <label className="block text-[11px] font-bold text-muted mb-1">
                  Claims Officer Review Notes (Recorded in Audit Trail)
                </label>
                <input
                  type="text"
                  value={reviewerNotes}
                  onChange={(e) => setReviewerNotes(e.target.value)}
                  placeholder="e.g. Verified against Payer Bulletin 2026-1042; reviewed with pharmacy committee."
                  className="w-full px-3 py-2 rounded-xl border border-line text-xs text-ink focus:ring-2 focus:ring-brand focus:outline-hidden"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs">Verified item type
                <select aria-label="Verified item type" value={editedType} onChange={e => setEditedType(e.target.value as any)} className="w-full p-2 border rounded-xl">
                  <option value="">Unknown — verify type</option><option value="drug">Drug</option><option value="procedure">Procedure</option><option value="service">Service</option>
                </select>
              </label>

            </div>
            <p className="text-xs text-muted">Synthetic documents only. Images and scanned pages are sent to Gemini as uploaded and are not de-identified. Verify evidence visually and record corrections in review notes.</p>
            {docResult?.extraction_method && <p className="text-xs">Extraction: {docResult.extraction_method}. {docResult.extraction_error || ''}</p>}
            {/* Action Bar: What-If Preview vs Approve */}
            {(!editedCode.trim() || !editedEffectiveDate.trim() || !editedInsurer.trim() || !editedPlans.trim() || !editedType || !editedEffect || (!activeProposal?.evidence_verified && (!evidenceConfirmed || !reviewerNotes.trim()))) && (
              <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs font-medium space-y-1">
                <div className="font-bold flex items-center gap-1.5 text-amber-800">
                  <AlertTriangle className="size-4" aria-hidden="true" />
                  <span>Verification required before approval</span>
                </div>
                <p className="text-[11px] leading-relaxed">
                  CoverageGuard prevents unverified policy activation. The uploaded document has missing policy fields. Please supply verified insurer, plans, type, code, effect and date in the fields above before submitting approval.
                </p>
              </div>
            )}

            <div className="pt-4 border-t border-line flex flex-wrap items-center justify-between gap-3">
              <button
                type="button"
                disabled={isPreviewingImpact}
                onClick={handlePreviewImpact}
                className="px-4 py-2.5 rounded-xl border border-brand bg-brand-soft hover:bg-brand-soft text-brand text-xs font-bold transition-colors flex items-center gap-2 cursor-pointer shadow-2xs"
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
                  className="px-3.5 py-2.5 rounded-xl border border-line text-muted hover:text-red-700 hover:bg-red-50 text-xs font-bold transition-colors cursor-pointer"
                >
                  Reject
                </button>
                <button
                  type="button"
                  disabled={(activeProposal.requires_billing_articles && !articlesVerified) || !scopeVerified || isApproving || activeProposal.review_state === 'approved' || !editedCode.trim() || !editedEffectiveDate.trim() || !editedInsurer.trim() || !editedPlans.trim() || !editedType || !editedEffect || (!activeProposal?.evidence_verified && editedQuote.trim() === (activeProposal.supporting_quote || '').trim() && (!evidenceConfirmed || !reviewerNotes.trim()))}
                  onClick={handleApprove}
                  className="px-5 py-2.5 rounded-xl bg-cta hover:bg-brand text-white text-xs font-black transition-all shadow-md cursor-pointer disabled:opacity-50 flex items-center gap-2"
                >
                  {isApproving ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Activating...</span>
                    </>
                  ) : activeProposal.review_state === 'approved' ? (
                    <><Check className="size-4" aria-hidden="true" /><span>Rule approved</span></>
                  ) : (!editedCode.trim() || !editedEffectiveDate.trim() || !editedInsurer.trim() || !editedPlans.trim() || !editedType || !editedEffect || (!activeProposal?.evidence_verified && (!evidenceConfirmed || !reviewerNotes.trim()))) ? (
                    <><AlertTriangle className="size-4" aria-hidden="true" /><span>Missing rule fields</span></>
                  ) : (
                    <><span>Approve & Apply Policy</span><ArrowRight className="size-4" aria-hidden="true" /></>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 3: WHAT-IF IMPACT PREVIEW BREAKDOWN (When impactResult is available) */}
      {impactResult && (
        <div className="bg-white rounded-2xl border border-line p-6 shadow-sm space-y-5 animate-in fade-in duration-150">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-line pb-4">
            <div>
              <span className="text-[11px] font-black uppercase tracking-wider text-brand">
                Deterministic Simulation Result
              </span>
              <h3 className="text-base font-bold text-ink">
                Hospital Caseload What-If Claim Impact
              </h3>
            </div>
            <span className="text-xs text-muted">
              Evaluated across <span className="font-bold text-ink">{impactResult.total_cases_checked} open hospital claims</span>
            </span>
          </div>

          {impactResult.notice && <p className="text-xs text-amber-900 bg-amber-50 p-3 rounded-xl">{impactResult.notice}</p>}
          {/* KPI Summary Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3.5 rounded-xl bg-sunken border border-line">
              <span className="block text-[11px] text-muted font-medium">Claims Evaluated</span>
              <span className="text-xl font-black text-ink">{impactResult.total_cases_checked}</span>
            </div>
            <div className={`p-3.5 rounded-xl border ${impactResult.affected_cases > 0 ? 'bg-amber-50 border-amber-200 text-amber-900' : 'bg-brand-soft border-brand/30 text-brand'}`}>
              <span className="block text-[11px] font-medium">Potentially Affected</span>
              <span className="text-xl font-black">{impactResult.affected_cases}</span>
            </div>
            <div className={`p-3.5 rounded-xl border ${impactResult.new_risks > 0 ? 'bg-red-50 border-red-200 text-red-900' : 'bg-sunken border-line text-ink'}`}>
              <span className="block text-[11px] font-medium">New Denial Risks</span>
              <span className="text-xl font-black">{impactResult.new_risks}</span>
            </div>
            <div className="p-3.5 rounded-xl bg-brand-soft border border-brand/30 text-brand">
              <span className="block text-[11px] font-medium">Unchanged Claims</span>
              <span className="text-xl font-black">{impactResult.unchanged_cases}</span>
            </div>
          </div>

          {/* Affected Cases Table */}
          {impactResult.cases.length > 0 ? (
            <div className="overflow-x-auto rounded-xl border border-line">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-sunken border-b border-line text-muted font-bold text-[11px] uppercase tracking-wider">
                    <th className="py-2.5 px-3">Case ID</th>
                    <th className="py-2.5 px-3">Specialty</th>
                    <th className="py-2.5 px-3">Service Date</th>
                    <th className="py-2.5 px-3">Prescribed Item</th>
                    <th className="py-2.5 px-3">Prior Status</th>
                    <th className="py-2.5 px-3">Simulated Status</th>
                    <th className="py-2.5 px-3">Adjudication Rationale</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {impactResult.cases.map((c) => (
                    <tr key={c.case_id} className="hover:bg-sunken transition-colors">
                      <td className="py-2.5 px-3 font-mono font-bold text-ink">
                        {c.case_id}
                      </td>
                      <td className="py-2.5 px-3 text-muted">{c.specialty}</td>
                      <td className="py-2.5 px-3 font-medium text-ink">
                        <span className="px-1.5 py-0.5 rounded bg-gray-100 font-mono text-[11px]">
                          {c.service_date}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-ink">{c.item_name}</td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-brand-soft text-brand">
                          {c.previous_verdict}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-900 border border-amber-300">
                          {c.simulated_verdict}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-muted max-w-xs leading-relaxed">
                        {c.reason}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-6 text-center text-xs text-brand font-bold bg-brand-soft rounded-xl border border-brand/20">
              {impactResult.total_cases_checked === 0 ? 'No pending claims available for analysis.' : impactResult.notice ? 'Review the simulation notice before interpreting this result.' : 'No claim verdicts changed in this preview.'}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
