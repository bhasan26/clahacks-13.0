import React, { useEffect, useState } from 'react';
import { Case, CaseCheckResult, ItemVerdict, CaseStatusType, ItemResultType } from '../types';
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
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!caseData || !checkResult) return null;

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
            <span>Needs attention</span>
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

  return (
    <div
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#092328]/40 backdrop-blur-xs animate-in fade-in duration-150"
    >
      <div className="bg-white border border-[#D8E5DC] rounded-3xl max-w-2xl w-full max-h-[85vh] overflow-y-auto shadow-2xl flex flex-col">
        {/* Page 3 Header: Case ID, specialty, status badge */}
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
              className="p-1.5 rounded-lg text-[#12544F]/60 hover:text-[#092328] hover:bg-[#F0F5F2] transition-colors cursor-pointer text-sm font-bold"
            >
              ✕
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
            {caseData.group_number && (
              <>
                <span>·</span>
                <span>
                  <strong className="text-[#092328] font-semibold">Group:</strong>{' '}
                  <span className="font-mono">{caseData.group_number}</span>
                </span>
              </>
            )}
          </div>
        </div>

        {/* Item List: Each item shows one result: Covered, Not covered, Prior approval needed, Document missing, Value wrong */}
        <div className="p-6 space-y-4">
          <div className="text-xs font-bold text-[#12544F]/80 uppercase tracking-wider">
            Items Checked ({checkResult.results.length})
          </div>

          <div className="space-y-4">
            {checkResult.results.map((verdict, idx) => (
              <div
                key={idx}
                className="p-4 rounded-2xl bg-[#F0F5F2]/40 border border-[#D8E5DC] space-y-2.5"
              >
                {/* Item code/name & Result badge */}
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

                {/* Plain issue sentence, rule reference, and what to do */}
                <div className="text-xs text-[#092328] leading-relaxed pt-1">
                  <p className="font-medium">
                    {verdict.full_issue_text}
                  </p>
                </div>

                {/* Sub-breakdown: Rule and Action */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[11px] text-[#12544F]/70 border-t border-[#D8E5DC]/60">
                  <div className="flex items-center gap-2">
                    <span>{verdict.rule_reference}</span>
                    <span>·</span>
                    <span className="font-semibold text-[#092328]">
                      Action: {verdict.what_to_do}
                    </span>
                  </div>

                  {verdict.rule_id && (
                    <button
                      onClick={() => {
                        setSelectedRuleId(verdict.rule_id || null);
                        setBulletinModalOpen(true);
                      }}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white border border-[#D5E2D9] text-[#2A835F] text-[11px] font-bold hover:bg-[#EBF4EE] transition-colors shadow-2xs cursor-pointer"
                    >
                      <span>📄 Review Policy Bulletin {verdict.rule_id}</span>
                      <span>↗</span>
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Clinical note footer */}
          <div className="mt-4 p-3 rounded-xl bg-[#F0F5F2] text-[11px] text-[#12544F]/80 leading-normal">
            The agent only notifies. It never edits, rejects or submits, and never suggests a medical alternative.
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
