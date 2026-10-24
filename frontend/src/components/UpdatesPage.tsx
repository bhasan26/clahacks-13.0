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

  return (
    <div className="space-y-6 max-w-6xl mx-auto py-8 px-6">
      {/* Top Header */}
      <div>
        <h1 className="text-xl font-black text-[#092328] tracking-tight">
          Insurer Updates
        </h1>
        <p className="text-xs text-[#12544F]/70 mt-0.5">
          Recent policy, formulary, and prior authorization updates received from the insurer.
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
          filteredUpdates.map((update) => (
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
                  <span className="font-mono text-[11px] text-[#12544F]/60">Rule {update.rule_id}</span>
                </div>

                <div>
                  {update.affected_cases_count > 0 ? (
                    <button
                      onClick={() => onViewAffectedCases(update.affected_case_ids)}
                      className="font-bold text-[#D97706] hover:underline cursor-pointer flex items-center space-x-1"
                    >
                      <span>Affects {update.affected_cases_count} open {update.affected_cases_count === 1 ? 'case' : 'cases'}</span>
                      <span>→</span>
                    </button>
                  ) : (
                    <span className="text-[#12544F]/50">Affects 0 open cases</span>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
