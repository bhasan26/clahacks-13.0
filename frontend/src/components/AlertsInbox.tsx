import React, { useState } from 'react';
import {
  AlertCircle,
  CheckCircle,
  ArrowRight,
  ShieldAlert,
  Check,
  MessageSquare,
  Clock,
  FileWarning,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { Alert, CaseSummary } from '../types';

interface AlertsInboxProps {
  alerts: Alert[];
  cases?: CaseSummary[];
  onSelectCase: (caseId: string) => void;
  onAcknowledge: (alertId: string, note?: string) => void;
}

export const AlertsInbox: React.FC<AlertsInboxProps> = ({
  alerts,
  cases,
  onSelectCase,
  onAcknowledge,
}) => {
  const [filter, setFilter] = useState<'all' | 'open' | 'closed'>('all');
  const [notePromptId, setNotePromptId] = useState<string | null>(null);
  const [officerNote, setOfficerNote] = useState('');

  const openAlerts = alerts.filter((a) => a.status === 'open');
  const totalOpenClaims = cases?.length ?? 30;
  const affectedCaseIds = Array.from(new Set(openAlerts.map((a) => a.case_id)));
  const affectedCount = affectedCaseIds.length;
  const safeCount = Math.max(0, totalOpenClaims - affectedCount);

  const filteredAlerts = alerts.filter((a) => {
    if (filter === 'open') return a.status === 'open';
    if (filter === 'closed') return a.status === 'closed' || a.status === 'superseded';
    return true;
  });

  const handleConfirmAcknowledge = (alertId: string) => {
    onAcknowledge(alertId, officerNote || undefined);
    setNotePromptId(null);
    setOfficerNote('');
  };

  return (
    <div className="space-y-6">
      {/* Top Bar / Filters */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900 flex items-center space-x-2">
            <span>Payer Policy Impact Alerts</span>
            <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-200">
              {openAlerts.length} Action Needed
            </span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Real-time notifications generated when insurer rule modifications impact open patient claims.
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex bg-slate-100 p-1 rounded-2xl border border-slate-200/80 text-xs font-semibold">
          <button
            onClick={() => setFilter('all')}
            className={`px-3 py-1.5 rounded-xl transition-all cursor-pointer ${
              filter === 'all'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            All ({alerts.length})
          </button>
          <button
            onClick={() => setFilter('open')}
            className={`px-3 py-1.5 rounded-xl transition-all cursor-pointer ${
              filter === 'open'
                ? 'bg-rose-500 text-white font-bold shadow-sm'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            Open ({openAlerts.length})
          </button>
          <button
            onClick={() => setFilter('closed')}
            className={`px-3 py-1.5 rounded-xl transition-all cursor-pointer ${
              filter === 'closed'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            Closed ({alerts.filter((a) => a.status !== 'open').length})
          </button>
        </div>
      </div>

      {/* Executive Policy Impact & Caseload Summary (The User's Highlighted Requirement) */}
      {openAlerts.length > 0 && (
        <div className="p-6 rounded-3xl bg-gradient-to-br from-amber-50/80 via-white to-rose-50/60 border-2 border-amber-300 shadow-[0_4px_20px_rgba(245,158,11,0.08)] space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-amber-200/60 pb-3">
            <div className="flex items-center space-x-2.5">
              <span className="flex h-3 w-3 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
              </span>
              <span className="text-xs font-extrabold uppercase tracking-wider text-amber-900 bg-amber-200/70 px-2.5 py-0.5 rounded-full border border-amber-300/80 flex items-center space-x-1.5">
                <Sparkles className="h-3 w-3 text-amber-800" />
                <span>Executive Payer Exclusion Notice</span>
              </span>
            </div>
            <span className="text-xs text-slate-500 font-mono font-semibold">
              Live Sentinel Agent Scan
            </span>
          </div>

          <div className="space-y-1.5">
            <h3 className="text-lg sm:text-xl font-black text-slate-900 flex items-center space-x-2">
              <span>📢 Insurer A no longer covers DRUG-A effective Nov 1, 2026</span>
            </h3>
            <p className="text-sm font-semibold text-slate-700 leading-relaxed">
              Of the <strong className="text-slate-900 font-black underline decoration-amber-400">{totalOpenClaims} open claims</strong> evaluated in the hospital system, these <span className="text-rose-600 font-black text-base bg-rose-100 px-2 py-0.5 rounded-md border border-rose-200">{affectedCount} claims are affected</span>:
            </p>
          </div>

          {/* Affected Case Chips */}
          <div className="flex flex-wrap items-center gap-2.5 pt-1">
            {affectedCaseIds.map((cid) => {
              const matchedCase = cases?.find((c) => c.case.case_id === cid)?.case;
              const svcDate = matchedCase?.service_date ?? 'Nov 2026';
              return (
                <button
                  key={cid}
                  onClick={() => onSelectCase(cid)}
                  className="group inline-flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-900 border border-rose-200 hover:border-rose-300 transition-all text-xs font-bold shadow-sm cursor-pointer active:scale-95"
                >
                  <FileWarning className="h-4 w-4 text-rose-600 group-hover:scale-110 transition-transform" />
                  <span>Case {cid}</span>
                  <span className="text-[11px] text-rose-700 font-normal">({svcDate})</span>
                  <ArrowRight className="h-3.5 w-3.5 text-rose-600 group-hover:translate-x-1 transition-transform" />
                </button>
              );
            })}
          </div>

          {/* Caseload Breakdown & Protected Claims Context */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-slate-200/60 text-xs">
            <div className="flex items-center space-x-2 text-emerald-700">
              <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-600" />
              <span>
                <strong className="text-slate-900 font-bold">{safeCount} claims safe & compliant</strong> (e.g. Case C-002 scheduled Oct 28 precedes the Nov 1 cutoff date).
              </span>
            </div>

            <div className="text-amber-900 font-bold bg-amber-100 px-3 py-1 rounded-lg border border-amber-200">
              ⚠️ Action: Obtain Prior Authorization before filing to prevent immediate claim denial.
            </div>
          </div>
        </div>
      )}

      {/* Alerts Feed */}
      {filteredAlerts.length === 0 ? (
        <div className="p-12 text-center rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div className="h-12 w-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto mb-3">
            <CheckCircle className="h-6 w-6" />
          </div>
          <h3 className="text-sm font-bold text-slate-900">No Policy Alerts in this View</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            All open patient claims comply with current insurer coverage rules. Use the simulator below to test live change events.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredAlerts.map((alert) => {
            const isOpen = alert.status === 'open';
            const isClosed = alert.status === 'closed';

            return (
              <div
                key={alert.alert_id}
                className={`p-6 rounded-3xl border transition-all ${
                  isOpen
                    ? 'bg-white border-2 border-amber-300 shadow-md shadow-amber-500/5'
                    : isClosed
                    ? 'bg-white/90 border border-slate-200 shadow-sm'
                    : 'bg-white/70 border border-slate-200 opacity-70'
                }`}
              >
                <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
                  {/* Left: Icon & Core Details */}
                  <div className="flex items-start space-x-4">
                    <div
                      className={`p-3 rounded-2xl shrink-0 mt-0.5 ${
                        isOpen
                          ? 'bg-amber-100 text-amber-800 border border-amber-200'
                          : isClosed
                          ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {isOpen ? (
                        <ShieldAlert className="h-5 w-5" />
                      ) : (
                        <CheckCircle className="h-5 w-5" />
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-mono font-bold text-slate-500">
                          {alert.alert_id}
                        </span>

                        {/* Status Badge */}
                        <span
                          className={`text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${
                            isOpen
                              ? 'bg-amber-100 text-amber-800 border-amber-200'
                              : isClosed
                              ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                              : 'bg-slate-100 text-slate-600 border-slate-200'
                          }`}
                        >
                          {alert.status}
                        </span>

                        {/* Rule Version Diff */}
                        <span className="text-xs font-mono font-bold text-slate-700 bg-slate-100 border border-slate-200 px-2.5 py-0.5 rounded-lg">
                          Rule {alert.rule_id} (v{alert.change.from_version ?? 1} → v{alert.change.to_version})
                        </span>

                        {/* Created time */}
                        <span className="text-[11px] text-slate-400 flex items-center space-x-1 font-medium">
                          <Clock className="h-3 w-3" />
                          <span>{new Date(alert.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        </span>
                      </div>

                      <h3 className="text-base font-bold text-slate-900">
                        {alert.headline || `Rule change affects Case ${alert.case_id}`}
                      </h3>

                      <p className="text-xs text-slate-600 leading-relaxed max-w-3xl">
                        {alert.explanation}
                      </p>

                      {/* Closed Reason or Suggested Officer Action */}
                      {isClosed && alert.closed_reason && (
                        <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-xl bg-emerald-50 border border-emerald-200 text-xs font-bold text-emerald-800 mt-1">
                          <Check className="h-3.5 w-3.5" />
                          <span>Resolved: {alert.closed_reason}</span>
                        </div>
                      )}

                      {isOpen && alert.suggested_action && (
                        <div className="text-xs text-amber-900 font-bold bg-amber-50 border border-amber-200 px-3.5 py-2 rounded-xl mt-2 inline-block">
                          💡 Recommended Action: {alert.suggested_action}
                        </div>
                      )}

                      {/* Officer Acknowledged Note */}
                      {alert.acknowledged && (
                        <div className="text-[11px] text-slate-500 italic flex items-center space-x-1 mt-1 font-medium">
                          <MessageSquare className="h-3 w-3 text-slate-400" />
                          <span>Acknowledged by Officer {alert.officer_note ? `("${alert.officer_note}")` : ''}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right: Actions */}
                  <div className="flex flex-row lg:flex-col items-center lg:items-end justify-between w-full lg:w-auto shrink-0 gap-2.5 pt-3 lg:pt-0 border-t border-slate-100 lg:border-t-0">
                    <button
                      onClick={() => onSelectCase(alert.case_id)}
                      className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-slate-900 hover:bg-slate-800 text-white shadow-sm transition-all active:scale-95 cursor-pointer"
                    >
                      <span>Inspect Case {alert.case_id}</span>
                      <ArrowRight className="h-3.5 w-3.5 text-lime-400" />
                    </button>

                    {isOpen && !alert.acknowledged && (
                      <div>
                        {notePromptId === alert.alert_id ? (
                          <div className="flex items-center space-x-1.5">
                            <input
                              type="text"
                              value={officerNote}
                              onChange={(e) => setOfficerNote(e.target.value)}
                              placeholder="Officer note..."
                              className="text-xs bg-white border border-slate-300 rounded-xl px-2.5 py-1 text-slate-900 focus:outline-none focus:border-slate-500 shadow-sm"
                            />
                            <button
                              onClick={() => handleConfirmAcknowledge(alert.alert_id)}
                              className="px-3 py-1 rounded-xl bg-slate-900 text-white text-xs font-bold cursor-pointer"
                            >
                              Save
                            </button>
                            <button
                              onClick={() => setNotePromptId(null)}
                              className="px-2 py-1 rounded-xl bg-slate-100 text-slate-500 text-xs cursor-pointer"
                            >
                              ✕
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setNotePromptId(alert.alert_id)}
                            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-bold text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 border border-slate-200 transition-all cursor-pointer"
                          >
                            <Check className="h-3.5 w-3.5 text-emerald-600" />
                            <span>Mark Acknowledged</span>
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
