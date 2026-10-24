import React, { useState } from 'react';
import { Search, BookOpen, Layers, Shield, Calendar, ArrowRight } from 'lucide-react';
import { Rule, RuleStatus } from '../types';

interface RulesLibraryProps {
  rules: Rule[];
}

export const RulesLibrary: React.FC<RulesLibraryProps> = ({ rules }) => {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredRules = rules.filter((r) => {
    const term = searchTerm.toLowerCase();
    return (
      r.rule_id.toLowerCase().includes(term) ||
      r.target.code.toLowerCase().includes(term) ||
      (r.target.name && r.target.name.toLowerCase().includes(term)) ||
      r.effect.toLowerCase().includes(term)
    );
  });

  const getStatusBadge = (status: RuleStatus) => {
    switch (status) {
      case 'effective':
        return <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase bg-emerald-100 text-emerald-800 border border-emerald-200">Effective</span>;
      case 'announced':
        return <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase bg-blue-100 text-blue-800 border border-blue-200">Announced</span>;
      case 'delayed':
        return <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase bg-amber-100 text-amber-800 border border-amber-200">Delayed</span>;
      case 'cancelled':
        return <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase bg-rose-100 text-rose-800 border border-rose-200">Cancelled</span>;
      case 'superseded':
        return <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase bg-slate-100 text-slate-500 border border-slate-200">Superseded</span>;
    }
  };

  const getEffectBadge = (effect: string) => {
    switch (effect) {
      case 'covered':
        return <span className="font-bold text-emerald-600">Covered</span>;
      case 'excluded':
        return <span className="font-bold text-rose-600">Excluded</span>;
      case 'requires_prior_approval':
        return <span className="font-bold text-amber-600">Prior Approval Required</span>;
      case 'requires_documents':
        return <span className="font-bold text-orange-600">Supporting Docs Required</span>;
      default:
        return <span className="font-bold text-slate-800">{effect}</span>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900 flex items-center space-x-2">
            <span>Payer Coverage Rules Catalog</span>
            <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
              {rules.length} Versions Stored
            </span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Immutable versioned policy rules synchronized directly from the read-only insurer feed. Rules are never overwritten—only superseded.
          </p>
        </div>

        {/* Search Input */}
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search rule ID, code, or effect..."
            className="w-full pl-10 pr-4 py-2 rounded-xl text-xs bg-white border border-slate-200 text-slate-900 placeholder-slate-400 focus:outline-none focus:border-slate-400 focus:ring-1 focus:ring-slate-300 transition-all shadow-sm"
          />
        </div>
      </div>

      {/* Rules Table */}
      <div className="bg-white rounded-3xl border border-slate-200/80 shadow-[0_2px_12px_rgba(0,0,0,0.03)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-600">
            <thead className="bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-200">
              <tr>
                <th className="px-6 py-4">Rule & Version</th>
                <th className="px-6 py-4">Payer / Plan Scope</th>
                <th className="px-6 py-4">Target Item</th>
                <th className="px-6 py-4">Coverage Effect</th>
                <th className="px-6 py-4">Lifecycle Status</th>
                <th className="px-6 py-4">Effective Window</th>
                <th className="px-6 py-4 text-right">Source Ref</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredRules.map((r) => (
                <tr key={`${r.rule_id}_v${r.version}`} className="hover:bg-slate-50/80 transition-colors">
                  <td className="px-6 py-4 font-mono font-bold text-slate-900">
                    {r.rule_id} <span className="text-slate-400 font-normal">v{r.version}</span>
                  </td>
                  <td className="px-6 py-4 font-medium text-slate-700">
                    {r.insurer_id}
                    <span className="block text-[10px] text-slate-400 font-mono">
                      {r.plan_ids.join(', ')}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-0.5 rounded-lg bg-slate-100 text-slate-900 font-mono font-bold border border-slate-200">
                      {r.target.code}
                    </span>
                    {r.target.name && (
                      <span className="block text-[11px] text-slate-500 mt-0.5">
                        {r.target.name}
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4">{getEffectBadge(r.effect)}</td>
                  <td className="px-6 py-4">{getStatusBadge(r.status)}</td>
                  <td className="px-6 py-4 font-mono text-[11px] text-slate-600">
                    {r.effective_from} → {r.effective_to || 'Indefinite'}
                  </td>
                  <td className="px-6 py-4 text-right font-mono text-[10px] text-slate-400">
                    {r.source_ref}
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
