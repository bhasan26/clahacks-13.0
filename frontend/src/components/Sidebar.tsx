import React from 'react';
import clsx from 'clsx';
import { Bell, ClipboardCheck, FileCheck2, ScrollText, ShieldCheck, type LucideIcon } from 'lucide-react';

export type Tab = 'cases' | 'monitoring' | 'updates' | 'intelligence';

interface SidebarProps {
  activeTab: Tab;
  setActiveTab: (tab: Tab) => void;
}

const navItems: Array<{ id: Tab; label: string; hint: string; icon: LucideIcon }> = [
  { id: 'cases', label: 'Claims', hint: 'Check a claim before sending it', icon: FileCheck2 },
  { id: 'monitoring', label: 'Insurer rules', hint: 'New rules and their sources', icon: ScrollText },
  { id: 'updates', label: 'Alerts', hint: 'Claims hit by a rule change', icon: Bell },
  { id: 'intelligence', label: 'Review a rule', hint: 'Read a policy and approve it', icon: ClipboardCheck },
];

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab }) => (
  <aside className="sticky top-0 z-30 flex min-h-screen w-64 shrink-0 flex-col justify-between border-r border-line bg-surface px-3 py-5">
    <div className="space-y-6">
      <div className="flex items-center gap-2.5 px-3">
        <div className="flex size-9 items-center justify-center rounded-xl bg-brand">
          <ShieldCheck className="size-4.5 text-white" aria-hidden="true" />
        </div>
        <div className="leading-tight">
          <span className="block text-[15px] font-bold tracking-tight text-ink">CoverageGuard</span>
          <span className="block text-xs text-subtle">Claim checks</span>
        </div>
      </div>

      <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-subtle">Menu</p>
      <nav className="-mt-3 space-y-1" aria-label="Main">
        {navItems.map(({ id, label, hint, icon: Icon }) => {
          const isActive = activeTab === id;
          return (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              aria-current={isActive ? 'page' : undefined}
              className={clsx(
                'group flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left transition-colors duration-150 cursor-pointer',
                isActive ? 'bg-cta-soft' : 'hover:bg-sunken',
              )}
            >
              <span
                className={clsx(
                  'flex size-8 shrink-0 items-center justify-center rounded-lg',
                  isActive ? 'bg-surface shadow-xs' : 'bg-sunken group-hover:bg-surface',
                )}
              >
                <Icon
                  className={clsx('size-4', isActive ? 'text-cta' : 'text-subtle group-hover:text-muted')}
                  aria-hidden="true"
                />
              </span>
              <span>
                <span className={clsx('block text-sm font-semibold', isActive ? 'text-cta-ink' : 'text-ink-2')}>{label}</span>
                <span className="block text-[11px] text-subtle">{hint}</span>
              </span>
            </button>
          );
        })}
      </nav>
    </div>

    <div className="mx-1 rounded-2xl bg-brand-soft px-4 py-4 text-xs text-brand-ink">
      <span className="mb-1 block text-sm font-semibold text-brand-ink">Prototype</span> Test patient data only. CoverageGuard gives advice; it
      never sends or approves claims.
    </div>
  </aside>
);
