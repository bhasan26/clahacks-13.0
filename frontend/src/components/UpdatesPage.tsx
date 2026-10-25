import type { PolicyUpdate } from '../types';
export function UpdatesPage({ updates }: { updates: PolicyUpdate[] }) {
  return <div className="space-y-6">
    <h1 className="text-xl font-black tracking-tight">Latest Insurance Updates</h1>
    <div className="space-y-3">
      {updates.length === 0 ? <p className="p-10 text-center text-xs text-[#12544F]/70 bg-white rounded-2xl border border-[#D8E5DC]">No verified updates found for uploaded requests.</p> : updates.map(update => <article key={`${update.source_url}-${update.treatment_name}-${update.effective_date}`} className="bg-white border border-[#D8E5DC] rounded-2xl p-5 shadow-sm space-y-3">
        <h2 className="font-bold text-sm">{update.title}</h2>
        <p className="text-xs text-[#12544F]/80">{update.insurer_name} · {update.treatment_name}</p>
        <p className="text-xs">Effective: <strong>{update.effective_date}</strong>{update.effective_date > new Date().toLocaleDateString('en-CA') ? ' · Upcoming' : ''}</p>
        <p className="text-xs text-[#12544F]/80">{update.description}</p>
        <a href={update.source_url} target="_blank" rel="noreferrer" className="inline-block text-xs font-bold underline text-[#12544F]">Source policy · Retrieved {update.checked_at}</a>
      </article>)}
    </div>
  </div>;
}
