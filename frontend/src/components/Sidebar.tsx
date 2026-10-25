import { ClipboardCheck, Files, Database, Bell } from 'lucide-react';
import type { Page } from '../types';

const pages = [
  { id: 'check', label: 'New Insurance Check', icon: ClipboardCheck },
  { id: 'requests', label: 'All Requests', icon: Files },
  { id: 'connection', label: 'Insurance Database Connection', icon: Database },
  { id: 'updates', label: 'Latest Insurance Updates', icon: Bell },
] as const;

export function Sidebar({ page, navigate }: { page: Page; navigate: (page: Page) => void }) {
  return <aside className="w-full md:w-64 bg-white border-b md:border-b-0 md:border-r border-[#D8E5DC] flex flex-col shrink-0 md:h-screen md:sticky md:top-0 z-30 p-5 shadow-[1px_0_4px_rgba(0,0,0,0.02)]">
    <div className="px-2 pt-2 mb-8 flex items-center gap-2.5">
      <div className="w-8 h-8 rounded-xl bg-[#092328] flex items-center justify-center text-sm font-black text-[#8BBB92] shadow-sm">CG</div>
      <div><span className="text-base font-black tracking-tight block leading-tight">Coverage Guard</span><span className="text-[10px] font-semibold text-[#12544F]/70 tracking-wide uppercase">Claims Sentinel</span></div>
    </div>
    <nav aria-label="Main navigation" className="grid grid-cols-2 md:grid-cols-1 gap-1.5">
      {pages.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => navigate(id)} aria-current={page === id ? 'page' : undefined} className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl font-bold text-xs text-left transition-colors cursor-pointer ${page === id ? 'bg-[#092328] text-white shadow-sm' : 'text-[#12544F]/80 hover:bg-[#F0F5F2]'}`}>
        <Icon aria-hidden="true" className={`w-4 h-4 shrink-0 ${page === id ? 'text-[#8BBB92]' : 'text-[#12544F]/60'}`} /><span>{label}</span>
      </button>)}
    </nav>
    <div className="hidden md:block mt-auto pt-4 border-t border-[#EAEFEA] text-[11px] text-[#12544F]/70 px-1">Insurance policy access · Read-only</div>
  </aside>;
}
