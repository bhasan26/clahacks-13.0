import { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { Sidebar } from './components/Sidebar';
import { NewCheckPage } from './components/NewCheckPage';
import { CasesPage } from './components/CasesPage';
import { UpdatesPage } from './components/UpdatesPage';
import { ResultPanel } from './components/ResultPanel';
import { fetchConnection, fetchReport, fetchRequests, fetchUpdates } from './api';
import type { Page, CheckReport, Connection, PolicyUpdate, RequestSummary } from './types';

const pages: Page[] = ['check', 'requests', 'connection', 'updates'];
function currentPage(): Page {
  const hash = window.location.hash.slice(1) as Page;
  return pages.includes(hash) ? hash : 'check';
}
function ReportDialog({ report, close }: { report: CheckReport; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    dialog.current?.showModal();
    return () => dialog.current?.close();
  }, []);
  return <dialog ref={dialog} onCancel={close} onClick={event => { if (event.target === event.currentTarget) close(); }} className="m-auto bg-white border border-[#D8E5DC] rounded-3xl w-[calc(100%-2rem)] max-w-2xl max-h-[90vh] p-6 shadow-2xl backdrop:bg-[#092328]/40 backdrop:backdrop-blur-xs text-[#092328]">
    <div className="flex justify-between gap-3 items-center mb-5"><h2 className="text-sm font-black">Report · {report.request_id}</h2><button onClick={close} aria-label="Close report" className="p-2 hover:bg-[#F0F5F2] rounded-lg cursor-pointer"><X className="w-4 h-4" /></button></div>
    <ResultPanel report={report} />
  </dialog>;
}

export function App() {
  const [page, setPage] = useState<Page>(currentPage);
  const [requests, setRequests] = useState<RequestSummary[]>([]);
  const [updates, setUpdates] = useState<PolicyUpdate[]>([]);
  const [connection, setConnection] = useState<Connection | null>(null);
  const [selected, setSelected] = useState<CheckReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const onHashChange = () => setPage(currentPage());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);
  useEffect(() => {
    let active = true;
    setError(''); setLoading(page !== 'check');
    async function load() {
      try {
        if (page === 'requests') { const data = await fetchRequests(); if (active) setRequests(data); }
        if (page === 'updates') { const data = await fetchUpdates(); if (active) setUpdates(data); }
        if (page === 'connection') { const data = await fetchConnection(); if (active) setConnection(data); }
      } catch (err) { if (active) setError(err instanceof Error ? err.message : 'Could not load the page.'); }
      finally { if (active) setLoading(false); }
    }
    load();
    return () => { active = false; };
  }, [page]);
  async function openReport(id: string) {
    setError('');
    try { setSelected(await fetchReport(id)); }
    catch { setError('Could not open the report.'); }
  }
  function navigate(next: Page) { window.location.hash = next; setPage(next); setSelected(null); }
  return <div className="min-h-screen bg-white text-[#092328] flex flex-col md:flex-row antialiased selection:bg-[#8BBB92]/20">
    <Sidebar page={page} navigate={navigate} />
    <main className="flex-1 min-w-0"><div className="max-w-6xl mx-auto py-8 px-6 pb-16">
      {error && <p role="alert" className="text-xs text-[#DC2626] mb-5">{error}</p>}
      <div hidden={page !== 'check'}><NewCheckPage /></div>
      {page !== 'check' && (loading ? <p role="status" className="text-xs text-[#12544F]/70">Loading…</p> : !error && <>
        {page === 'requests' && <CasesPage requests={requests} openReport={openReport} />}
        {page === 'updates' && <UpdatesPage updates={updates} />}
        {page === 'connection' && connection && <div className="space-y-6"><h1 className="text-xl font-black tracking-tight">Insurance Database Connection</h1><section className="bg-white border border-[#D8E5DC] rounded-2xl p-6 shadow-sm space-y-5 max-w-2xl"><dl className="space-y-5 text-xs">
          {[['Connection status', connection.status], ['Insurance company / database', connection.database_name], ['Access mode', connection.access_mode], ['Permission', connection.permission]].map(([label, value]) => <div key={label} className="flex flex-wrap justify-between gap-2 border-b border-[#EAEFEA] pb-4 last:border-0 last:pb-0"><dt className="text-[#12544F]/70">{label}</dt><dd className={`font-bold ${label === 'Connection status' ? 'text-[#2A835F]' : ''}`}>{value}</dd></div>)}
        </dl><p className="text-xs text-[#12544F]/70 border-t border-[#EAEFEA] pt-4">{connection.description}</p></section></div>}
      </>)}
    </div></main>
    {selected && <ReportDialog report={selected} close={() => setSelected(null)} />}
  </div>;
}
export default App;
