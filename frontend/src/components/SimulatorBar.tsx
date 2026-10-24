import React, { useState } from 'react';
import { Sliders, AlertOctagon, Clock, CheckCircle, WifiOff, RotateCcw, ChevronUp, ChevronDown, Sparkles } from 'lucide-react';
import {
  simExcludeDrugA,
  simDelayDrugA,
  simCancelDrugA,
  simToggleOutage,
  simReset,
} from '../api';

interface SimulatorBarProps {
  onScenarioTriggered: (message: string) => void;
}

export const SimulatorBar: React.FC<SimulatorBarProps> = ({ onScenarioTriggered }) => {
  const [isOpen, setIsOpen] = useState(true);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const handleAction = async (name: string, fn: () => Promise<any>) => {
    setLoadingAction(name);
    try {
      const res = await fn();
      onScenarioTriggered(res.message || 'Action executed successfully');
    } catch (err: any) {
      onScenarioTriggered(`Error: ${err.message}`);
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 w-full max-w-4xl px-4 pointer-events-none">
      <div className="bg-white/95 border border-slate-200/90 rounded-2xl shadow-[0_16px_40px_rgba(0,0,0,0.12)] backdrop-blur-md pointer-events-auto overflow-hidden transition-all">
        {/* Toggle Bar */}
        <div
          onClick={() => setIsOpen(!isOpen)}
          className="px-4 py-2 bg-slate-50 border-b border-slate-200/80 flex items-center justify-between cursor-pointer select-none"
        >
          <div className="flex items-center space-x-2">
            <span className="h-2 w-2 rounded-full bg-lime-500 animate-pulse"></span>
            <span className="text-xs font-bold text-slate-800 tracking-wide uppercase">
              Live Demo & Pitch Simulator Bar
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-200 text-slate-700">
              Interactive Judgement Console
            </span>
          </div>

          <div className="flex items-center space-x-1 text-slate-500 hover:text-slate-800 text-xs font-semibold">
            <span>{isOpen ? 'Minimize' : 'Expand Controls'}</span>
            {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </div>
        </div>

        {/* Action Buttons */}
        {isOpen && (
          <div className="p-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5 bg-white">
            {/* 1. Exclude DRUG-A */}
            <button
              onClick={() => handleAction('exclude', simExcludeDrugA)}
              disabled={loadingAction !== null}
              className="p-2.5 rounded-xl bg-amber-50 hover:bg-amber-100/80 border border-amber-200 text-amber-900 flex flex-col items-center text-center transition-all active:scale-95 disabled:opacity-50 cursor-pointer shadow-sm group"
            >
              <AlertOctagon className="h-4 w-4 mb-1 text-amber-600 group-hover:scale-110 transition-transform" />
              <span className="text-[11px] font-bold">1. Exclude DRUG-A</span>
              <span className="text-[10px] text-amber-700 font-medium">Flags 3 of 30 claims</span>
            </button>

            {/* 2. Delay Rule */}
            <button
              onClick={() => handleAction('delay', simDelayDrugA)}
              disabled={loadingAction !== null}
              className="p-2.5 rounded-xl bg-blue-50 hover:bg-blue-100/80 border border-blue-200 text-blue-900 flex flex-col items-center text-center transition-all active:scale-95 disabled:opacity-50 cursor-pointer shadow-sm group"
            >
              <Clock className="h-4 w-4 mb-1 text-blue-600 group-hover:scale-110 transition-transform" />
              <span className="text-[11px] font-bold">2. Delay to Dec 1</span>
              <span className="text-[10px] text-blue-700 font-medium">Auto-closes alerts</span>
            </button>

            {/* 3. Cancel Exclusion */}
            <button
              onClick={() => handleAction('cancel', simCancelDrugA)}
              disabled={loadingAction !== null}
              className="p-2.5 rounded-xl bg-emerald-50 hover:bg-emerald-100/80 border border-emerald-200 text-emerald-900 flex flex-col items-center text-center transition-all active:scale-95 disabled:opacity-50 cursor-pointer shadow-sm group"
            >
              <CheckCircle className="h-4 w-4 mb-1 text-emerald-600 group-hover:scale-110 transition-transform" />
              <span className="text-[11px] font-bold">3. Cancel Change</span>
              <span className="text-[10px] text-emerald-700 font-medium">Reverts to covered</span>
            </button>

            {/* 4. Simulate Feed Failure */}
            <button
              onClick={() => handleAction('outage', simToggleOutage)}
              disabled={loadingAction !== null}
              className="p-2.5 rounded-xl bg-purple-50 hover:bg-purple-100/80 border border-purple-200 text-purple-900 flex flex-col items-center text-center transition-all active:scale-95 disabled:opacity-50 cursor-pointer shadow-sm group"
            >
              <WifiOff className="h-4 w-4 mb-1 text-purple-600 group-hover:scale-110 transition-transform" />
              <span className="text-[11px] font-bold">4. Cut Feed Link</span>
              <span className="text-[10px] text-purple-700 font-medium">Stale Rules Banner</span>
            </button>

            {/* 5. Reset Demo State */}
            <button
              onClick={() => handleAction('reset', simReset)}
              disabled={loadingAction !== null}
              className="p-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white flex flex-col items-center text-center transition-all active:scale-95 disabled:opacity-50 cursor-pointer shadow-sm group col-span-2 sm:col-span-1"
            >
              <RotateCcw className="h-4 w-4 mb-1 text-lime-400 group-hover:rotate-180 transition-transform duration-500" />
              <span className="text-[11px] font-bold text-white">↺ Reset Demo</span>
              <span className="text-[10px] text-slate-400 font-medium">Clean 30 baseline</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
