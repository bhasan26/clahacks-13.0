import React from 'react';
import { ShieldCheck, AlertTriangle, BookOpen, Activity, ArrowUpRight, TrendingUp } from 'lucide-react';
import { HealthStatus, CaseSummary, Alert } from '../types';

interface MetricsStripProps {
  health: HealthStatus | null;
  cases: CaseSummary[];
  alerts: Alert[];
}

export const MetricsStrip: React.FC<MetricsStripProps> = ({ health, cases, alerts }) => {
  const openAlertsCount = alerts.filter((a) => a.status === 'open').length;
  const clearCasesCount = cases.filter((c) => c.overall_status === 'clear').length;
  const attentionCasesCount = cases.filter((c) => c.overall_status === 'needs_attention').length;
  const cannotAssessCount = cases.filter((c) => c.overall_status === 'cannot_assess').length;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Metric 1: Total Active Claims */}
      <div className="p-5 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-900/60 border border-slate-800 shadow-xl relative overflow-hidden group hover:border-slate-700 transition-all">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-400">Total Monitored Claims</span>
          <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
            <ShieldCheck className="h-4 w-4" />
          </div>
        </div>
        <div className="mt-3 flex items-baseline space-x-2">
          <span className="text-2xl font-bold text-white font-mono">{cases.length}</span>
          <span className="text-xs text-emerald-400 font-medium flex items-center">
            <TrendingUp className="h-3 w-3 mr-0.5" />
            <span>{clearCasesCount} Clear</span>
          </span>
        </div>
        <p className="text-[11px] text-slate-500 mt-1">
          {attentionCasesCount} require action • {cannotAssessCount} cannot assess
        </p>
      </div>

      {/* Metric 2: Open Policy Alerts */}
      <div className={`p-5 rounded-2xl border shadow-xl relative overflow-hidden transition-all ${
        openAlertsCount > 0
          ? 'bg-gradient-to-br from-slate-900 via-slate-900/90 to-amber-950/20 border-amber-500/30'
          : 'bg-gradient-to-br from-slate-900 to-slate-900/60 border-slate-800'
      }`}>
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-400">Active Policy Alerts</span>
          <div className={`p-2 rounded-xl ${
            openAlertsCount > 0 ? 'bg-amber-500/10 text-amber-400' : 'bg-slate-800 text-slate-500'
          }`}>
            <AlertTriangle className={`h-4 w-4 ${openAlertsCount > 0 ? 'animate-pulse' : ''}`} />
          </div>
        </div>
        <div className="mt-3 flex items-baseline space-x-2">
          <span className="text-2xl font-bold text-white font-mono">{openAlertsCount}</span>
          <span className="text-xs text-amber-400 font-medium">Immediate Action</span>
        </div>
        <p className="text-[11px] text-slate-500 mt-1">
          Adverse rule changes touching open claims
        </p>
      </div>

      {/* Metric 3: Active Payer Rules Stored */}
      <div className="p-5 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-900/60 border border-slate-800 shadow-xl relative overflow-hidden group hover:border-slate-700 transition-all">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-400">Payer Rules Versioned</span>
          <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400">
            <BookOpen className="h-4 w-4" />
          </div>
        </div>
        <div className="mt-3 flex items-baseline space-x-2">
          <span className="text-2xl font-bold text-white font-mono">{health?.total_rules ?? 2}</span>
          <span className="text-xs text-cyan-400 font-medium">PLAN-GOLD Scoped</span>
        </div>
        <p className="text-[11px] text-slate-500 mt-1">
          Drugs, procedures & authorization criteria
        </p>
      </div>

      {/* Metric 4: Payer Feed Status */}
      <div className="p-5 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-900/60 border border-slate-800 shadow-xl relative overflow-hidden group hover:border-slate-700 transition-all">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-400">Insurer Feed Integrity</span>
          <div className={`p-2 rounded-xl ${
            health?.is_stale ? 'bg-amber-500/10 text-amber-400' : 'bg-emerald-500/10 text-emerald-400'
          }`}>
            <Activity className="h-4 w-4" />
          </div>
        </div>
        <div className="mt-3 flex items-baseline space-x-2">
          <span className={`text-base font-bold font-mono ${
            health?.is_stale ? 'text-amber-400' : 'text-emerald-400'
          }`}>
            {health?.is_stale ? 'Warning: Stale' : '100% Synced'}
          </span>
          <span className="text-xs text-slate-400">
            {health ? `${Math.round(health.age_seconds)}s ago` : 'Active'}
          </span>
        </div>
        <p className="text-[11px] text-slate-500 mt-1">
          Direct read-only rules API connection
        </p>
      </div>
    </div>
  );
};
