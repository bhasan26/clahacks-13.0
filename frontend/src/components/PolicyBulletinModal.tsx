import React, { useEffect, useState } from 'react';
import { PolicyBulletin } from '../types';
import { fetchPolicyBulletin } from '../api';

interface PolicyBulletinModalProps {
  ruleId: string | null;
  initialBulletin?: PolicyBulletin | null;
  isOpen: boolean;
  onClose: () => void;
}

export const PolicyBulletinModal: React.FC<PolicyBulletinModalProps> = ({
  ruleId,
  initialBulletin,
  isOpen,
  onClose,
}) => {
  const [bulletin, setBulletin] = useState<PolicyBulletin | null>(initialBulletin || null);
  const [loading, setLoading] = useState<boolean>(!initialBulletin);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !ruleId) return;

    if (initialBulletin && initialBulletin.rule_id === ruleId) {
      setBulletin(initialBulletin);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    fetchPolicyBulletin(ruleId)
      .then((data) => {
        setBulletin(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load bulletin:', err);
        setError('Failed to fetch official policy circular. Please verify rule ID.');
        setLoading(false);
      });
  }, [isOpen, ruleId, initialBulletin]);

  if (!isOpen) return null;

  return (
    <div
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-[#092328]/60 backdrop-blur-xs animate-in fade-in duration-150"
    >
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-[#D5E2D9]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#E8EFEA] flex items-center justify-between bg-[#F8FAF9]">
          <div className="flex items-center gap-3">
            <span className="w-8 h-8 rounded-lg bg-[#EBF4EE] text-[#2A835F] flex items-center justify-center text-sm font-bold border border-[#D5E2D9]">
              <svg className="w-4 h-4 text-[#2A835F]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-[#698579]">
                  Official Payer Policy Circular
                </span>
                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-[#EBF4EE] text-[#2A835F] border border-[#D5E2D9]">
                  {bulletin?.insurer_name || 'Insurer Policy'}
                </span>
              </div>
              <h3 className="text-base font-bold text-[#092328]">
                {bulletin?.title || `Policy Bulletin ${ruleId}`}
              </h3>
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

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-5 text-sm">
          {loading ? (
            <div className="py-12 flex flex-col items-center justify-center space-y-3">
              <div className="w-8 h-8 border-3 border-[#2A835F] border-t-transparent rounded-full animate-spin" />
              <p className="text-sm font-medium text-[#698579]">Retrieving official insurer bulletin...</p>
            </div>
          ) : error || !bulletin ? (
            <div className="py-8 text-center text-red-600 space-y-2">
              <p className="font-semibold">{error || 'Policy details not available.'}</p>
              <button
                onClick={onClose}
                className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200"
              >
                Close
              </button>
            </div>
          ) : (
            <>
              {/* Meta Chips */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3 rounded-xl bg-[#F4F7F5] border border-[#E8EFEA] text-xs">
                <div>
                  <span className="block text-[#698579] font-medium text-[11px]">Rule ID</span>
                  <span className="font-bold text-[#092328]">{bulletin.rule_id}</span>
                </div>
                <div>
                  <span className="block text-[#698579] font-medium text-[11px]">Effective Date</span>
                  <span className="font-bold text-[#D97706]">{bulletin.effective_date}</span>
                </div>
                <div>
                  <span className="block text-[#698579] font-medium text-[11px]">Policy Status</span>
                  <span className="font-bold text-[#2A835F]">{bulletin.status}</span>
                </div>
                <div>
                  <span className="block text-[#698579] font-medium text-[11px]">Last Reviewed</span>
                  <span className="font-bold text-[#092328]">{bulletin.last_reviewed}</span>
                </div>
              </div>

              {/* Policy Summary */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-[#698579] mb-1.5">
                  Policy Summary & Reason for Rule Update
                </h4>
                <div className="p-3.5 rounded-xl bg-[#FFFDF5] border border-[#FDE68A] text-[#92400E] leading-relaxed">
                  <p className="font-medium">{bulletin.summary}</p>
                </div>
              </div>

              {/* Clinical Coverage Criteria */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-[#698579] mb-2">
                  Mandatory Coverage Criteria & Pre-Requisites
                </h4>
                <div className="space-y-2">
                  {bulletin.coverage_criteria.map((criteria, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2.5 p-2.5 rounded-lg bg-[#F8FAF9] border border-[#E8EFEA]"
                    >
                      <span className="w-5 h-5 rounded-full bg-[#EBF4EE] text-[#2A835F] flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
                        {i + 1}
                      </span>
                      <span className="text-[#092328] font-medium text-xs leading-relaxed">
                        {criteria}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Denial Risk Warning */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-[#DC2626] mb-1.5 flex items-center gap-1.5">
                  <svg className="w-4 h-4 text-[#DC2626]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <span>Denial Risk If Submitted Without Fulfillment</span>
                </h4>
                <div className="p-3 rounded-xl bg-red-50/70 border border-red-200 text-red-900 text-xs leading-relaxed">
                  {bulletin.denial_risk}
                </div>
              </div>

              {/* External Link */}
              {bulletin.official_reference_url && (
                <div className="pt-3 pb-1 flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-t border-[#E8EFEA] bg-[#F8FAF9] -mx-6 -mb-6 p-4 rounded-b-2xl">
                  <div>
                    <span className="block text-xs font-bold text-[#092328]">Official Insurer Policy Document</span>
                    <span className="text-[11px] text-[#698579]">Direct link to verified publication on payer portal</span>
                  </div>
                  <a
                    href={bulletin.official_reference_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#2A835F] text-white text-xs font-bold hover:bg-[#1F6347] transition-colors shadow-2xs"
                  >
                    <span>Open Official Document</span>
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-[#E8EFEA] bg-[#F8FAF9] flex items-center justify-between">
          <span className="text-[11px] text-[#698579]">
            CoverageGuard Deterministic Citation · Read-Only Scoped Access
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-[#092328] text-white text-xs font-semibold hover:bg-[#133E46] transition-colors"
          >
            Done Reviewing
          </button>
        </div>
      </div>
    </div>
  );
};
