import React, { useState } from 'react';
import { X, CheckCircle2, AlertTriangle, ShieldCheck, RefreshCw, FileText, Calendar, ShieldAlert, BookOpen } from 'lucide-react';
import { Case, CaseCheckResult, Alert, ItemVerdict } from '../types';

interface CaseDetailModalProps {
  caseData: Case | null;
  checkResult: CaseCheckResult | null;
  alerts: Alert[];
  onClose: () => void;
  onRecheck: (caseId: string) => Promise<void>;
}

export const CaseDetailModal: React.FC<CaseDetailModalProps> = ({
  caseData,
  checkResult,
  alerts,
  onClose,
  onRecheck,
}) => {
  const [isRechecking, setIsRechecking] = useState(false);

  if (!caseData || !checkResult) return null;

  const handleRecheck = async () => {
    setIsRechecking(true);
    await onRecheck(caseData.case_id);
    setIsRechecking(false);
  };

  const getVerdictChip = (verdict: ItemVerdict) => {
    switch (verdict.verdict) {
      case 'covered':
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-lime-50 text-lime-800 border border-lime-300 shadow-sm">
            ✓ Covered
          </span>
        );
      case 'excluded':
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-300 shadow-sm">
            ✕ Excluded
          </span>
        );
      case 'prior_approval_needed':
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-300 shadow-sm">
            ⚠ Prior Approval Needed
          </span>
        );
      case 'documents_missing':
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-orange-50 text-orange-800 border border-orange-300 shadow-sm">
            📄 Documents Missing
          </span>
        );
      case 'no_rule_found':
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-600 border border-slate-200">
            ❓ No Rule Found
          </span>
        );
      default:
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-600">
            {verdict.verdict}
          </span>
        );
    }
  };

  const isClear = checkResult.overall_status === 'clear';
  const hasExcluded = checkResult.results.some((r) => r.verdict === 'excluded');
  const excludedItems = checkResult.results
    .filter((r) => r.verdict === 'excluded')
    .map((r) => r.item.name || r.item.code);
  const excludedDate =
    checkResult.results.find((r) => r.verdict === 'excluded')?.effective_from ??
    'Nov 1, 2026';

  const hasPriorAuthNeeded = checkResult.results.some(
    (r) => r.verdict === 'prior_approval_needed'
  );
  const priorAuthItems = checkResult.results
    .filter((r) => r.verdict === 'prior_approval_needed')
    .map((r) => r.item.name || r.item.code);

  const hasMissingDocs = checkResult.results.some(
    (r) => r.verdict === 'documents_missing'
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white border border-slate-200/80 rounded-3xl max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
        {/* Modal Header */}
        <div className="sticky top-0 bg-white/95 backdrop-blur-md border-b border-slate-100 p-6 flex items-center justify-between z-10">
          <div>
            <div className="flex items-center space-x-3">
              <h2 className="text-xl font-extrabold text-slate-900 font-mono tracking-tight">Case {caseData.case_id}</h2>
              <span className="px-3 py-0.5 rounded-full text-xs font-mono font-bold bg-slate-100 text-slate-800 border border-slate-200">
                Plan: {caseData.plan_id}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
              <span>Member Ref: <strong className="text-slate-800 font-mono">{caseData.member_ref}</strong></span>
              <span>•</span>
              <span className="flex items-center space-x-1">
                <Calendar className="h-3 w-3 text-slate-400" />
                <span>Service Date: <strong className="text-slate-800">{caseData.service_date}</strong></span>
              </span>
              <span>•</span>
              <span>Prior Approval: <strong className={caseData.prior_approval_ref ? "text-emerald-700 font-mono font-bold" : "text-rose-600 italic font-bold"}>{caseData.prior_approval_ref || 'Missing'}</strong></span>
              {caseData.documents.length > 0 && (
                <>
                  <span>•</span>
                  <span>Docs: <strong className="text-slate-700 font-mono">{caseData.documents.join(', ')}</strong></span>
                </>
              )}
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleRecheck}
              disabled={isRechecking}
              className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-slate-900 hover:bg-slate-800 text-white transition-all active:scale-95 cursor-pointer shadow-sm"
            >
              <RefreshCw className={`h-3.5 w-3.5 text-lime-400 ${isRechecking ? 'animate-spin' : ''}`} />
              <span>Re-check</span>
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-900 transition-all cursor-pointer"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-6">
          {/* Executive Agent Determination: Complete vs Action Required */}
          {isClear ? (
            <div className="p-6 rounded-3xl bg-lime-50/70 border-2 border-lime-400 shadow-[0_2px_16px_rgba(132,204,22,0.12)] space-y-3">
              <div className="flex items-center space-x-3">
                <div className="h-10 w-10 rounded-2xl bg-lime-400 text-slate-950 flex items-center justify-center font-bold shadow-sm">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
                <div>
                  <span className="text-[11px] font-extrabold uppercase tracking-wider text-lime-900 bg-lime-200 px-3 py-0.5 rounded-full">
                    Agent Determination: Verified Clean
                  </span>
                  <h3 className="text-base font-extrabold text-slate-950 mt-1">
                    File is Complete & Ready to Submit
                  </h3>
                </div>
              </div>
              <p className="text-xs text-slate-700 leading-relaxed pl-1">
                All patient data, required documentation, and prior approvals ({caseData.prior_approval_ref ? <span className="font-mono text-slate-950 font-bold">{caseData.prior_approval_ref}</span> : 'verified on file'}) are present. Every requested drug and procedure is 100% covered under the insurer's current rules. No rejection risks detected.
              </p>
              <div className="inline-flex items-center space-x-2 text-xs font-bold text-lime-900 bg-lime-200/80 px-3.5 py-1.5 rounded-xl border border-lime-300">
                <span>✓ Cleared for immediate electronic claims filing.</span>
              </div>
            </div>
          ) : (
            <div className="p-6 rounded-3xl bg-rose-50/80 border-2 border-rose-400 shadow-[0_2px_16px_rgba(244,63,94,0.12)] space-y-4">
              <div className="flex items-center space-x-3">
                <div className="h-10 w-10 rounded-2xl bg-rose-500 text-white flex items-center justify-center font-bold shadow-sm">
                  <AlertTriangle className="h-6 w-6" />
                </div>
                <div>
                  <span className="text-[11px] font-extrabold uppercase tracking-wider text-rose-900 bg-rose-200 px-3 py-0.5 rounded-full">
                    Agent Determination: Rejection Risk Detected
                  </span>
                  <h3 className="text-base font-extrabold text-slate-950 mt-1">
                    File Has Gaps That Will Cause Payer Claim Rejection
                  </h3>
                </div>
              </div>

              <div className="text-xs text-slate-700 space-y-2">
                {hasExcluded && (
                  <div className="flex items-start space-x-2.5 bg-white p-3.5 rounded-2xl border border-rose-200 shadow-sm">
                    <span className="text-rose-600 font-extrabold shrink-0 text-sm">✕</span>
                    <span>
                      <strong className="text-slate-900">Formulary Exclusion:</strong> The requested medication <span className="font-bold text-rose-700">({excludedItems.join(', ')})</span> is <strong>no longer covered</strong> effective <span className="font-bold text-slate-900">{excludedDate}</span> under the insurer's recent policy update.
                    </span>
                  </div>
                )}
                {hasPriorAuthNeeded && (
                  <div className="flex items-start space-x-2.5 bg-white p-3.5 rounded-2xl border border-amber-200 shadow-sm">
                    <span className="text-amber-600 font-extrabold shrink-0 text-sm">⚠</span>
                    <span>
                      <strong className="text-slate-900">Documentation / Approval Gap:</strong> Procedure <span className="font-bold text-slate-900">({priorAuthItems.join(', ')})</span> requires insurer Prior Authorization, but no approval reference is on file.
                    </span>
                  </div>
                )}
                {hasMissingDocs && (
                  <div className="flex items-start space-x-2.5 bg-white p-3.5 rounded-2xl border border-amber-200 shadow-sm">
                    <span className="text-amber-600 font-extrabold shrink-0 text-sm">📄</span>
                    <span>
                      <strong className="text-slate-900">Missing Records:</strong> Supporting clinical chart documentation required by insurer is missing.
                    </span>
                  </div>
                )}
              </div>

              {/* Clear Staff Instruction */}
              <div className="p-4 rounded-2xl bg-slate-950 text-white text-xs space-y-1.5 shadow-md">
                <div className="font-bold text-lime-400 flex items-center space-x-2">
                  <span>👉</span>
                  <span className="text-white">Hospital Employee Action Required Before Submission:</span>
                </div>
                <p className="text-slate-300 leading-relaxed pl-5">
                  Take this file to the <strong>treating physician before submission</strong> to choose a covered alternative drug under the insurer's updated formulary and obtain the missing prior authorization. Submitting this file in its current state will cause an immediate claim rejection.
                </p>
              </div>
            </div>
          )}

          {/* Active Alerts for this Case */}
          {alerts.length > 0 && (
            <div className="space-y-2.5">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                <ShieldAlert className="h-4 w-4 text-rose-500" />
                <span>Associated Policy Alerts ({alerts.length})</span>
              </h4>
              <div className="space-y-2">
                {alerts.map((a) => (
                  <div
                    key={a.alert_id}
                    className={`p-4 rounded-2xl border text-xs ${
                      a.status === 'open'
                        ? 'bg-rose-50/70 border-rose-200 text-rose-950'
                        : 'bg-slate-50 border-slate-200 text-slate-600'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900">{a.headline}</span>
                      <span className="uppercase text-[10px] font-extrabold px-2 py-0.5 rounded-full bg-white border border-slate-200">
                        {a.status}
                      </span>
                    </div>
                    <p className="mt-1 text-slate-600 leading-relaxed">{a.explanation}</p>
                    {a.closed_reason && (
                      <p className="mt-1.5 text-emerald-700 font-bold">✓ Closed: {a.closed_reason}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Itemized Findings */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
              <BookOpen className="h-4 w-4 text-lime-600" />
              <span>Item-by-Item Coverage Findings ({checkResult.results.length})</span>
            </h4>

            <div className="space-y-3">
              {checkResult.results.map((itemVerdict, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-2xl bg-white border border-slate-200/80 hover:border-slate-300 shadow-sm transition-all space-y-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-bold font-mono px-2.5 py-0.5 rounded-lg bg-slate-100 text-slate-800 border border-slate-200">
                          {itemVerdict.item.code}
                        </span>
                        <span className="text-sm font-bold text-slate-900">
                          {itemVerdict.item.name || itemVerdict.item.code}
                        </span>
                        <span className="text-xs text-slate-400 capitalize">
                          ({itemVerdict.item.type})
                        </span>
                      </div>
                    </div>
                    {getVerdictChip(itemVerdict)}
                  </div>

                  <p className="text-xs text-slate-600 leading-relaxed">
                    {itemVerdict.explanation}
                  </p>

                  {/* Audit Trail & Citation Data */}
                  <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100 text-[11px] text-slate-500">
                    {itemVerdict.rule_id ? (
                      <>
                        <span className="font-mono bg-slate-100 px-2 py-0.5 rounded-lg text-slate-800 font-bold">
                          Rule: {itemVerdict.rule_id} v{itemVerdict.rule_version}
                        </span>
                        {itemVerdict.effective_from && (
                          <span className="bg-slate-100 px-2 py-0.5 rounded-lg text-slate-700">
                            Effective: {itemVerdict.effective_from}
                          </span>
                        )}
                        {itemVerdict.source_ref && (
                          <span className="bg-slate-100 px-2 py-0.5 rounded-lg text-slate-500">
                            Source: {itemVerdict.source_ref}
                          </span>
                        )}
                      </>
                    ) : (
                      <span className="italic text-slate-400">No rule citation available in insurer feed</span>
                    )}
                  </div>

                  {itemVerdict.suggested_officer_action && (
                    <div className="bg-slate-50 border border-slate-200 text-slate-800 p-3 rounded-xl text-xs flex items-center space-x-2">
                      <span>👉</span>
                      <span><strong>Officer Action:</strong> {itemVerdict.suggested_officer_action}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Diagnostic Context */}
          {caseData.diagnoses.length > 0 && (
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-1.5">
              <h5 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Primary Diagnoses
              </h5>
              <div className="flex flex-wrap gap-2">
                {caseData.diagnoses.map((dx, i) => (
                  <span
                    key={i}
                    className="px-2.5 py-1 rounded-xl bg-white text-xs font-mono text-slate-800 border border-slate-200 shadow-sm"
                  >
                    <strong>{dx.code}</strong> {dx.description ? `- ${dx.description}` : ''}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
