import type { RequestSummary } from '../types';
import { StatusBadge } from './ResultPanel';

export function CasesPage({ requests, openReport }: { requests: RequestSummary[]; openReport: (id: string) => void }) {
  return <div className="space-y-6">
    <h1 className="text-xl font-black tracking-tight">All Requests</h1>
    <div className="bg-white border border-[#D8E5DC] rounded-2xl overflow-hidden shadow-sm overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead className="bg-[#F0F5F2] border-b border-[#D8E5DC] text-[#12544F] font-bold"><tr>{['Request ID', 'Insurer', 'Medication / procedure', 'Submission date', 'Result', 'Report'].map(title => <th key={title} scope="col" className="py-3 px-5">{title}</th>)}</tr></thead>
        <tbody className="divide-y divide-[#EAEFEA]">
          {requests.length === 0 ? <tr><td colSpan={6} className="py-12 text-center text-[#12544F]/60">No requests uploaded yet.</td></tr> : requests.map(request => <tr key={request.request_id} className="hover:bg-[#F0F5F2]/50">
            <td className="py-3.5 px-5 font-mono font-bold whitespace-nowrap">{request.request_id}</td>
            <td className="py-3.5 px-5 font-semibold">{request.insurer_name || 'Not found'}</td>
            <td className="py-3.5 px-5">{request.treatment_name || 'Not found'}</td>
            <td className="py-3.5 px-5 whitespace-nowrap">{new Date(request.submitted_at).toLocaleDateString()}</td>
            <td className="py-3.5 px-5"><StatusBadge status={request.status} /></td>
            <td className="py-3.5 px-5"><button onClick={() => openReport(request.request_id)} className="text-[#12544F] font-bold hover:underline cursor-pointer whitespace-nowrap">Open report</button></td>
          </tr>)}
        </tbody>
      </table>
    </div>
  </div>;
}
