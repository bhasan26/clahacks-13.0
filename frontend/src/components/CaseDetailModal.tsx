import React, { useEffect, useState } from 'react';
import { Check, ChevronDown, ChevronRight, Copy, ShieldCheck } from 'lucide-react';
import { Case, ClaimFindingsReport, CaseCheckResult, ItemVerdict, ItemResultType, Alert, AlertTask } from '../types';
import { fetchCaseAlerts, updateAlertTask } from '../api';
import { PolicyBulletinModal } from './PolicyBulletinModal';
import { ClaimFindingsPanel } from './ClaimFindingsPanel';

interface CaseDetailModalProps {
  findings?: ClaimFindingsReport | null;
  caseData: Case | null;
  checkResult: CaseCheckResult | null;
  onClose: () => void;
}

export const CaseDetailModal: React.FC<CaseDetailModalProps> = ({
  caseData,
  findings,
  checkResult,
  onClose,
}) => {
  const [bulletinModalOpen, setBulletinModalOpen] = useState<boolean>(false);
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [copiedDraft, setCopiedDraft] = useState<boolean>(false);
  const [showDraftBox, setShowDraftBox] = useState<boolean>(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (caseData?.case_id) {
      fetchCaseAlerts(caseData.case_id)
        .then((res) => setAlerts(res || []))
        .catch(() => setAlerts([]));
    }
  }, [caseData?.case_id]);

  if (!caseData || !checkResult) return null;

  const activeAlert = alerts.find((a) => a.status === 'open');

  const handleToggleTask = async (alertId: string, task: AlertTask) => {
    const nextStatus: 'open' | 'in_progress' | 'completed' =
      task.status === 'open' ? 'in_progress' : (task.status === 'in_progress' ? 'completed' : 'open');
    try {
      const res = await updateAlertTask(alertId, task.task_id, nextStatus, 'Claims Officer');
      setAlerts((prev) => prev.map((a) => (a.alert_id === alertId ? res.alert : a)));
    } catch (e) {
      console.error('Failed to update task status', e);
    }
  };

  const handleCopyDraft = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedDraft(true);
    setTimeout(() => setCopiedDraft(false), 2500);
  };

  const getItemResultBadge = (result: ItemResultType) => {
    switch (result) {
      case 'Covered':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-brand/15 text-brand border border-brand/30">
            Covered
          </span>
        );
      case 'Not covered':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-warn-soft text-warn border border-warn-line">
            Not covered
          </span>
        );
      case 'Prior approval needed':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-warn-soft text-warn border border-warn-line">
            Prior approval needed
          </span>
        );
      case 'Document missing':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-bad-soft text-bad border border-bad-line">
            Document missing
          </span>
        );
      case 'Value wrong':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-bad-soft text-bad border border-bad-line">
            Value wrong
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-warn-soft text-warn border border-warn-line">
            No rule found
          </span>
        );
    }
  };

  const draftMessage = activeAlert?.draft_message || (
    `Notice regarding Claim ${caseData.case_id}: Policy update for ${caseData.items[0]?.name || 'scheduled care'} effective ${activeAlert?.effective_date || 'recently'}. Please review the attached coverage rule and verify any required documentation or prior authorization before submission.`
  );

  return (
    <div
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/40 backdrop-blur-xs animate-in fade-in duration-150"
    >
      <div className="bg-white border border-line rounded-3xl max-w-3xl w-full max-h-[88vh] overflow-y-auto shadow-2xl flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-line sticky top-0 bg-white/95 backdrop-blur-sm z-10 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <h2 className="text-xl font-bold text-ink tracking-tight">
                Claim {caseData.case_id}
              </h2>
              <span className="text-xs font-bold text-subtle px-2.5 py-1 bg-sunken rounded-lg">
                {caseData.specialty}
              </span>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-subtle hover:text-ink hover:bg-sunken transition-colors cursor-pointer"
              aria-label="Close"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Insurer & Member Info Row */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-subtle pt-1 border-t border-line">
            <span>
              <strong className="text-ink font-semibold">Insurer:</strong>{' '}
              {caseData.insurer_name || caseData.insurer_id || 'Insurer missing'}
            </span>
            <span>·</span>
            <span>
              <strong className="text-ink font-semibold">Plan:</strong>{' '}
              {caseData.plan_id || 'Plan ID missing'}
            </span>
            <span>·</span>
            <span>
              <strong className="text-ink font-semibold">Member ID:</strong>{' '}
              <span className="font-mono">{caseData.member_ref}</span>
            </span>
            <span>·</span>
            <span>
              <strong className="text-ink font-semibold">Service Date:</strong>{' '}
              <span className="font-semibold text-ink">{caseData.service_date}</span>
            </span>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* The plain answer first, then what to do about any rule change. */}
          {findings && <ClaimFindingsPanel report={findings} />}
          {activeAlert && (
            <div className="bg-warn-soft border-2 border-warn-line rounded-2xl p-5 space-y-4 shadow-sm animate-in fade-in">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center space-x-2.5">
                  <span className="p-2 rounded-xl bg-warn-line text-warn">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </span>
                  <div>
                    <h3 className="font-extrabold text-sm text-warn">
                      A rule change affects this claim
                    </h3>
                    <p className="text-xs text-warn font-medium">
                      Work through the steps below before sending it to the insurer.
                    </p>
                  </div>
                </div>

                <span className="px-2.5 py-1 rounded-full text-[11px] font-black bg-warn-line text-warn border border-warn-line uppercase tracking-wider shrink-0">
                  Action needed
                </span>
              </div>

              {/* Structured Explainability Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-white/80 rounded-xl p-3.5 border border-warn-line">
                <div>
                  <span className="text-[10px] uppercase font-bold text-warn block">Reason</span>
                  <span className="font-bold text-warn">
                    {activeAlert?.headline || `${caseData.items[0]?.code || 'Item'} excluded or restricted under approved policy`}
                  </span>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-bold text-warn block">Effective date and rule</span>
                  <span className="font-bold text-ink">
                    {activeAlert?.effective_date || 'Effective date unavailable'} · <span className="font-mono">{activeAlert?.rule_id || 'Policy Rule'}</span>
                  </span>
                </div>

                <div className="md:col-span-2 pt-2 border-t border-warn-line">
                  <span className="text-[10px] uppercase font-bold text-warn block">Insurer's wording</span>
                  <blockquote className="mt-1 pl-3 border-l-2 border-brand text-ink font-medium italic text-[11px] bg-sunken py-1.5 pr-2 rounded-r">
                    "{activeAlert?.evidence_quote || 'No verified source quotation is available. Review the policy evidence before acting.'}"
                  </blockquote>
                </div>

                <div className="md:col-span-2 pt-1">
                  <span className="text-[10px] uppercase font-bold text-warn block">What to do</span>
                  <p className="font-semibold text-ink mt-0.5">
                    {activeAlert?.suggested_action || 'Contact the insurer or responsible clinical staff to review coverage requirements before claim submission.'}
                  </p>
                </div>
              </div>

              {/* Action Queue: Checklist of Administrative Tasks */}
              <div className="space-y-2 pt-2 border-t border-warn-line">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-warn uppercase tracking-wide">
                    To-do ({activeAlert?.tasks?.filter((t) => t.status === 'completed').length || 0} of {activeAlert?.tasks?.length || 0} done)
                  </span>
                  <span className="text-[10px] text-warn font-medium">Click a task to update it</span>
                </div>

                <div className="space-y-1.5">
                  {(activeAlert?.tasks && activeAlert.tasks.length > 0
                    ? activeAlert.tasks
                    : []
                  ).map((t) => {
                    const isCompleted = t.status === 'completed';
                    const isInProgress = t.status === 'in_progress';
                    return (
                      <div
                        key={t.task_id}
                        onClick={() => activeAlert && handleToggleTask(activeAlert.alert_id, t)}
                        className={`flex items-center justify-between p-2.5 rounded-xl border text-xs cursor-pointer transition-all ${
                          isCompleted
                            ? 'bg-brand/10 border-brand/30 text-brand'
                            : isInProgress
                            ? 'bg-warn-soft border-warn-line text-warn'
                            : 'bg-white border-line text-ink hover:bg-sunken'
                        }`}
                      >
                        <div className="flex items-center space-x-2.5">
                          <input
                            type="checkbox"
                            checked={isCompleted}
                            onChange={() => {}}
                            className="rounded text-brand focus:ring-0 cursor-pointer"
                          />
                          <span className={`font-semibold ${isCompleted ? 'line-through text-subtle' : ''}`}>
                            {t.title}
                          </span>
                        </div>

                        <div className="flex items-center space-x-2 shrink-0">
                          {t.completed_by && (
                            <span className="text-[10px] text-subtle">
                              By {t.completed_by}
                            </span>
                          )}
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              isCompleted
                                ? 'bg-brand text-white'
                                : isInProgress
                                ? 'bg-warn text-white'
                                : 'bg-line text-muted'
                            }`}
                          >
                            {t.status.replace('_', ' ')}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Administrative Draft Message (Optional AI Feature) */}
              <div className="pt-2 border-t border-warn-line">
                <button
                  type="button"
                  onClick={() => setShowDraftBox(!showDraftBox)}
                  className="flex items-center space-x-2 text-xs font-bold text-warn hover:text-warn cursor-pointer"
                >
                  {showDraftBox ? <ChevronDown className="size-4" aria-hidden="true" /> : <ChevronRight className="size-4" aria-hidden="true" />}
                  <span>{showDraftBox ? 'Hide draft message' : 'View draft notice'}</span>
                </button>

                {showDraftBox && (
                  <div className="mt-3 p-3 bg-white rounded-xl border border-warn-line space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase text-warn tracking-wider">
                        Suggested Notice Draft (Hospital Staff Review)
                      </span>
                      <button
                        type="button"
                        onClick={() => handleCopyDraft(draftMessage)}
                        className="px-2.5 py-1 rounded-lg bg-cta text-white text-[11px] font-bold hover:bg-cta-hover transition-all cursor-pointer flex items-center space-x-1"
                      >
                        {copiedDraft ? <Check className="size-3.5" aria-hidden="true" /> : <Copy className="size-3.5" aria-hidden="true" />}
                        <span>{copiedDraft ? 'Copied' : 'Copy draft'}</span>
                      </button>
                    </div>

                    <p className="text-xs text-ink font-mono bg-sunken p-2.5 rounded-lg border border-line">
                      {draftMessage}
                    </p>

                    <p className="text-[10px] text-warn italic">
                      <ShieldCheck className="mr-1 inline size-3.5 align-[-2px]" aria-hidden="true" />A person must review and send this draft; nothing is sent automatically.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Item List: Each item shows one result */}
          {!findings && <div className="space-y-4">
            <div className="text-xs font-bold text-subtle uppercase tracking-wider">
              Items Checked ({checkResult.results.length})
            </div>

            <div className="space-y-4">
              {checkResult.results.map((verdict, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-2xl bg-sunken border border-line space-y-2.5"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-sm text-ink">
                        {verdict.item.name || verdict.item.code}
                      </span>
                      <span className="font-mono text-xs text-subtle">
                        ({verdict.item.code})
                      </span>
                    </div>
                    {getItemResultBadge(verdict.result)}
                  </div>

                  <div className="text-xs text-ink leading-relaxed pt-1">
                    <p className="font-medium">
                      {verdict.full_issue_text}
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[11px] text-subtle border-t border-line">
                    <div className="flex items-center gap-2">
                      <span>{verdict.rule_reference}</span>
                      <span>·</span>
                      <span className="font-semibold text-ink">
                        Action: {verdict.what_to_do}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 mt-2">
                      {verdict.official_reference_url && (
                        <a
                          href={verdict.official_reference_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-brand text-white text-[11px] font-bold hover:bg-brand-hover transition-colors shadow-2xs cursor-pointer"
                        >
                          <span>{caseData.policy_environment === "demo" ? "Simulated policy source" : "Policy source"}</span>
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>
                      )}
                      {verdict.rule_id && (
                        <button
                          onClick={() => {
                            setSelectedRuleId(verdict.rule_id || null);
                            setBulletinModalOpen(true);
                          }}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white border border-line text-brand text-[11px] font-bold hover:bg-brand-soft transition-colors shadow-2xs cursor-pointer"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <span>Review Policy Bulletin {verdict.rule_id}</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-4 p-3 rounded-xl bg-sunken text-[11px] text-subtle leading-normal">
              The agent only notifies. It never edits, rejects or submits, and never suggests a medical alternative.
            </div>
          </div>}
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-line bg-sunken rounded-b-3xl flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-cta hover:bg-cta-hover text-white text-xs font-bold transition-all cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>

      <PolicyBulletinModal
        isOpen={bulletinModalOpen}
        onClose={() => setBulletinModalOpen(false)}
        ruleId={selectedRuleId}
      />
    </div>
  );
};
