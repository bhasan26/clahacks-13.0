import React from 'react';
import { ShieldCheck, RefreshCw, AlertTriangle, CheckCircle2, Clock } from 'lucide-react';
import { HealthStatus } from '../types';

interface HeaderProps {
  health: HealthStatus | null;
  activeTab: 'alerts' | 'cases' | 'rules' | 'audit';
  setActiveTab: (tab: 'alerts' | 'cases' | 'rules' | 'audit') => void;
  onSync: () => void;
  isSyncing: boolean;
  openIntake: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  activeTab,
  setActiveTab,
  onSync,
  isSyncing,
  openIntake,
}) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-blue-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
              <ShieldCheck className="h-6 w-6 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xl font-bold tracking-tight text-white">CoverageGuard</span>
                <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  Hospital Claims Agent
                </span>
              </div>
              <p className="text-xs text-slate-400">Autonomous Coverage Check & Policy Monitoring</p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="hidden md:flex space-x-1 bg-slate-950/60 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setActiveTab('alerts')}
              className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-all flex items-center space-x-2 ${
                activeTab === 'alerts'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <span>Alerts Inbox</span>
              {health && health.open_alerts > 0 && (
                <span className="h-4 px-1.5 rounded-full text-[10px] font-bold bg-amber-500 text-slate-950">
                  {health.open_alerts}
                </span>
              )}
            </button>
            <button
              onClick={() => setActiveTab('cases')}
              className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                activeTab === 'cases'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              Cases Explorer
            </button>
            <button
              onClick={() => setActiveTab('rules')}
              className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                activeTab === 'rules'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              Rules Catalog
            </button>
            <button
              onClick={() => setActiveTab('audit')}
              className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                activeTab === 'audit'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              Audit Trail
            </button>
          </nav>

          {/* Actions & Feed Status */}
          <div className="flex items-center space-x-3">
            {/* Feed Health Indicator */}
            {health && (
              <div
                className={`hidden lg:flex items-center space-x-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border ${
                  health.is_stale
                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                    : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                }`}
                title={`Last synced: ${new Date(health.last_sync_time).toLocaleTimeString()}`}
              >
                {health.is_stale ? (
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-400 animate-pulse" />
                ) : (
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                )}
                <span>{health.is_stale ? 'Feed Stale' : 'Feed Active'}</span>
              </div>
            )}

            {/* Run Sync Now Button */}
            <button
              onClick={onSync}
              disabled={isSyncing}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 transition-all active:scale-95 disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isSyncing ? 'animate-spin text-blue-400' : ''}`} />
              <span>{isSyncing ? 'Syncing...' : 'Sync Rules'}</span>
            </button>

            {/* AI Intake Upload */}
            <button
              onClick={openIntake}
              className="inline-flex items-center space-x-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 text-white shadow-sm shadow-blue-500/30 transition-all active:scale-95"
            >
              <span>+ New File Intake</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
