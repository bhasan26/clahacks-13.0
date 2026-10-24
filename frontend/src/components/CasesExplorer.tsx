import React, { useState } from 'react';
import { Search, Filter, ArrowUpRight, CheckCircle2, AlertTriangle, HelpCircle, FileText, Calendar, Plus } from 'lucide-react';
import { CaseOverallStatus, CaseSummary } from '../types';

interface CasesExplorerProps {
  cases: CaseSummary[];
  onSelectCase: (caseId: string) => void;
  openIntake: () => void;
}

export const CasesExplorer: React.FC<CasesExplorerProps> = ({ cases, onSelectCase, openIntake }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | CaseOverallStatus>('all');

  const filteredCases = cases.filter((c) => {
    const matchesSearch =
      c.case.case_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.case.member_ref.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.case.items.some((i) => i.code.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesStatus = statusFilter === 'all' || c.overall_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status: CaseOverallStatus) => {
    switch (status) {
      case 'clear':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-lime-100 text-lime-800 border border-lime-200">
            <CheckCircle2 className="h-3.5 w-3.5 text-lime-700" />
            <span>Clear</span>
          </span>
        );
      case 'needs_attention':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-700" />
            <span>Needs Attention</span>
          </span>
        );
      case 'cannot_assess':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-200">
            <HelpCircle className="h-3.5 w-3.5 text-slate-500" />
            <span>Cannot Assess</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900">Hospital Claims Registry</h2>
          <p className="text-xs text-slate-500 mt-1">
            Audited patient claims verified against active insurer coverage and document requirements.
          </p>
        </div>

        <button
          onClick={openIntake}
          className="inline-flex items-center space-x-1.5 px-4 py-2.5 rounded-2xl text-xs font-bold bg-slate-900 hover:bg-slate-800 text-white shadow-sm transition-all active:scale-95 cursor-pointer"
        >
          <Plus className="h-4 w-4 text-lime-400" />
          <span>+ Upload Patient File</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 rounded-2xl bg-white border border-slate-200/80 shadow-sm">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search claim ID, member, code..."
            className="w-full pl-10 pr-4 py-2 rounded-xl text-xs bg-slate-50 border border-slate-200 text-slate-900 placeholder-slate-400 focus:outline-none focus:border-slate-400 focus:ring-1 focus:ring-slate-300 transition-all"
          />
        </div>

        <div className="flex items-center space-x-2 w-full sm:w-auto">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center space-x-1">
            <Filter className="h-3.5 w-3.5" />
            <span>Filter:</span>
          </span>
          <div className="flex bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-bold">
            <button
              onClick={() => setStatusFilter('all')}
              className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                statusFilter === 'all'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              All ({cases.length})
            </button>
            <button
              onClick={() => setStatusFilter('clear')}
              className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                statusFilter === 'clear'
                  ? 'bg-lime-400 text-slate-950 shadow-sm'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              Clear
            </button>
            <button
              onClick={() => setStatusFilter('needs_attention')}
              className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                statusFilter === 'needs_attention'
                  ? 'bg-amber-400 text-slate-950 shadow-sm'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              Needs Attention
            </button>
            <button
              onClick={() => setStatusFilter('cannot_assess')}
              className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                statusFilter === 'cannot_assess'
                  ? 'bg-slate-300 text-slate-950 shadow-sm'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              Cannot Assess
            </button>
          </div>
        </div>
      </div>

      {/* Cases Table */}
      <div className="bg-white rounded-3xl border border-slate-200/80 shadow-[0_2px_12px_rgba(0,0,0,0.03)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-600">
            <thead className="bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-200">
              <tr>
                <th className="px-6 py-4">Case ID</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Patient / Member Ref</th>
                <th className="px-6 py-4">Service Date</th>
                <th className="px-6 py-4">Items Checked</th>
                <th className="px-6 py-4">Diagnoses</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredCases.map((c) => (
                <tr
                  key={c.case.case_id}
                  onClick={() => onSelectCase(c.case.case_id)}
                  className="hover:bg-slate-50/80 transition-colors cursor-pointer group"
                >
                  <td className="px-6 py-4 font-mono font-bold text-slate-900 group-hover:text-lime-700 transition-colors">
                    {c.case.case_id}
                  </td>
                  <td className="px-6 py-4">{getStatusBadge(c.overall_status)}</td>
                  <td className="px-6 py-4 font-mono font-medium text-slate-600">
                    {c.case.member_ref}
                    <span className="block text-[10px] text-slate-400 font-sans">
                      {c.case.plan_id}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="flex items-center space-x-1.5 font-medium text-slate-700">
                      <Calendar className="h-3.5 w-3.5 text-slate-400" />
                      <span>{c.case.service_date}</span>
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1">
                      {c.case.items.map((item, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 rounded-lg bg-slate-100 text-slate-800 text-[11px] font-mono font-bold border border-slate-200"
                        >
                          {item.code}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1">
                      {c.case.diagnoses.map((dx, idx) => (
                        <span
                          key={idx}
                          className="text-[11px] text-slate-500 font-medium"
                        >
                          {dx.code}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectCase(c.case.case_id);
                      }}
                      className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-900 hover:text-white text-slate-700 font-bold text-xs transition-all cursor-pointer"
                    >
                      <span>Inspect</span>
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
