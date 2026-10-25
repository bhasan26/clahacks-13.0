import React, { useState, useRef, useEffect } from 'react';
import { InsurerConnectionInfo } from '../types';

interface SidebarProps {
  activeTab: 'dashboard' | 'cases' | 'updates' | 'intelligence';
  setActiveTab: (tab: 'dashboard' | 'cases' | 'updates' | 'intelligence') => void;
  connection: InsurerConnectionInfo | null;
  onRunCheckNow?: () => void;
  onToggleFail?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  connection,
  onRunCheckNow,
  onToggleFail,
}) => {
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close popover when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setIsPopoverOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const isFailed = connection?.is_check_failed ?? false;
  const insurerName = connection?.insurer_name || 'Demo Insurance Co.';
  const lastCheck = connection?.last_check_time || '06:00 today';

  const navItems = [
    {
      id: 'dashboard' as const,
      label: 'Dashboard',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
        </svg>
      ),
    },
    {
      id: 'cases' as const,
      label: 'Cases',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
    },
    {
      id: 'updates' as const,
      label: 'Updates',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
      ),
    },
    {
      id: 'intelligence' as const,
      label: 'Policy Intelligence',
      badge: 'Multimodal',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
      ),
    },
  ];

  return (
    <aside className="w-64 bg-white border-r border-[#D8E5DC] flex flex-col justify-between shrink-0 min-h-screen sticky top-0 z-30 p-5 shadow-[1px_0_4px_rgba(0,0,0,0.02)]">
      {/* Top Brand & Navigation */}
      <div className="space-y-8">
        {/* Brand Header */}
        <div className="px-2 pt-2">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-[#092328] flex items-center justify-center text-white shadow-sm">
              <span className="text-sm font-black text-[#8BBB92]">CG</span>
            </div>
            <div>
              <span className="text-base font-black tracking-tight text-[#092328] block leading-tight">
                Coverage Guard
              </span>
              <span className="text-[10px] font-semibold text-[#12544F]/70 tracking-wide uppercase">
                Claims Sentinel
              </span>
            </div>
          </div>
        </div>

        {/* Navigation List: Dashboard · Cases · Updates */}
        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl font-bold text-xs transition-all cursor-pointer ${
                  isActive
                    ? 'bg-[#092328] text-white shadow-sm'
                    : 'text-[#12544F]/80 hover:text-[#092328] hover:bg-[#F0F5F2]'
                }`}
              >
                <span className={isActive ? 'text-[#8BBB92]' : 'text-[#12544F]/60'}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Insurer Connection Chip with Popover */}
      <div className="pt-4 border-t border-[#EAEFEA] relative" ref={popoverRef}>
        <div className="text-[10px] font-bold text-[#12544F]/60 uppercase tracking-wider mb-2 px-1">
          Insurer System
        </div>

        {/* Connection Chip */}
        <button
          onClick={() => setIsPopoverOpen(!isPopoverOpen)}
          className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-all border shadow-xs cursor-pointer ${
            isFailed
              ? 'bg-amber-50 text-[#D97706] border-amber-300 hover:bg-amber-100'
              : 'bg-[#F0F5F2] text-[#092328] border-[#D8E5DC] hover:border-[#2A835F]'
          }`}
          title="Click to view connection details"
        >
          <div className="flex items-center space-x-2 truncate">
            <span
              className={`h-2 w-2 rounded-full shrink-0 ${
                isFailed ? 'bg-[#D97706]' : 'bg-[#2A835F]'
              }`}
            />
            <span className="truncate">
              {insurerName}
            </span>
          </div>
          <span className="text-[10px] text-[#12544F]/70 shrink-0 font-bold ml-1">
            {isFailed ? 'Pending' : 'Active'}
          </span>
        </button>

        <div className="mt-1 px-1 text-[11px] text-[#12544F]/60 truncate">
          ● {isFailed ? 'Check pending' : 'Access active'}
        </div>

        {/* Small Popover on Chip Click: "Read-only" appears only here */}
        {isPopoverOpen && (
          <div className="absolute left-0 bottom-full mb-2 w-72 bg-white rounded-2xl shadow-xl border border-[#D8E5DC] p-4 text-xs space-y-3 z-50 animate-in fade-in zoom-in-95 duration-150">
            <div className="border-b border-[#EAEFEA] pb-2">
              <span className="font-extrabold text-[#092328] text-sm block">
                {insurerName}
              </span>
              <span className="text-[11px] text-[#12544F]/70">
                Insurer Rules Connection
              </span>
            </div>

            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between py-0.5">
                <span className="text-[#12544F]/70">Connection status:</span>
                <span className="font-bold text-[#092328]">
                  {isFailed ? 'Check pending' : 'Connected'}
                </span>
              </div>

              <div className="flex justify-between py-0.5">
                <span className="text-[#12544F]/70">Authorization:</span>
                <span
                  className={`font-bold ${
                    isFailed ? 'text-[#D97706]' : 'text-[#2A835F]'
                  }`}
                >
                  {isFailed ? 'Check pending' : 'Access active'}
                </span>
              </div>

              <div className="flex justify-between py-0.5">
                <span className="text-[#12544F]/70">Access mode:</span>
                {/* "Read-only" appears ONLY here */}
                <span className="font-bold text-[#092328] bg-[#F0F5F2] px-2 py-0.5 rounded text-[11px]">
                  Read-only
                </span>
              </div>

              <div className="flex justify-between py-0.5">
                <span className="text-[#12544F]/70">Last checked:</span>
                <span className="font-bold text-[#092328]">{lastCheck}</span>
              </div>
            </div>

            {/* Popover Demo Controls */}
            {(onRunCheckNow || onToggleFail) && (
              <div className="pt-2 border-t border-[#EAEFEA] flex flex-col space-y-1.5">
                {onRunCheckNow && (
                  <button
                    onClick={() => {
                      onRunCheckNow();
                      setIsPopoverOpen(false);
                    }}
                    className="w-full text-center py-1.5 rounded-lg bg-[#092328] hover:bg-[#12544F] text-white text-xs font-bold transition-all cursor-pointer"
                  >
                    Run check now
                  </button>
                )}
                {onToggleFail && (
                  <button
                    onClick={() => {
                      onToggleFail();
                      setIsPopoverOpen(false);
                    }}
                    className="w-full text-center py-1 rounded text-[11px] text-[#12544F]/80 hover:text-[#092328] hover:bg-[#F0F5F2] transition-colors cursor-pointer"
                  >
                    {isFailed ? 'Clear simulated failure' : 'Simulate failed check'}
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
