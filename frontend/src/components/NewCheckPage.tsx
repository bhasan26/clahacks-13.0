import { useState } from 'react';
import { Upload } from 'lucide-react';
import { checkDocuments } from '../api';
import type { CheckReport } from '../types';
import { ResultPanel } from './ResultPanel';

const accept = '.pdf,.png,.jpg,.jpeg,.webp,.txt';
export function NewCheckPage() {
  const [card, setCard] = useState<File | null>(null);
  const [prescription, setPrescription] = useState<File | null>(null);
  const [report, setReport] = useState<CheckReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  function selectFile(file: File | null, setter: (file: File | null) => void) {
    setReport(null);
    if (file && file.size > 8 * 1024 * 1024) {
      setter(null);
      setError('Each file must be 8 MB or smaller.');
      return;
    }
    setter(file);
    setError('');
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(''); setReport(null);
    try { setReport(await checkDocuments(card, prescription)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not check the documents.'); }
    finally { setBusy(false); }
  }
  return <div className="space-y-6">
    <h1 className="text-xl font-black tracking-tight">New Insurance Check</h1>
    <form onSubmit={submit} className="space-y-5">
      <div className="grid sm:grid-cols-2 gap-5">
        {[{ id: 'insurance-card', label: 'Insurance Card', file: card, setter: setCard }, { id: 'prescription', label: 'Prescription', file: prescription, setter: setPrescription }].map(({ id, label, file, setter }) => <div key={id} className="bg-white border border-[#D8E5DC] rounded-2xl p-5 shadow-sm space-y-4">
          <label htmlFor={id} className="text-sm font-bold flex items-center gap-2"><Upload aria-hidden="true" className="w-4 h-4 text-[#2A835F]" />{label} upload</label>
          <input id={id} name={id} type="file" accept={accept} disabled={busy} onClick={event => { event.currentTarget.value = ''; }} onChange={event => selectFile(event.target.files?.[0] || null, setter)} className="w-full text-xs text-[#12544F]/80 file:mr-3 file:rounded-lg file:border-0 file:bg-[#F0F5F2] file:px-3 file:py-2 file:font-semibold file:text-[#12544F] file:cursor-pointer" />
          <p className="text-[11px] text-[#12544F]/60 break-words">{file ? file.name : 'PDF, PNG, JPG, WebP, or text · Up to 8 MB'}</p>
        </div>)}
      </div>
      <button type="submit" disabled={busy} className="px-6 py-2.5 rounded-xl bg-[#092328] hover:bg-[#12544F] text-white text-xs font-bold shadow-sm cursor-pointer disabled:opacity-60 disabled:cursor-wait">{busy ? 'Checking documents…' : 'Check'}</button>
    </form>
    {error && <p role="alert" className="text-xs text-[#DC2626]">{error} If insurance does not cover the prescribed treatment, please consult the responsible physician.</p>}
    <ResultPanel report={report} />
  </div>;
}
