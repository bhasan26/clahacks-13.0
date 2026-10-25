import type { CheckReport, ResultStatus } from '../types';

export function StatusBadge({ status }: { status: ResultStatus }) {
  const color = status === 'Ready' || status === 'Accepted' ? '#2A835F' : status === 'Coverage alert' || status === 'Needs policy review' ? '#D97706' : '#DC2626';
  return <span style={{ color, backgroundColor: `${color}15`, borderColor: `${color}40` }} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-bold whitespace-nowrap"><span style={{ backgroundColor: color }} className="h-1.5 w-1.5 rounded-full" />{status}</span>;
}

export function ResultPanel({ report }: { report: CheckReport | null }) {
  return <section aria-label="Check result" aria-live="polite" className="bg-white border border-[#D8E5DC] rounded-2xl p-6 shadow-sm space-y-4">
    <div className="flex items-center justify-between gap-3"><h2 className="text-sm font-bold">Result</h2>{report && <StatusBadge status={report.status} />}</div>
    {!report ? <p className="text-xs text-[#12544F]/70">Upload the insurance card and prescription, then click Check.</p> : <>
      <div className="space-y-2"><p className="text-sm font-semibold">{report.message}</p><p className="text-xs text-[#12544F]/80">{report.coverage_note}</p></div>
      {!!report.policy_findings?.length && <div className="space-y-3 text-xs border-t border-[#EAEFEA] pt-4">
        {report.policy_findings.map((finding, index) => <div key={`${finding.source_url}-${index}`} className="space-y-1">
          <a href={finding.source_url} target="_blank" rel="noreferrer" className="font-bold text-[#12544F] underline">Policy: {finding.policy_id || finding.policy_title}</a>
          <p className="text-[#12544F]/80">{finding.reason}</p>
        </div>)}
      </div>}
      <dl className="grid sm:grid-cols-2 gap-3 text-xs border-t border-[#EAEFEA] pt-4">
        <div><dt className="text-[#12544F]/60 mb-1">Insurer</dt><dd className="font-bold break-words">{report.insurer_name || 'Not found in the card'}</dd></div>
        <div><dt className="text-[#12544F]/60 mb-1">Medication / procedure</dt><dd className="font-bold break-words">{report.treatment_name || 'Not found in the prescription'}</dd></div>
      </dl>
      <div className="space-y-2 text-xs border-t border-[#EAEFEA] pt-4">
        <h3 className="font-bold">Information used</h3>
        {report.documents.filter(doc => doc.filename).map(doc => <div key={doc.type} className="text-[#12544F]/80 break-words"><span className="font-semibold">{doc.type}: {doc.filename}</span><p className="mt-1">{Object.entries(doc.information).map(([key, value]) => `${key.replace(/_/g, ' ')}: ${value}`).join(' · ') || 'No readable information found.'}</p></div>)}
        {report.sources.map((source, index) => <div key={`${source.url}-${index}`} className="bg-[#F0F5F2] rounded-xl p-3 space-y-1">
          <a href={source.url} target="_blank" rel="noreferrer" className="font-bold text-[#12544F] underline break-words">Source: {source.title}</a>
          <blockquote className="text-[#12544F]/80 break-words">“{source.excerpt}”</blockquote>
          {source.effective_date && <p>Effective: {source.effective_date}</p>}
          <p className="text-[#12544F]/60">Retrieved: {source.checked_at}</p>
        </div>)}
      </div>
      <p className="text-xs text-[#12544F]/80 border-t border-[#EAEFEA] pt-4">{report.physician_note}</p>
    </>}
  </section>;
}
