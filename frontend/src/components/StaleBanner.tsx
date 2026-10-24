import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { HealthStatus } from '../types';

interface StaleBannerProps {
  health: HealthStatus | null;
  onSync: () => void;
  isSyncing: boolean;
}

export const StaleBanner: React.FC<StaleBannerProps> = ({ health, onSync, isSyncing }) => {
  if (!health || !health.is_stale) return null;

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-6 py-3">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-xl bg-amber-100 text-amber-700">
            <AlertTriangle className="h-5 w-5 animate-pulse" />
          </div>
          <div>
            <h4 className="text-xs sm:text-sm font-bold text-amber-900">
              Payer Rules Feed May Be Out of Date (Stale Connection Alert)
            </h4>
            <p className="text-xs text-amber-800/80 mt-0.5">
              The direct payer rules sync is delayed (last check was {Math.round(health.age_seconds)}s ago). New claims may not reflect today's policy changes.
            </p>
          </div>
        </div>

        <button
          onClick={onSync}
          disabled={isSyncing}
          className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs transition-all shadow-sm active:scale-95 disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
          <span>Force Refresh Feed</span>
        </button>
      </div>
    </div>
  );
};
