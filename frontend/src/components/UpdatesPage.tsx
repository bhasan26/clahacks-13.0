import React, { useState } from 'react';
import { InsurerUpdateEntry } from '../types';

interface UpdatesPageProps {
  updates: InsurerUpdateEntry[];
  onViewAffectedCases: (caseIds: string[]) => void;
}

export const UpdatesPage: React.FC<UpdatesPageProps> = ({
  updates,
  onViewAffectedCases,
}) => {
  const [typeFilter, setTypeFilter] = useState<string>('All');

  const types = ['All', 'Drug', 'Procedure', 'Document', 'Approval'];

  const filteredUpdates = updates.filter((u) => {
    if (typeFilter === 'All') return true;
    return u.item_type.toLowerCase() === typeFilter.toLowerCase();
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'Effective':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#2A835F]/15 text-[#2A835F] border border-[#2A835F]/30">
            Effective
          </span>
        );
      case 'Announced':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#D97706]/15 text-[#D97706] border border-[#D97706]/30">
            Announced
          </span>
        );
      case 'Delayed':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-300">
            Delayed
          </span>
        );
      case 'Cancelled':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-500 border border-slate-200 line-through">
            Cancelled
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-600">
            {status}
          </span>
        );
    }
  };

  const [expandedUpdateId, setExpandedUpdateId] = useState<string | null>(null);

  return (
    <div className="space-y-6 max-w-6xl mx-auto py-8 px-6">
      {/* Top Header */}
      <div>
        <h1 className="text-xl font-black text-[#092328] tracking-tight">
          Insurer Updates & Policy Action Center
        </h1>
        <p className="text-xs text-[#12544F]/70 mt-0.5">
          Human-reviewed policy updates and synthetic demo notices, with claim-impact tracking.
        </p>
      </div>

      {/* Filter by Type */}
      <div className="bg-white border border-[#D8E5DC] rounded-2xl p-4 shadow-sm flex items-center space-x-2">
        <span className="text-xs font-bold text-[#12544F]/70">Filter by type:</span>
        <div className="flex items-center space-x-1">
          {types.map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                typeFilter === t
                  ? 'bg-[#092328] text-white'
                  : 'text-[#12544F]/80 hover:bg-[#F0F5F2]'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Reverse-Chronological List of Updates */}
      <div className="space-y-3">
        {filteredUpdates.length === 0 ? (
          <div className="p-12 text-center text-xs text-[#12544F]/60 bg-white rounded-2xl border border-[#D8E5DC]">
            No updates found for the selected type.
          </div>
        ) : (
          filteredUpdates.map((update) => {
            const isExpanded = expandedUpdateId === update.update_id;
            return (
              <div
                key={update.update_id}
                className="bg-white border border-[#D8E5DC] rounded-2xl p-5 shadow-sm space-y-3 hover:border-[#12544F]/40 transition-colors"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center space-x-2.5">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-[#F0F5F2] text-[#12544F] border border-[#D8E5DC]">
                      {update.item_type}
                    </span>
                    <h3 className="font-bold text-sm text-[#092328]">
                      {update.headline}
                    </h3>
                  </div>

                  <div className="flex items-center space-x-3 shrink-0">
                    {getStatusBadge(update.status)}
                  </div>
                </div>

                {/* Bottom metadata: Effective date, Rule reference, Affects N open cases */}
                <div className="flex flex-wrap items-center justify-between pt-2 border-t border-[#EAEFEA] text-xs text-[#12544F]/80">
                  <div className="flex items-center space-x-2">
                    <span>Effective: <strong className="text-[#092328]">{update.effective_date}</strong></span>
                    <span>·</span>
                    <span className="font-mono text-[11px] text-[#12544F]/60">Rule {update.rule_id} v{update.rule_version}</span>
                  </div>

                  <div className="flex items-center space-x-3">
                    {update.affected_cases_count > 0 ? (
                      <>
                        <button
                          onClick={() => setExpandedUpdateId(isExpanded ? null : update.update_id)}
                          className="text-xs font-bold text-[#12544F] hover:underline cursor-pointer flex items-center space-x-1"
                        >
                          <span>{isExpanded ? 'Hide Impacted Claims' : 'View Impacted Claims'}</span>
                          <span>{isExpanded ? '▲' : '▼'}</span>
                        </button>
                        <button
                          onClick={() => onViewAffectedCases(update.affected_case_ids)}
                          className="px-2.5 py-1 rounded-lg bg-[#D97706]/10 text-[#D97706] hover:bg-[#D97706]/20 font-bold text-xs cursor-pointer flex items-center space-x-1"
                        >
                          <span>Affects {update.affected_cases_count} {update.affected_cases_count === 1 ? 'case' : 'cases'}</span>
                          <span>→</span>
                        </button>
                      </>
                    ) : (
                      <span className="text-[#12544F]/50">Affects 0 open cases</span>
                    )}
                  </div>
                </div>

                {/* Expandable Explainable Action Center Checklist for Affected Claims */}
                {isExpanded && update.affected_cases_count > 0 && (
                  <div className="mt-3 pt-3 border-t border-[#F59E0B]/30 bg-[#FFFBEB]/60 rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-extrabold text-[#92400E] uppercase tracking-wider flex items-center gap-1.5">
                        <span>🛡️ Action Center: Impacted Claims Queue</span>
                      </span>
                      <button
                        onClick={() => onViewAffectedCases(update.affected_case_ids)}
                        className="text-xs font-bold text-[#92400E] hover:underline cursor-pointer"
                      >
                        Inspect all in Cases table →
                      </button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                      {update.affected_case_ids.map((cid) => (
                        <div
                          key={cid}
                          onClick={() => onViewAffectedCases([cid])}
                          className="p-3 bg-white rounded-xl border border-[#F59E0B]/30 hover:border-[#D97706] shadow-xs cursor-pointer transition-all space-y-1.5"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-mono font-black text-xs text-[#092328]">
                              Claim {cid}
                            </span>
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#F59E0B]/15 text-[#B45309]">
                              Denial Risk
                            </span>
                          </div>
                          <p className="text-[11px] text-[#12544F]/80">
                            Service scheduled on or after {update.effective_date}. Rule mandate applies.
                          </p>
                          <span className="text-[10px] font-bold text-[#2A835F] hover:underline block pt-1">
                            Open Case & Action Checklist →
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
