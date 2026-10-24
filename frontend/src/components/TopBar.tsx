import React from 'react';
import { Search, Sparkles, Bell, Wifi, RefreshCw } from 'lucide-react';
import { HealthStatus } from '../types';

interface TopBarProps {
  health: HealthStatus | null;
  openIntake: () => void;
  onSync: () => void;
  isSyncing: boolean;
}

export const TopBar: React.FC<TopBarProps> = ({
  health,
  openIntake,
  onSync,
  isSyncing,
}) => {
  return (
    <header className="h-20 bg-transparent flex items-center justify-between px-6 sm:px-8 border-b border-slate-200/60 sticky top-0 z-20 backdrop-blur-sm">
      {/* Search Bar (Matching Shakuro ACRU top search) */}
      <div className="flex-1 max-w-md">
        <div className="relative">
          <Search className="h-4 w-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search patient, claim ID, medication, or policy code..."
            className="w-full pl-10 pr-4 py-2.5 rounded-2xl bg-white border border-slate-200/80 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-slate-400 focus:ring-2 focus:ring-slate-100 transition-all shadow-sm"
          />
        </div>
      </div>

      {/* Right Controls: Live status, Notifications, Profile, Primary CTA */}
      <div className="flex items-center space-x-4">
        {/* Live Status Pill */}
        <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-full bg-white border border-slate-200/80 shadow-sm text-xs font-semibold text-slate-700">
          <span className={`h-2 w-2 rounded-full ${health?.is_stale ? 'bg-amber-500' : 'bg-lime-500'}`} />
          <span>{health?.is_stale ? 'Rules Outdated' : 'Payer Feed Live'}</span>
        </div>

        {/* Sync Button */}
        <button
          onClick={onSync}
          disabled={isSyncing}
          className="p-2.5 rounded-xl bg-white border border-slate-200/80 hover:bg-slate-50 text-slate-700 transition-all shadow-sm cursor-pointer"
          title="Sync Insurer Rules"
        >
          <RefreshCw className={`h-4 w-4 ${isSyncing ? 'animate-spin text-lime-600' : ''}`} />
        </button>

        {/* Primary CTA: + Intake Clinical File */}
        <button
          onClick={openIntake}
          className="px-4 py-2.5 rounded-2xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold shadow-md shadow-slate-900/10 transition-all flex items-center space-x-2 cursor-pointer active:scale-95"
        >
          <Sparkles className="h-3.5 w-3.5 text-lime-400" />
          <span>+ Intake File</span>
        </button>

        {/* Officer Profile Pill (ACRU style avatar & name) */}
        <div className="flex items-center space-x-3 pl-2 border-l border-slate-200">
          <div className="h-9 w-9 rounded-full bg-slate-900 text-lime-400 font-extrabold text-xs flex items-center justify-center shadow-sm">
            BH
          </div>
          <div className="hidden md:block text-left">
            <span className="text-xs font-bold text-slate-900 block leading-tight">
              Dr. Bilal Hasan
            </span>
            <span className="text-[10px] text-slate-400 font-medium block">
              Claims Officer
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
