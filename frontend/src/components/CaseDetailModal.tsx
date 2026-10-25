import React, { useEffect, useState } from 'react';
import { Case, CaseCheckResult, ItemVerdict, CaseStatusType, ItemResultType, Alert, AlertTask } from '../types';
import { fetchCaseAlerts, updateAlertTask } from '../api';
import { PolicyBulletinModal } from './PolicyBulletinModal';

interface CaseDetailModalProps {
  caseData: Case | null;
  checkResult: CaseCheckResult | null;
  onClose: () => void;
}

export const CaseDetailModal: React.FC<CaseDetailModalProps> = ({
  caseData,
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

  const activeAlert = alerts.find((a) => a.status === 'open') || alerts[0];

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

  const getStatusBadge = (status: CaseStatusType) => {
    switch (status) {
      case 'Approved':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#2A835F]/15 text-[#2A835F] border border-[#2A835F]/30">
            <span className="h-2 w-2 rounded-full bg-[#2A835F]" />
            <span>Approved</span>
          </span>
        );
      case 'Needs attention':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#D97706]/15 text-[#D97706] border border-[#D97706]/30">
            <span className="h-2 w-2 rounded-full bg-[#D97706]" />
            <span>Potential Denial Risk</span>
          </span>
        );
      case 'Missing or wrong info':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#DC2626]/15 text-[#DC2626] border border-[#DC2626]/30">
            <span className="h-2 w-2 rounded-full bg-[#DC2626]" />
            <span>Missing or wrong info</span>
          </span>
        );
    }
  };

  const getItemResultBadge = (result: ItemResultType) => {
    switch (result) {
      case 'Covered':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#2A835F]/15 text-[#2A835F] border border-[#2A835F]/30">
            Covered
          </span>
        );
      case 'Not covered':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#D97706]/15 text-[#D97706] border border-[#D97706]/30">
            Not covered
          </span>
        );
      case 'Prior approval needed':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#D97706]/15 text-[#D97706] border border-[#D97706]/30">
            Prior approval needed
          </span>
        );
      case 'Document missing':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#DC2626]/15 text-[#DC2626] border border-[#DC2626]/30">
            Document missing
          </span>
        );
      case 'Value wrong':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#DC2626]/15 text-[#DC2626] border border-[#DC2626]/30">
            Value wrong
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#D97706]/15 text-[#D97706] border border-[#D97706]/30">
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
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#092328]/40 backdrop-blur-xs animate-in fade-in duration-150"
    >
      <div className="bg-white border border-[#D8E5DC] rounded-3xl max-w-3xl w-full max-h-[88vh] overflow-y-auto shadow-2xl flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-[#EAEFEA] sticky top-0 bg-white/95 backdrop-blur-sm z-10 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <h2 className="text-xl font-black text-[#092328] font-mono tracking-tight">
                Case {caseData.case_id}
              </h2>
              <span className="text-xs font-bold text-[#12544F]/70 px-2.5 py-1 bg-[#F0F5F2] rounded-lg">
                {caseData.specialty}
              </span>
              {getStatusBadge(caseData.status)}
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-[#12544F]/60 hover:text-[#092328] hover:bg-[#F0F5F2] transition-colors cursor-pointer"
              aria-label="Close"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Insurer & Member Info Row */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[#12544F]/75 pt-1 border-t border-[#EAEFEA]">
            <span>
              <strong className="text-[#092328] font-semibold">Insurer:</strong>{' '}
              {caseData.insurer_name || caseData.insurer_id || 'Demo Insurance Co.'}
            </span>
            <span>·</span>
            <span>
              <strong className="text-[#092328] font-semibold">Plan:</strong>{' '}
              {caseData.plan_id || 'PLAN-GOLD'}
            </span>
            <span>·</span>
            <span>
              <strong className="text-[#092328] font-semibold">Member ID:</strong>{' '}
              <span className="font-mono">{caseData.member_ref}</span>
            </span>
            <span>·</span>
            <span>
              <strong className="text-[#092328] font-semibold">Service Date:</strong>{' '}
              <span className="font-semibold text-[#092328]">{caseData.service_date}</span>
            </span>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* ------------------------------------------------------------- */}
          {/* Phase 7: Explainable Action Center Panel                       */}
          {/* ------------------------------------------------------------- */}
          {(caseData.status === 'Needs attention' || activeAlert) && (
            <div className="bg-[#FFFBEB] border-2 border-[#F59E0B]/40 rounded-2xl p-5 space-y-4 shadow-sm animate-in fade-in">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center space-x-2.5">
                  <span className="p-2 rounded-xl bg-[#F59E0B]/20 text-[#B45309]">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </span>
                  <div>
                    <h3 className="font-extrabold text-sm text-[#92400E]">
                      Explainable Action Center · Claim Denial Prevention
                    </h3>
                    <p className="text-xs text-[#B45309] font-medium">
                      Autonomous Sentinel identified a potential denial risk for scheduled services.
                    </p>
                  </div>
                </div>

                <span className="px-2.5 py-1 rounded-full text-[11px] font-black bg-[#F59E0B]/20 text-[#B45309] border border-[#F59E0B]/40 uppercase tracking-wider shrink-0">
                  Potential Denial Risk
                </span>
              </div>

              {/* Structured Explainability Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-white/80 rounded-xl p-3.5 border border-[#F59E0B]/25">
                <div>
                  <span className="text-[10px] uppercase font-bold text-[#92400E]/70 block">Reason</span>
                  <span className="font-bold text-[#92400E]">
                    {activeAlert?.headline || `${caseData.items[0]?.code || 'Item'} excluded or restricted under approved policy`}
                  </span>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-bold text-[#92400E]/70 block">Effective Date & Policy</span>
                  <span className="font-bold text-[#092328]">
                    {activeAlert?.effective_date || 'Effective 1 Nov 2026'} · <span className="font-mono">{activeAlert?.rule_id || 'Policy Rule'}</span>
                  </span>
                </div>

                <div className="md:col-span-2 pt-2 border-t border-[#F59E0B]/20">
                  <span className="text-[10px] uppercase font-bold text-[#92400E]/70 block">Verified Document Evidence</span>
                  <blockquote className="mt-1 pl-3 border-l-2 border-[#2A835F] text-[#092328] font-medium italic text-[11px] bg-[#F0F5F2]/50 py-1.5 pr-2 rounded-r">
                    "{activeAlert?.evidence_quote || 'Beginning November 1, 2026, PLAN-GOLD will no longer cover DRUG-A. This change applies to services performed on or after November 1, 2026.'}"
                  </blockquote>
                </div>

                <div className="md:col-span-2 pt-1">
                  <span className="text-[10px] uppercase font-bold text-[#92400E]/70 block">Suggested Follow-Up</span>
                  <p className="font-semibold text-[#092328] mt-0.5">
                    {activeAlert?.suggested_action || 'Contact the insurer or responsible clinical staff to review coverage requirements before claim submission.'}
                  </p>
                </div>
              </div>

              {/* Action Queue: Checklist of Administrative Tasks */}
              <div className="space-y-2 pt-2 border-t border-[#F59E0B]/20">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[#92400E] uppercase tracking-wide">
                    Action Queue Tasks ({activeAlert?.tasks?.filter((t) => t.status === 'completed').length || 0}/{activeAlert?.tasks?.length || 5} Completed)
                  </span>
                  <span className="text-[10px] text-[#B45309] font-medium">Click task to advance status</span>
                </div>

                <div className="space-y-1.5">
                  {(activeAlert?.tasks && activeAlert.tasks.length > 0
                    ? activeAlert.tasks
                    : [
                        { task_id: 't1', title: 'Review policy mandate and governing date criteria', status: 'open' as const },
                        { task_id: 't2', title: 'Verify member eligibility and plan formulary tier', status: 'open' as const },
                        { task_id: 't3', title: 'Check prior authorization status or submit PA packet', status: 'open' as const },
                        { task_id: 't4', title: 'Obtain required clinical documentation or lab results', status: 'open' as const },
                        { task_id: 't5', title: 'Contact responsible clinical department before submission', status: 'open' as const },
                      ]
                  ).map((t) => {
                    const isCompleted = t.status === 'completed';
                    const isInProgress = t.status === 'in_progress';
                    return (
                      <div
                        key={t.task_id}
                        onClick={() => activeAlert && handleToggleTask(activeAlert.alert_id, t)}
                        className={`flex items-center justify-between p-2.5 rounded-xl border text-xs cursor-pointer transition-all ${
                          isCompleted
                            ? 'bg-[#2A835F]/10 border-[#2A835F]/30 text-[#2A835F]'
                            : isInProgress
                            ? 'bg-[#D97706]/10 border-[#D97706]/30 text-[#D97706]'
                            : 'bg-white border-[#D8E5DC] text-[#092328] hover:bg-[#F0F5F2]'
                        }`}
                      >
                        <div className="flex items-center space-x-2.5">
                          <input
                            type="checkbox"
                            checked={isCompleted}
                            onChange={() => {}}
                            className="rounded text-[#2A835F] focus:ring-0 cursor-pointer"
                          />
                          <span className={`font-semibold ${isCompleted ? 'line-through text-[#12544F]/70' : ''}`}>
                            {t.title}
                          </span>
                        </div>

                        <div className="flex items-center space-x-2 shrink-0">
                          {t.completed_by && (
                            <span className="text-[10px] text-[#12544F]/60">
                              By {t.completed_by}
                            </span>
                          )}
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              isCompleted
                                ? 'bg-[#2A835F] text-white'
                                : isInProgress
                                ? 'bg-[#D97706] text-white'
                                : 'bg-[#EAEFEA] text-[#12544F]'
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
              <div className="pt-2 border-t border-[#F59E0B]/20">
                <button
                  type="button"
                  onClick={() => setShowDraftBox(!showDraftBox)}
                  className="flex items-center space-x-2 text-xs font-bold text-[#B45309] hover:text-[#92400E] cursor-pointer"
                >
                  <span>{showDraftBox ? '▼ Hide Administrative Draft Message' : '► ✨ View Administrative Draft Notice'}</span>
                </button>

                {showDraftBox && (
                  <div className="mt-3 p-3 bg-white rounded-xl border border-[#F59E0B]/30 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase text-[#92400E] tracking-wider">
                        Suggested Notice Draft (Hospital Staff Review)
                      </span>
                      <button
                        type="button"
                        onClick={() => handleCopyDraft(draftMessage)}
                        className="px-2.5 py-1 rounded-lg bg-[#092328] text-white text-[11px] font-bold hover:bg-[#12544F] transition-all cursor-pointer flex items-center space-x-1"
                      >
                        <span>{copiedDraft ? '✓ Copied' : 'Copy Draft'}</span>
                      </button>
                    </div>

                    <p className="text-xs text-[#092328] font-mono bg-[#F0F5F2] p-2.5 rounded-lg border border-[#D8E5DC]">
                      {draftMessage}
                    </p>

                    <p className="text-[10px] text-[#92400E]/80 italic">
                      🛡️ Safety Governance: Human must review and transmit draft manually. Automatic external dispatch disabled.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Item List: Each item shows one result */}
          <div className="space-y-4">
            <div className="text-xs font-bold text-[#12544F]/80 uppercase tracking-wider">
              Items Checked ({checkResult.results.length})
            </div>

            <div className="space-y-4">
              {checkResult.results.map((verdict, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-2xl bg-[#F0F5F2]/40 border border-[#D8E5DC] space-y-2.5"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-sm text-[#092328]">
                        {verdict.item.name || verdict.item.code}
                      </span>
                      <span className="font-mono text-xs text-[#12544F]/60">
                        ({verdict.item.code})
                      </span>
                    </div>
                    {getItemResultBadge(verdict.result)}
                  </div>

                  <div className="text-xs text-[#092328] leading-relaxed pt-1">
                    <p className="font-medium">
                      {verdict.full_issue_text}
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[11px] text-[#12544F]/70 border-t border-[#D8E5DC]/60">
                    <div className="flex items-center gap-2">
                      <span>{verdict.rule_reference}</span>
                      <span>·</span>
                      <span className="font-semibold text-[#092328]">
                        Action: {verdict.what_to_do}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 mt-2">
                      {verdict.official_reference_url && (
                        <a
                          href={verdict.official_reference_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#2A835F] text-white text-[11px] font-bold hover:bg-[#20684b] transition-colors shadow-2xs cursor-pointer"
                        >
                          <span>Official Payer Document</span>
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
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white border border-[#D5E2D9] text-[#2A835F] text-[11px] font-bold hover:bg-[#EBF4EE] transition-colors shadow-2xs cursor-pointer"
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

            <div className="mt-4 p-3 rounded-xl bg-[#F0F5F2] text-[11px] text-[#12544F]/80 leading-normal">
              The agent only notifies. It never edits, rejects or submits, and never suggests a medical alternative.
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-[#EAEFEA] bg-[#FBFDFB] rounded-b-3xl flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-[#092328] hover:bg-[#12544F] text-white text-xs font-bold transition-all cursor-pointer"
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
