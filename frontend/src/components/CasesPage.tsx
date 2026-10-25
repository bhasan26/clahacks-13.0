import React, { useState } from 'react';
import { Case, CaseStatusType } from '../types';

interface CasesPageProps {
  cases: Case[];
  onSelectCase: (caseId: string) => void;
  onOpenUploadModal: () => void;
  initialStatusFilter?: string;
  initialSpecialtyFilter?: string;
}

export const CasesPage: React.FC<CasesPageProps> = ({
  cases,
  onSelectCase,
  onOpenUploadModal,
  initialStatusFilter = 'All',
  initialSpecialtyFilter = 'All',
}) => {
  const [statusFilter, setStatusFilter] = useState<string>(initialStatusFilter);
  const [specialtyFilter, setSpecialtyFilter] = useState<string>(initialSpecialtyFilter);

  const specialties = [
    'All',
    'Cardiology',
    'Oncology',
    'Orthopedics',
    'Neurology',
    'Gastroenterology',
  ];

  const statuses = ['All', 'Approved', 'Needs attention', 'Missing or wrong info'];

  // Filter cases
  const filteredCases = cases.filter((c) => {
    const matchesStatus =
      statusFilter === 'All' || c.status.toLowerCase() === statusFilter.toLowerCase();
    const matchesSpecialty =
      specialtyFilter === 'All' || c.specialty.toLowerCase() === specialtyFilter.toLowerCase();
    return matchesStatus && matchesSpecialty;
  });

  const getStatusBadge = (status: CaseStatusType) => {
    switch (status) {
      case 'Approved':
        return (
          <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-[#2A835F]/15 text-[#2A835F] border border-[#2A835F]/30">
            <span className="h-1.5 w-1.5 rounded-full bg-[#2A835F]" />
            <span>No checked issue</span>
          </span>
        );
      case 'Needs attention':
        return (
          <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-[#D97706]/15 text-[#D97706] border border-[#D97706]/30">
            <span className="h-1.5 w-1.5 rounded-full bg-[#D97706]" />
            <span>Needs attention</span>
          </span>
        );
      case 'Missing or wrong info':
        return (
          <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-[#DC2626]/15 text-[#DC2626] border border-[#DC2626]/30">
            <span className="h-1.5 w-1.5 rounded-full bg-[#DC2626]" />
            <span>Missing or wrong info</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto py-8 px-6">
      {/* Top Header & Upload Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-black text-[#092328] tracking-tight">
            Cases
          </h1>
          <p className="text-xs text-[#12544F]/70 mt-0.5">
            Open patient claims evaluated against the insurer's current rules.
          </p>
        </div>

        <button
          onClick={onOpenUploadModal}
          className="px-4 py-2.5 rounded-xl bg-[#092328] hover:bg-[#12544F] text-white text-xs font-bold transition-all shadow-sm active:scale-95 cursor-pointer self-start sm:self-auto"
        >
          + Upload patient file
        </button>
      </div>

      {/* Filters Bar: Status & Specialty */}
      <div className="bg-white border border-[#D8E5DC] rounded-2xl p-4 shadow-sm flex flex-wrap items-center justify-between gap-4">
        {/* Status Filter */}
        <div className="flex items-center space-x-2">
          <span className="text-xs font-bold text-[#12544F]/70">Status:</span>
          <div className="flex items-center space-x-1">
            {statuses.map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  statusFilter === st
                    ? 'bg-[#092328] text-white'
                    : 'text-[#12544F]/80 hover:bg-[#F0F5F2]'
                }`}
              >
                {st}
              </button>
            ))}
          </div>
        </div>

        {/* Specialty Filter */}
        <div className="flex items-center space-x-2">
          <span className="text-xs font-bold text-[#12544F]/70">Specialty:</span>
          <select
            value={specialtyFilter}
            onChange={(e) => setSpecialtyFilter(e.target.value)}
            className="px-3 py-1 text-xs font-semibold bg-[#F0F5F2] border border-[#D8E5DC] rounded-lg text-[#092328] focus:outline-none cursor-pointer"
          >
            {specialties.map((sp) => (
              <option key={sp} value={sp}>
                {sp}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Cases Table */}
      <div className="bg-white border border-[#D8E5DC] rounded-2xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F0F5F2] border-b border-[#D8E5DC] text-[#12544F] font-bold">
              <tr>
                <th className="py-3 px-5">Case ID</th>
                <th className="py-3 px-5">Specialty</th>
                <th className="py-3 px-5">Status</th>
                <th className="py-3 px-5 text-right">Items (count)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EAEFEA]">
              {filteredCases.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-16 text-center text-xs text-[#12544F]/70">
                    <div className="max-w-sm mx-auto space-y-2">
                      <p className="font-bold text-sm text-[#092328]">
                        {cases.length === 0 ? 'No cases in caseload yet' : 'No cases match the selected filters'}
                      </p>
                      <p className="text-[#698579] text-xs">
                        {cases.length === 0
                          ? 'Demo entries deleted. File or upload a patient case to run a real-time coverage audit.'
                          : 'Try selecting a different specialty or status filter.'}
                      </p>
                      {cases.length === 0 && (
                        <button
                          type="button"
                          onClick={onOpenUploadModal}
                          className="mt-2 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#2A835F] text-white text-xs font-bold hover:bg-[#1F6347] transition-all shadow-sm cursor-pointer"
                        >
                          + File Patient Case
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                filteredCases.map((c) => (
                  <tr
                    key={c.case_id}
                    onClick={() => onSelectCase(c.case_id)}
                    className="hover:bg-[#F0F5F2]/50 transition-colors cursor-pointer group"
                  >
                    <td className="py-3.5 px-5 font-bold font-mono text-[#092328] group-hover:text-[#2A835F]">
                      {c.case_id}
                    </td>
                    <td className="py-3.5 px-5 font-semibold text-[#092328]">
                      {c.specialty}
                    </td>
                    <td className="py-3.5 px-5">
                      {getStatusBadge(c.status)}
                    </td>
                    <td className="py-3.5 px-5 text-right font-mono font-bold text-[#12544F]">
                      {c.items_count} {c.items_count === 1 ? 'item' : 'items'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="p-3 bg-[#FBFDFB] border-t border-[#D8E5DC] text-[11px] text-[#12544F]/60 flex justify-between">
          <span>Showing {filteredCases.length} of {cases.length} cases</span>
          <span>Click any row to open case detail</span>
        </div>
      </div>
    </div>
  );
};
