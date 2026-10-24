import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { DashboardOverview } from './components/DashboardOverview';
import { StaleBanner } from './components/StaleBanner';
import { AlertsInbox } from './components/AlertsInbox';
import { CasesExplorer } from './components/CasesExplorer';
import { CaseDetailModal } from './components/CaseDetailModal';
import { RulesLibrary } from './components/RulesLibrary';
import { AuditLogView } from './components/AuditLogView';
import { ClinicalIntakeModal } from './components/ClinicalIntakeModal';
import { SimulatorBar } from './components/SimulatorBar';
import {
  fetchHealth,
  fetchCases,
  fetchAlerts,
  fetchRules,
  fetchAudit,
  fetchCaseDetail,
  acknowledgeAlert,
  triggerSync,
  recheckCase,
} from './api';
import { HealthStatus, CaseSummary, Alert, Rule, AuditEntry, Case, CaseCheckResult } from './types';

export function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'alerts' | 'cases' | 'rules' | 'audit'>('dashboard');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditEntry[]>([]);

  // Modals state
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [selectedCaseData, setSelectedCaseData] = useState<Case | null>(null);
  const [selectedCaseResult, setSelectedCaseResult] = useState<CaseCheckResult | null>(null);
  const [selectedCaseAlerts, setSelectedCaseAlerts] = useState<Alert[]>([]);
  const [isIntakeOpen, setIsIntakeOpen] = useState(false);

  // Loading & Toasts
  const [isSyncing, setIsSyncing] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [h, c, a, r, log] = await Promise.all([
        fetchHealth(),
        fetchCases(),
        fetchAlerts(),
        fetchRules(),
        fetchAudit(),
      ]);
      setHealth(h);
      setCases(c);
      setAlerts(a);
      setRules(r);
      setAuditLogs(log);
    } catch (err) {
      console.error('Failed to load initial data', err);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 4000); // Polling for live status & age updates
    return () => clearInterval(interval);
  }, []);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const res = await triggerSync();
      showToast(`Sync complete: ${res.alerts_affected} open claims evaluated.`);
      await loadData();
    } catch (err: any) {
      showToast(err.message || 'Sync failed');
    } finally {
      setIsSyncing(false);
    }
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const handleOpenCase = async (caseId: string) => {
    try {
      const detail = await fetchCaseDetail(caseId);
      setSelectedCaseId(caseId);
      setSelectedCaseData(detail.case);
      setSelectedCaseResult(detail.check_result);
      setSelectedCaseAlerts(detail.alerts);
    } catch (err) {
      showToast('Could not load case details');
    }
  };

  const handleRecheckCase = async (caseId: string) => {
    try {
      const res = await recheckCase(caseId);
      setSelectedCaseResult(res);
      showToast(`Case ${caseId} re-evaluated: Status ${res.overall_status}`);
      await loadData();
    } catch (err) {
      showToast('Re-check failed');
    }
  };

  const handleAcknowledgeAlert = async (alertId: string, note?: string) => {
    try {
      await acknowledgeAlert(alertId, note);
      showToast('Alert acknowledged');
      await loadData();
    } catch (err) {
      showToast('Failed to acknowledge alert');
    }
  };

  const handleScenarioTriggered = async (msg: string) => {
    showToast(msg);
    await loadData();
    if (selectedCaseId) {
      handleOpenCase(selectedCaseId);
    }
  };

  return (
    <div className="min-h-screen bg-[#F4F5F7] text-slate-900 flex antialiased">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-6 right-8 z-50 animate-in slide-in-from-top duration-300">
          <div className="bg-slate-900 text-white font-bold text-xs px-4 py-3 rounded-2xl shadow-2xl flex items-center space-x-2 border border-slate-700">
            <span className="text-lime-400">✨</span>
            <span>{toastMessage}</span>
          </div>
        </div>
      )}

      {/* Left Navigation Sidebar (ACRU Dribbble Layout) */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        health={health}
        onSync={handleSync}
        isSyncing={isSyncing}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-h-screen min-w-0 pb-36">
        {/* Top Header Bar */}
        <TopBar
          health={health}
          openIntake={() => setIsIntakeOpen(true)}
          onSync={handleSync}
          isSyncing={isSyncing}
        />

        {/* Stale Rules Warning Banner if feed disconnected */}
        <StaleBanner health={health} onSync={handleSync} isSyncing={isSyncing} />

        {/* View Router */}
        <main className="p-6 sm:p-8 max-w-7xl w-full mx-auto flex-1">
          {activeTab === 'dashboard' && (
            <DashboardOverview
              health={health}
              cases={cases}
              alerts={alerts}
              rules={rules}
              onSelectCase={handleOpenCase}
              onNavigateTab={(tab) => setActiveTab(tab)}
              openIntake={() => setIsIntakeOpen(true)}
              onSync={handleSync}
              isSyncing={isSyncing}
            />
          )}

          {activeTab === 'alerts' && (
            <AlertsInbox
              alerts={alerts}
              cases={cases}
              onSelectCase={handleOpenCase}
              onAcknowledge={handleAcknowledgeAlert}
            />
          )}

          {activeTab === 'cases' && (
            <CasesExplorer
              cases={cases}
              onSelectCase={handleOpenCase}
              openIntake={() => setIsIntakeOpen(true)}
            />
          )}

          {activeTab === 'rules' && <RulesLibrary rules={rules} />}

          {activeTab === 'audit' && <AuditLogView logs={auditLogs} />}
        </main>
      </div>

      {/* Case Detail Modal */}
      <CaseDetailModal
        caseData={selectedCaseData}
        checkResult={selectedCaseResult}
        alerts={selectedCaseAlerts}
        onClose={() => setSelectedCaseId(null)}
        onRecheck={handleRecheckCase}
      />

      {/* AI Clinical Intake Modal */}
      <ClinicalIntakeModal
        isOpen={isIntakeOpen}
        onClose={() => setIsIntakeOpen(false)}
        onCaseCreated={(newCase) => {
          showToast(`Case ${newCase.case_id} added and evaluated!`);
          loadData();
          handleOpenCase(newCase.case_id);
        }}
      />

      {/* Simulator Bottom Dock Control Bar */}
      <SimulatorBar onScenarioTriggered={handleScenarioTriggered} />
    </div>
  );
}

export default App;
