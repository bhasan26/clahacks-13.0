import React from 'react';
import { History, Shield, Clock } from 'lucide-react';
import { AuditEntry } from '../types';

interface AuditLogViewProps {
  logs: AuditEntry[];
}

export const AuditLogView: React.FC<AuditLogViewProps> = ({ logs }) => {
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900 tracking-tight flex items-center space-x-2">
            <History className="h-5 w-5 text-lime-600" />
            <span>Append-Only Regulatory Audit Log</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Every statement, rule sync, check execution, and officer acknowledgment is immutably recorded for regulatory compliance.
          </p>
        </div>
        <span className="text-xs font-bold text-slate-500 font-mono bg-slate-100 px-3 py-1.5 rounded-xl border border-slate-200">
          {logs.length} Immutable Entries
        </span>
      </div>

      <div className="overflow-hidden rounded-3xl border border-slate-200/80 bg-white shadow-[0_2px_12px_rgba(0,0,0,0.03)]">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50/70 text-slate-400 font-bold uppercase tracking-wider text-[11px]">
              <th className="py-3.5 px-5">Entry ID</th>
              <th className="py-3.5 px-5">Timestamp (UTC)</th>
              <th className="py-3.5 px-5">Actor</th>
              <th className="py-3.5 px-5">Action</th>
              <th className="py-3.5 px-5">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
            {logs.map((log) => (
              <tr key={log.entry_id} className="hover:bg-slate-50/60 transition-colors">
                <td className="py-3 px-5 font-bold text-slate-900">{log.entry_id}</td>
                <td className="py-3 px-5 text-slate-500">
                  {new Date(log.timestamp).toLocaleString()}
                </td>
                <td className="py-3 px-5 text-slate-700">
                  <span className="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 font-semibold text-[10px] border border-slate-200">
                    {log.actor}
                  </span>
                </td>
                <td className="py-3 px-5 font-bold text-slate-900 font-sans text-xs">
                  {log.action}
                </td>
                <td className="py-3 px-5 text-slate-500 font-mono max-w-md truncate">
                  {JSON.stringify(log.details)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
