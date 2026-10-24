import React, { useState } from 'react';
import { DashboardData } from '../types';

interface DashboardPageProps {
  data: DashboardData | null;
  onNavigateToUpdates: () => void;
  onNavigateToCasesWithFilter?: (status?: string, specialty?: string) => void;
  onUpdateTarget?: (target: number) => Promise<void>;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  data,
  onNavigateToUpdates,
  onNavigateToCasesWithFilter,
  onUpdateTarget,
}) => {
  const [isEditingTarget, setIsEditingTarget] = useState(false);
  const [targetInput, setTargetInput] = useState<string>(
    data?.clean_claims.target ? String(data.clean_claims.target) : '85'
  );

  if (!data) {
    return (
      <div className="py-20 text-center text-sm font-semibold text-[#12544F]">
        Loading dashboard...
      </div>
    );
  }

  const { counts, clean_claims, specialties, latest_updates } = data;

  const handleSaveTarget = async (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = parseFloat(targetInput);
    if (!isNaN(parsed) && parsed > 0 && parsed <= 100 && onUpdateTarget) {
      await onUpdateTarget(parsed);
      setIsEditingTarget(false);
    }
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto py-8 px-6">
      {/* ------------------------------------------------------------- */}
      {/* ROW 1: Three number cards, nothing else in the row            */}
      {/* ------------------------------------------------------------- */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Approved Card (Green) */}
        <div
          onClick={() => onNavigateToCasesWithFilter && onNavigateToCasesWithFilter('Approved')}
          className="bg-white border border-[#D8E5DC] rounded-2xl p-6 shadow-sm hover:border-[#2A835F] transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[#12544F]/80 uppercase tracking-wider">
              Approved
            </span>
            <span className="h-2.5 w-2.5 rounded-full bg-[#2A835F]" />
          </div>
          <div className="mt-3 text-4xl font-extrabold text-[#2A835F] tracking-tight">
            {counts.approved}
          </div>
          <p className="mt-2 text-xs text-[#12544F]/70">
            Cases that are complete and covered.
          </p>
        </div>

        {/* Needs attention Card (Amber/Yellow) */}
        <div
          onClick={() => onNavigateToCasesWithFilter && onNavigateToCasesWithFilter('Needs attention')}
          className="bg-white border border-[#D8E5DC] rounded-2xl p-6 shadow-sm hover:border-[#D97706] transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[#12544F]/80 uppercase tracking-wider">
              Needs attention
            </span>
            <span className="h-2.5 w-2.5 rounded-full bg-[#D97706]" />
          </div>
          <div className="mt-3 text-4xl font-extrabold text-[#D97706] tracking-tight">
            {counts.needs_attention}
          </div>
          <p className="mt-2 text-xs text-[#12544F]/70">
            An update or rule affects the case.
          </p>
        </div>

        {/* Missing or wrong info Card (Red) */}
        <div
          onClick={() => onNavigateToCasesWithFilter && onNavigateToCasesWithFilter('Missing or wrong info')}
          className="bg-white border border-[#D8E5DC] rounded-2xl p-6 shadow-sm hover:border-[#DC2626] transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[#12544F]/80 uppercase tracking-wider">
              Missing or wrong info
            </span>
            <span className="h-2.5 w-2.5 rounded-full bg-[#DC2626]" />
          </div>
          <div className="mt-3 text-4xl font-extrabold text-[#DC2626] tracking-tight">
            {counts.missing_or_wrong_info}
          </div>
          <p className="mt-2 text-xs text-[#12544F]/70">
            A required document, number or field is missing, or a value is wrong.
          </p>
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* ROW 2: Clean claims submission (left) | Cases by specialty (right) */}
      {/* ------------------------------------------------------------- */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Row 2 Left: Clean claims submission */}
        <div className="bg-white border border-[#D8E5DC] rounded-2xl p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-[#092328]">
                Clean claims submission
              </h2>

              {/* Editable Target Marker Label */}
              {isEditingTarget ? (
                <form onSubmit={handleSaveTarget} className="flex items-center space-x-1">
                  <input
                    type="number"
                    min="1"
                    max="100"
                    step="0.1"
                    value={targetInput}
                    onChange={(e) => setTargetInput(e.target.value)}
                    className="w-14 px-1.5 py-0.5 text-xs border border-[#2A835F] rounded focus:outline-none"
                    autoFocus
                  />
                  <button
                    type="submit"
                    className="px-2 py-0.5 bg-[#2A835F] text-white rounded text-xs font-bold cursor-pointer"
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsEditingTarget(false)}
                    className="px-1 text-xs text-[#12544F]/70 hover:text-[#092328]"
                  >
                    Cancel
                  </button>
                </form>
              ) : (
                <button
                  onClick={() => setIsEditingTarget(true)}
                  className="inline-flex items-center gap-1 text-xs font-bold text-[#12544F]/80 hover:text-[#092328] hover:underline cursor-pointer"
                  title="Click to edit target percentage"
                >
                  <span>Target {clean_claims.target}%</span>
                  <svg className="w-3 h-3 text-[#12544F]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                </button>
              )}
            </div>

            {/* Big Percentage */}
            <div className="mt-4 flex items-baseline space-x-2">
              <span className="text-5xl font-black text-[#092328] tracking-tight">
                {clean_claims.percentage}%
              </span>
              <span className="text-xs font-semibold text-[#12544F]/70">
                ({clean_claims.approved_count} of {clean_claims.total_checked} cases complete & covered)
              </span>
            </div>
          </div>

          {/* Horizontal Progress Bar with Target Marker */}
          <div className="mt-6">
            <div className="relative w-full h-4 bg-[#F0F5F2] rounded-full overflow-visible border border-[#D8E5DC]">
              {/* Actual Clean Percentage Fill */}
              <div
                className="h-full bg-[#2A835F] rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, clean_claims.percentage)}%` }}
              />

              {/* Target Marker */}
              <div
                className="absolute top-[-4px] bottom-[-4px] w-0.5 bg-[#092328] z-10"
                style={{ left: `${Math.min(100, clean_claims.target)}%` }}
                title={`Target ${clean_claims.target}%`}
              >
                <span className="absolute -top-5 -translate-x-1/2 text-[10px] font-extrabold text-[#092328] whitespace-nowrap bg-white px-1 rounded shadow-xs border border-[#D8E5DC]">
                  Target {clean_claims.target}%
                </span>
              </div>
            </div>

            <div className="flex justify-between mt-2 text-[10px] text-[#12544F]/60 font-semibold">
              <span>0%</span>
              <span>100%</span>
            </div>
          </div>
        </div>

        {/* Row 2 Right: Cases by specialty */}
        <div className="bg-white border border-[#D8E5DC] rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-[#092328]">
              Cases by specialty
            </h2>
            {/* Legend showing identical 3 status colors */}
            <div className="flex items-center space-x-3 text-[10px] font-bold">
              <span className="inline-flex items-center space-x-1 text-[#2A835F]">
                <span className="h-2 w-2 rounded-full bg-[#2A835F]" />
                <span>Approved</span>
              </span>
              <span className="inline-flex items-center space-x-1 text-[#D97706]">
                <span className="h-2 w-2 rounded-full bg-[#D97706]" />
                <span>Needs attention</span>
              </span>
              <span className="inline-flex items-center space-x-1 text-[#DC2626]">
                <span className="h-2 w-2 rounded-full bg-[#DC2626]" />
                <span>Missing/wrong</span>
              </span>
            </div>
          </div>

          {/* Horizontal Bars, sorted by count descending */}
          <div className="space-y-3 pt-1">
            {!specialties.some((s) => s.total > 0) ? (
              <div className="py-8 text-center text-xs text-[#698579] space-y-1">
                <p className="font-semibold text-[#092328]">No active caseload entries</p>
                <p>Upload a clinical file to populate specialty statistics.</p>
              </div>
            ) : (
              specialties.filter((s) => s.total > 0).map((item) => {
                const total = item.total;
                const appPct = total > 0 ? (item.approved / total) * 100 : 0;
                const naPct = total > 0 ? (item.needs_attention / total) * 100 : 0;
                const mwiPct = total > 0 ? (item.missing_or_wrong_info / total) * 100 : 0;

                return (
                  <div
                    key={item.specialty}
                    onClick={() => onNavigateToCasesWithFilter && onNavigateToCasesWithFilter(undefined, item.specialty)}
                    className="space-y-1 cursor-pointer group"
                    title={`View ${item.specialty} cases`}
                  >
                    <div className="flex justify-between text-xs font-semibold text-[#092328]">
                      <span className="group-hover:text-[#2A835F] transition-colors">
                        {item.specialty}
                      </span>
                      <span className="font-bold text-[#12544F]">
                        {item.total}
                      </span>
                    </div>

                    {/* Split horizontal bar using exact same 3 colors */}
                    <div className="w-full h-3 bg-[#F0F5F2] rounded-full overflow-hidden flex border border-[#D8E5DC]">
                      {item.approved > 0 && (
                        <div
                          style={{ width: `${appPct}%` }}
                          className="h-full bg-[#2A835F]"
                          title={`Approved: ${item.approved}`}
                        />
                      )}
                      {item.needs_attention > 0 && (
                        <div
                          style={{ width: `${naPct}%` }}
                          className="h-full bg-[#D97706]"
                          title={`Needs attention: ${item.needs_attention}`}
                        />
                      )}
                      {item.missing_or_wrong_info > 0 && (
                        <div
                          style={{ width: `${mwiPct}%` }}
                          className="h-full bg-[#DC2626]"
                          title={`Missing or wrong info: ${item.missing_or_wrong_info}`}
                        />
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* ROW 3: Latest updates (the 3 most recent)                     */}
      {/* ------------------------------------------------------------- */}
      <div className="bg-white border border-[#D8E5DC] rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-[#EAEFEA] pb-3">
          <h2 className="text-sm font-bold text-[#092328]">
            Latest updates
          </h2>
          <button
            onClick={onNavigateToUpdates}
            className="text-xs font-bold text-[#2A835F] hover:text-[#12544F] hover:underline cursor-pointer"
          >
            View all updates →
          </button>
        </div>

        {/* 3 Most Recent Updates */}
        <div className="space-y-3">
          {latest_updates.length === 0 ? (
            <div className="py-6 text-center text-xs text-[#698579]">
              No active policy circular notifications.
            </div>
          ) : (
            latest_updates.map((update) => (
              <div
                key={update.update_id}
                onClick={onNavigateToUpdates}
                className="flex flex-col sm:flex-row sm:items-center justify-between text-xs py-2 px-3 rounded-xl hover:bg-[#F0F5F2] transition-colors cursor-pointer border border-transparent hover:border-[#D8E5DC]"
              >
                {/* What changed */}
                <div className="font-semibold text-[#092328] flex-1 pr-4 truncate">
                  {update.headline}
                </div>

                {/* Effective date and number of open cases affected */}
                <div className="flex items-center space-x-4 shrink-0 text-[#12544F]/80 mt-1 sm:mt-0 font-medium">
                  <span>Effective {update.effective_date}</span>
                  <span>·</span>
                  <span
                    className={
                      update.affected_cases_count > 0
                        ? 'font-bold text-[#D97706]'
                        : 'text-[#12544F]/60'
                    }
                  >
                    Affects {update.affected_cases_count} open {update.affected_cases_count === 1 ? 'case' : 'cases'}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
