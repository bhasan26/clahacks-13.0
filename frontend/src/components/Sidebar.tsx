import React from 'react';
import {
  LayoutDashboard,
  ShieldAlert,
  FolderArchive,
  BookOpen,
  Clock,
  ShieldCheck,
  RefreshCw,
  LogOut,
  ChevronRight,
  Wifi,
} from 'lucide-react';
import { HealthStatus } from '../types';

interface SidebarProps {
  activeTab: 'dashboard' | 'alerts' | 'cases' | 'rules' | 'audit';
  setActiveTab: (tab: 'dashboard' | 'alerts' | 'cases' | 'rules' | 'audit') => void;
  health: HealthStatus | null;
  onSync: () => void;
  isSyncing: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  health,
  onSync,
  isSyncing,
}) => {
  const openAlertsCount = health?.open_alerts ?? 0;

  type TabId = 'dashboard' | 'alerts' | 'cases' | 'rules' | 'audit';
  interface NavItem {
    id: TabId;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    badge?: number;
  }

  const navItems: NavItem[] = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'alerts', label: 'Policy Alerts', icon: ShieldAlert, badge: openAlertsCount > 0 ? openAlertsCount : undefined },
    { id: 'cases', label: 'Claims Explorer', icon: FolderArchive },
    { id: 'rules', label: 'Payer Rules', icon: BookOpen },
    { id: 'audit', label: 'Audit Trail', icon: Clock },
  ];

  return (
    <aside className="w-64 bg-white border-r border-slate-200/80 flex flex-col justify-between shrink-0 min-h-screen sticky top-0 z-30 p-5">
      {/* Brand Header */}
      <div className="space-y-8">
        <div className="flex items-center space-x-3 px-2">
          <div className="h-10 w-10 rounded-2xl bg-slate-900 text-white flex items-center justify-center shadow-md shadow-slate-900/10">
            <ShieldCheck className="h-6 w-6 text-lime-400" />
          </div>
          <div>
            <span className="text-lg font-black tracking-tight text-slate-900 block leading-tight">
              CoverageGuard
            </span>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Hospital Sentinel
            </span>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;

            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-3 rounded-2xl font-bold text-xs transition-all cursor-pointer ${
                  isActive
                    ? 'bg-slate-900 text-white shadow-md shadow-slate-900/10'
                    : 'text-slate-500 hover:text-slate-900 hover:bg-slate-100/70'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <Icon className={`h-4 w-4 ${isActive ? 'text-lime-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>

                {item.badge !== undefined && (
                  <span
                    className={`h-5 min-w-[20px] px-1.5 rounded-full text-[10px] font-extrabold flex items-center justify-center ${
                      isActive
                        ? 'bg-rose-500 text-white'
                        : 'bg-rose-100 text-rose-700'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Sidebar Feed Health Widget (ACRU style bottom card) */}
      <div className="space-y-4 pt-6 border-t border-slate-100">
        <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-900 flex items-center space-x-1.5">
              <span className={`h-2 w-2 rounded-full ${health?.is_stale ? 'bg-amber-500 animate-pulse' : 'bg-lime-500'}`} />
              <span>Direct Payer Feed</span>
            </span>
            <span className="text-[10px] font-bold text-slate-400 uppercase">
              {health?.is_stale ? 'Stale' : 'Live'}
            </span>
          </div>

          <p className="text-[11px] text-slate-500 leading-snug">
            {health?.is_stale
              ? 'Feed failure simulated. Rules may be out of date.'
              : 'Direct API connected to commercial payer rules.'}
          </p>

          <button
            onClick={onSync}
            disabled={isSyncing}
            className="w-full py-2 px-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-[11px] font-bold transition-all flex items-center justify-center space-x-1.5 cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${isSyncing ? 'animate-spin' : ''}`} />
            <span>{isSyncing ? 'Syncing...' : 'Sync Payer Feed'}</span>
          </button>
        </div>

        <div className="text-[11px] text-slate-400 px-2 flex items-center justify-between">
          <span>v1.4 Production</span>
          <span className="text-lime-600 font-bold font-mono">100% Sync</span>
        </div>
      </div>
    </aside>
  );
};
