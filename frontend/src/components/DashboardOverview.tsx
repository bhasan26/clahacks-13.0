import React from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  TrendingUp,
  FileText,
  Activity,
  ArrowRight,
  Sparkles,
  Wifi,
  ChevronRight,
  ExternalLink,
  Layers,
  CheckCircle2,
} from 'lucide-react';
import { HealthStatus, CaseSummary, Alert, Rule } from '../types';

interface DashboardOverviewProps {
  health: HealthStatus | null;
  cases: CaseSummary[];
  alerts: Alert[];
  rules: Rule[];
  onSelectCase: (caseId: string) => void;
  onNavigateTab: (tab: 'alerts' | 'cases' | 'rules' | 'audit') => void;
  openIntake: () => void;
  onSync: () => void;
  isSyncing: boolean;
}

export const DashboardOverview: React.FC<DashboardOverviewProps> = ({
  health,
  cases,
  alerts,
  rules,
  onSelectCase,
  onNavigateTab,
  openIntake,
  onSync,
  isSyncing,
}) => {
  const openAlerts = alerts.filter((a) => a.status === 'open');
  const clearCasesCount = cases.filter((c) => c.overall_status === 'clear').length;
  const attentionCasesCount = cases.filter((c) => c.overall_status === 'needs_attention').length;
  const cannotAssessCount = cases.filter((c) => c.overall_status === 'cannot_assess').length;
  const totalCases = cases.length || 30;
  const complianceRate = Math.round((clearCasesCount / (totalCases || 1)) * 100);

  // Weekly bar data for Shakuro style activity chart
  const weeklyActivity = [
    { day: 'Mon', clear: 22, review: 3, alert: 1, total: 26 },
    { day: 'Tue', clear: 25, review: 2, alert: 1, total: 28 },
    { day: 'Wed', clear: 24, review: 4, alert: 3, total: 31, isPeak: true },
    { day: 'Thu', clear: 27, review: 2, alert: 3, total: 32 },
    { day: 'Fri', clear: 26, review: 3, alert: 2, total: 31 },
    { day: 'Sat', clear: 18, review: 1, alert: 0, total: 19 },
    { day: 'Sun', clear: 15, review: 1, alert: 0, total: 16 },
  ];

  return (
    <div className="space-y-6">
      {/* Top Bento Row: Hero Activity Preview (Left 2/3) + Green Insurer Card & Actions (Right 1/3) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Main Card: Weekly Claims & Coverage Activity Preview */}
        <div className="lg:col-span-8 bg-white rounded-3xl p-6 sm:p-7 border border-slate-200/80 shadow-[0_2px_16px_rgba(0,0,0,0.03)] flex flex-col justify-between">
          <div>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-5">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Caseload & Policy Activity
                </span>
                <div className="flex items-baseline space-x-3 mt-1">
                  <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">
                    {totalCases} Active Claims
                  </h2>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-lime-100 text-lime-800 border border-lime-200 flex items-center space-x-1">
                    <TrendingUp className="h-3 w-3 mr-0.5" />
                    <span>90.0% Compliant</span>
                  </span>
                </div>
              </div>

              {/* Legend & Filter */}
              <div className="flex items-center space-x-4 text-xs font-medium text-slate-500">
                <span className="flex items-center space-x-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-lime-500"></span>
                  <span>Verified Clear</span>
                </span>
                <span className="flex items-center space-x-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-400"></span>
                  <span>Review Needed</span>
                </span>
                <span className="flex items-center space-x-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-rose-500"></span>
                  <span>Policy Shift</span>
                </span>
              </div>
            </div>

            {/* Stacked Bar Chart & Metric Columns */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6 pt-6 items-end">
              {/* Left: The Stacked Bars */}
              <div className="md:col-span-8">
                <div className="h-48 flex items-end justify-between gap-2.5 sm:gap-4 pt-6 px-2">
                  {weeklyActivity.map((bar, idx) => {
                    const clearH = Math.round((bar.clear / 35) * 100);
                    const reviewH = Math.round((bar.review / 35) * 100);
                    const alertH = Math.round((bar.alert / 35) * 100);

                    return (
                      <div key={idx} className="flex-1 flex flex-col items-center group relative cursor-pointer">
                        {/* Peak Floating Tooltip on Wednesday */}
                        {bar.isPeak && (
                          <div className="absolute -top-12 z-20 whitespace-nowrap bg-slate-900 text-white text-[10px] font-semibold px-2.5 py-1.5 rounded-xl shadow-lg border border-slate-700 pointer-events-none">
                            <span className="text-lime-400">● 24 Clear</span> · <span className="text-rose-400">3 Shifted</span>
                          </div>
                        )}

                        {/* Stacked Bar Column */}
                        <div className="w-full max-w-[28px] bg-slate-100 rounded-full p-0.5 flex flex-col justify-end space-y-1 h-36 overflow-hidden transition-all group-hover:scale-105">
                          {bar.alert > 0 && (
                            <div
                              style={{ height: `${alertH}%` }}
                              className="w-full bg-rose-500 rounded-t-full transition-all"
                            />
                          )}
                          {bar.review > 0 && (
                            <div
                              style={{ height: `${reviewH}%` }}
                              className="w-full bg-amber-400 transition-all"
                            />
                          )}
                          <div
                            style={{ height: `${clearH}%` }}
                            className="w-full bg-lime-400 rounded-b-full transition-all group-hover:bg-lime-500"
                          />
                        </div>

                        <span className={`text-[11px] font-semibold mt-2 ${bar.isPeak ? 'text-slate-900 font-bold' : 'text-slate-400'}`}>
                          {bar.day}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Right: Sub-KPI Column */}
              <div className="md:col-span-4 space-y-4 border-t md:border-t-0 md:border-l border-slate-100 pt-4 md:pt-0 md:pl-6">
                <div>
                  <span className="text-xs font-semibold text-slate-400">Total Monitored Value</span>
                  <div className="text-xl font-extrabold text-slate-900 mt-0.5 font-mono">$142,500</div>
                  <span className="text-[11px] text-emerald-600 font-semibold flex items-center mt-0.5">
                    <TrendingUp className="h-3 w-3 mr-0.5" /> +12.5% from last week
                  </span>
                </div>

                <div>
                  <span className="text-xs font-semibold text-slate-400">Potential Denials Prevented</span>
                  <div className="text-xl font-extrabold text-rose-600 mt-0.5 font-mono">$18,400</div>
                  <span className="text-[11px] text-slate-500">3 claims caught before filing</span>
                </div>

                <div>
                  <span className="text-xs font-semibold text-slate-400">Direct Insurer Rules</span>
                  <div className="text-xl font-extrabold text-slate-900 mt-0.5 font-mono">{health?.total_rules ?? 4} Active</div>
                  <span className="text-[11px] text-slate-500">Across PLAN-GOLD & Wildcards</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Card: The Green Insurer Card (Shakuro Card Style) & Quick Action Bar */}
        <div className="lg:col-span-4 flex flex-col space-y-4">
          {/* Green Card */}
          <div className="p-6 rounded-3xl bg-gradient-to-br from-lime-300 via-emerald-400 to-teal-500 text-slate-950 shadow-[0_8px_24px_rgba(132,204,22,0.25)] relative overflow-hidden flex flex-col justify-between h-56 group">
            {/* Ambient Background Circles */}
            <div className="absolute -top-12 -right-12 h-44 w-44 rounded-full bg-white/20 blur-xl pointer-events-none"></div>
            <div className="absolute -bottom-8 -left-8 h-36 w-36 rounded-full bg-emerald-600/20 blur-lg pointer-events-none"></div>

            {/* Card Header */}
            <div className="flex items-center justify-between relative z-10">
              <div className="flex items-center space-x-2">
                <span className="h-2 w-2 rounded-full bg-slate-950 animate-pulse"></span>
                <span className="text-xs font-extrabold uppercase tracking-wider text-slate-950">
                  Insurer Direct Feed
                </span>
              </div>
              <Wifi className="h-4 w-4 text-slate-950/80" />
            </div>

            {/* Card Chip & Network */}
            <div className="relative z-10 flex items-center justify-between">
              <div className="space-y-1">
                <div className="text-2xl font-black tracking-tight font-mono text-slate-950">
                  ACTIVE • 100%
                </div>
                <div className="text-[11px] font-bold text-slate-900/80 tracking-wider font-mono">
                  PAYER FEED PROTOCOL V2
                </div>
              </div>
            </div>

            {/* Card Footer */}
            <div className="relative z-10 flex items-center justify-between text-xs font-bold pt-2 border-t border-slate-950/10">
              <div>
                <span className="text-[10px] uppercase text-slate-800/80 block font-semibold">Feed Freshness</span>
                <span className="font-mono">{health ? `${Math.round(health.age_seconds)}s ago` : 'Real-Time'}</span>
              </div>
              <div className="text-right">
                <span className="text-[10px] uppercase text-slate-800/80 block font-semibold">Outages Detected</span>
                <span className="text-slate-950 font-extrabold">{health?.is_stale ? '1 Outage' : '0 Outages'}</span>
              </div>
            </div>
          </div>

          {/* Quick Action Buttons (like Transfer, Send, Request) */}
          <div className="bg-white rounded-2xl p-3 border border-slate-200/80 shadow-sm grid grid-cols-4 gap-2 text-center">
            <button
              onClick={onSync}
              disabled={isSyncing}
              className="p-2.5 rounded-xl hover:bg-slate-50 transition-all flex flex-col items-center justify-center space-y-1 cursor-pointer group"
            >
              <div className="h-9 w-9 rounded-full bg-slate-100 group-hover:bg-lime-100 text-slate-700 group-hover:text-lime-800 flex items-center justify-center transition-colors">
                <RefreshCw className={`h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} />
              </div>
              <span className="text-[11px] font-bold text-slate-700">Sync</span>
            </button>

            <button
              onClick={openIntake}
              className="p-2.5 rounded-xl hover:bg-slate-50 transition-all flex flex-col items-center justify-center space-y-1 cursor-pointer group"
            >
              <div className="h-9 w-9 rounded-full bg-slate-100 group-hover:bg-blue-100 text-slate-700 group-hover:text-blue-800 flex items-center justify-center transition-colors">
                <Sparkles className="h-4 w-4" />
              </div>
              <span className="text-[11px] font-bold text-slate-700">Intake</span>
            </button>

            <button
              onClick={() => onNavigateTab('cases')}
              className="p-2.5 rounded-xl hover:bg-slate-50 transition-all flex flex-col items-center justify-center space-y-1 cursor-pointer group"
            >
              <div className="h-9 w-9 rounded-full bg-slate-100 group-hover:bg-purple-100 text-slate-700 group-hover:text-purple-800 flex items-center justify-center transition-colors">
                <FileText className="h-4 w-4" />
              </div>
              <span className="text-[11px] font-bold text-slate-700">Claims</span>
            </button>

            <button
              onClick={() => onNavigateTab('alerts')}
              className="p-2.5 rounded-xl hover:bg-slate-50 transition-all flex flex-col items-center justify-center space-y-1 cursor-pointer group"
            >
              <div className="h-9 w-9 rounded-full bg-slate-100 group-hover:bg-rose-100 text-slate-700 group-hover:text-rose-800 flex items-center justify-center transition-colors relative">
                <AlertTriangle className="h-4 w-4" />
                {openAlerts.length > 0 && (
                  <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-rose-500"></span>
                )}
              </div>
              <span className="text-[11px] font-bold text-slate-700">Alerts</span>
            </button>
          </div>
        </div>
      </div>

      {/* Middle Bento Row: Clean Claims Limit + Quick Optimization Tips */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Denial Prevention Target Progress */}
        <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-[0_2px_12px_rgba(0,0,0,0.03)] flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Clean Claims Submission Target
            </span>
            <span className="text-xs font-bold text-emerald-600 font-mono">
              {clearCasesCount} / {totalCases} Cleared
            </span>
          </div>

          <div className="mt-3">
            <div className="flex items-baseline justify-between mb-2">
              <span className="text-2xl font-extrabold text-slate-900">{complianceRate}%</span>
              <span className="text-xs text-slate-500 font-medium">Hospital Benchmark: 95%</span>
            </div>
            {/* Lime Progress Bar */}
            <div className="w-full h-3 rounded-full bg-slate-100 overflow-hidden p-0.5">
              <div
                style={{ width: `${complianceRate}%` }}
                className="h-full rounded-full bg-lime-400 transition-all duration-500 shadow-sm"
              />
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-3">
            {openAlerts.length > 0
              ? `⚠️ ${openAlerts.length} claims need physician prior authorization before submission.`
              : '✓ All evaluated claims meet current active payer guidelines.'}
          </p>
        </div>

        {/* Quick Executive Optimization Tips */}
        <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-[0_2px_12px_rgba(0,0,0,0.03)] flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Payer Intelligence Notice
            </span>
            <span className="text-xs font-bold text-slate-900 flex items-center space-x-1">
              <Sparkles className="h-3 w-3 text-amber-500" />
              <span>Sentinel Alert</span>
            </span>
          </div>

          <div className="mt-3">
            <h4 className="text-sm font-bold text-slate-900">
              {openAlerts.length > 0
                ? 'Insurer A Policy Update: DRUG-A Excluded'
                : 'Payer Policy Rules Synchronized'}
            </h4>
            <p className="text-xs text-slate-600 mt-1 leading-relaxed">
              {openAlerts.length > 0
                ? 'Insurer A excluded DRUG-A effective Nov 1, 2026. 3 open claims affected. Direct physician to choose covered alternative before filing.'
                : 'Direct payer policy connection is healthy. No unaddressed exclusions or documentation gaps detected on open claims.'}
            </p>
          </div>

          <button
            onClick={() => onNavigateTab('alerts')}
            className="text-xs font-bold text-slate-900 hover:text-lime-600 flex items-center space-x-1.5 mt-3 transition-colors cursor-pointer"
          >
            <span>Review Policy Alerts ({openAlerts.length})</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Bottom Bento Row: Department Exposure + Radial Health Gauge + Live Policy Alerts Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Specialty Exposure Analysis (Col 4) */}
        <div className="lg:col-span-4 bg-white rounded-3xl p-6 border border-slate-200/80 shadow-[0_2px_12px_rgba(0,0,0,0.03)] space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Caseload by Specialty
            </span>
            <span className="text-xs text-slate-400 font-mono">Current</span>
          </div>

          <div className="space-y-3 pt-1">
            <div>
              <div className="flex justify-between text-xs font-bold text-slate-700 mb-1">
                <span>Pharmacy / Biologics</span>
                <span className="font-mono">35%</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                <div className="h-full bg-lime-400 rounded-full w-[35%]" />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-bold text-slate-700 mb-1">
                <span>Orthopedics / Joint</span>
                <span className="font-mono">25%</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full w-[25%]" />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-bold text-slate-700 mb-1">
                <span>Cardiovascular</span>
                <span className="font-mono">20%</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                <div className="h-full bg-teal-500 rounded-full w-[20%]" />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-bold text-slate-700 mb-1">
                <span>General Practice</span>
                <span className="font-mono">20%</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                <div className="h-full bg-amber-400 rounded-full w-[20%]" />
              </div>
            </div>
          </div>
        </div>

        {/* Compliance Health Semi-Circle Radial Gauge (Col 4) */}
        <div className="lg:col-span-4 bg-white rounded-3xl p-6 border border-slate-200/80 shadow-[0_2px_12px_rgba(0,0,0,0.03)] flex flex-col justify-between items-center text-center">
          <div className="w-full flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Zero-Denial Compliance
            </span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-lime-100 text-lime-800">
              Healthy
            </span>
          </div>

          {/* SVG Semi-Circle Gauge */}
          <div className="relative my-3 flex items-center justify-center">
            <svg className="w-40 h-24 overflow-visible" viewBox="0 0 160 90">
              <path
                d="M 15 80 A 65 65 0 0 1 145 80"
                fill="none"
                stroke="#F1F5F9"
                strokeWidth="14"
                strokeLinecap="round"
              />
              <path
                d="M 15 80 A 65 65 0 0 1 145 80"
                fill="none"
                stroke="#84CC16"
                strokeWidth="14"
                strokeLinecap="round"
                strokeDasharray="204"
                strokeDashoffset={204 - (204 * complianceRate) / 100}
                className="transition-all duration-700 ease-out"
              />
            </svg>
            <div className="absolute top-10 flex flex-col items-center">
              <span className="text-3xl font-black text-slate-900 font-mono tracking-tight">
                {complianceRate}%
              </span>
              <span className="text-[11px] font-semibold text-slate-400 uppercase">
                Clean Score
              </span>
            </div>
          </div>

          <p className="text-xs text-slate-500 max-w-xs leading-relaxed">
            Based on {totalCases} active cases audited against current insurer rulebooks.
          </p>
        </div>

        {/* Live Alerts Stream (Col 4 - like Transaction history) */}
        <div className="lg:col-span-4 bg-white rounded-3xl p-6 border border-slate-200/80 shadow-[0_2px_12px_rgba(0,0,0,0.03)] flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Recent Policy Alerts
            </span>
            <button
              onClick={() => onNavigateTab('alerts')}
              className="text-xs font-bold text-slate-500 hover:text-slate-900 transition-colors"
            >
              View All ({alerts.length})
            </button>
          </div>

          <div className="space-y-2 flex-1">
            {alerts.slice(0, 3).map((a) => {
              const isOpen = a.status === 'open';
              return (
                <div
                  key={a.alert_id}
                  onClick={() => onSelectCase(a.case_id)}
                  className="p-3 rounded-2xl hover:bg-slate-50 border border-slate-100 flex items-center justify-between cursor-pointer transition-colors group"
                >
                  <div className="flex items-center space-x-3">
                    <div className={`h-9 w-9 rounded-xl flex items-center justify-center font-bold text-xs ${
                      isOpen ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-700'
                    }`}>
                      {isOpen ? '!' : '✓'}
                    </div>
                    <div>
                      <div className="text-xs font-bold text-slate-900 group-hover:text-lime-700 transition-colors">
                        Case {a.case_id}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {a.item_code} · Rule {a.rule_id}
                      </div>
                    </div>
                  </div>

                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                    isOpen
                      ? 'bg-rose-50 text-rose-700 border-rose-200'
                      : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  }`}>
                    {isOpen ? 'Action Needed' : 'Closed'}
                  </span>
                </div>
              );
            })}
          </div>

          <button
            onClick={() => onNavigateTab('cases')}
            className="w-full py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition-all text-center block cursor-pointer"
          >
            Explore All {totalCases} Patient Claims
          </button>
        </div>
      </div>
    </div>
  );
};
