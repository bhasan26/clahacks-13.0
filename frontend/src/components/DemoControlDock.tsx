import React, { useState } from 'react';

interface DemoControlDockProps {
  onRunCheckNow: () => Promise<void>;
  onToggleFail: () => Promise<void>;
  onReset: () => Promise<void>;
}

export const DemoControlDock: React.FC<DemoControlDockProps> = ({
  onRunCheckNow,
  onToggleFail,
  onReset,
}) => {
  const [isRunning, setIsRunning] = useState(false);

  const handleRun = async () => {
    setIsRunning(true);
    await onRunCheckNow();
    setIsRunning(false);
  };

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 bg-[#092328]/95 backdrop-blur-md text-white border border-[#12544F] rounded-2xl px-4 py-2.5 shadow-2xl flex items-center space-x-3 text-xs">
      <span className="text-[11px] font-bold text-[#8BBB92] uppercase tracking-wider hidden sm:inline">
        Demo Actions:
      </span>

      {/* Primary Action: Run Check Now */}
      <button
        onClick={handleRun}
        disabled={isRunning}
        className="px-3 py-1.5 rounded-xl bg-[#2A835F] hover:bg-[#8BBB92] hover:text-[#092328] font-bold text-white transition-all shadow-sm active:scale-95 cursor-pointer disabled:opacity-50"
        title="Pulls rule change (Drug A excluded Nov 1) and moves 3 open cases to Needs attention"
      >
        {isRunning ? 'Checking rules...' : '▶ Run check now'}
      </button>

      <span className="text-[#12544F]">|</span>

      {/* Toggle Failed Check */}
      <button
        onClick={onToggleFail}
        className="px-2.5 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-white/90 font-semibold transition-all cursor-pointer"
        title="Simulates a check failure to verify the amber header chip and warning banner"
      >
        Simulate check failure
      </button>

      <span className="text-[#12544F]">|</span>

      {/* Reset */}
      <button
        onClick={onReset}
        className="px-2.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/15 text-white/70 hover:text-white font-semibold transition-all cursor-pointer"
        title="Reset demo data to initial 40 cases"
      >
        Reset
      </button>
    </div>
  );
};
