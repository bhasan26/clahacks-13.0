import React, { useState, useEffect } from 'react';
import { PolicyMonitoring } from './components/PolicyMonitoring';
import { ClaimsWorkspace } from './components/ClaimsWorkspace';
import { WorkflowOverview, ClaimAlerts } from './components/WorkflowOverview';
import { Sidebar } from './components/Sidebar';
import { DashboardPage } from './components/DashboardPage';
import { CasesPage } from './components/CasesPage';
import { UpdatesPage } from './components/UpdatesPage';
import { CaseDetailModal } from './components/CaseDetailModal';
import { UploadPatientFileModal } from './components/UploadPatientFileModal';
import { DemoControlDock } from './components/DemoControlDock';
import { PolicyIntelligence } from './components/PolicyIntelligence';
import {
  fetchDashboard,
  fetchCases,
  fetchCaseDetail,
  fetchUpdates,
  fetchConnection,
  triggerRunCheckNow,
  updateCleanClaimsTarget,
  toggleCheckFailure,
  resetDemoState,
} from './api';
import {
  DashboardData,
  Case,
  CaseCheckResult,
  InsurerUpdateEntry,
  InsurerConnectionInfo,
} from './types';

export function App() {
  const [affectedFilterIds,setAffectedFilterIds]=useState<string[]>([]);
  const [reviewDocumentId, setReviewDocumentId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'cases' | 'updates' | 'intelligence' | 'monitoring'>('dashboard');
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [updates, setUpdates] = useState<InsurerUpdateEntry[]>([]);
  const [connection, setConnection] = useState<InsurerConnectionInfo | null>(null);

  // Filter pass-through from dashboard or updates to cases
  const [initialStatusFilter, setInitialStatusFilter] = useState<string>('All');
  const [initialSpecialtyFilter, setInitialSpecialtyFilter] = useState<string>('All');

  // Case Detail Modal
  const [selectedCaseData, setSelectedCaseData] = useState<Case | null>(null);
  const [selectedCaseResult, setSelectedCaseResult] = useState<CaseCheckResult | null>(null);

  // Upload Modal
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  // Toast
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const loadAll = async () => {
    try {
      const [dash, cs, ups, conn] = await Promise.all([
        fetchDashboard(),
        fetchCases(),
        fetchUpdates(),
        fetchConnection(),
      ]);
      setDashboardData(dash);
      setCases(cs);
      setUpdates(ups);
      setConnection(conn);
    } catch (err) {
      console.error('Failed to load application data', err);
    }
  };

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleOpenCase = async (caseId: string) => {
    try {
      const detail = await fetchCaseDetail(caseId);
      setSelectedCaseData(detail.case);
      setSelectedCaseResult(detail.check_result);
    } catch (err) {
      showToast('Could not load case detail');
    }
  };

  const handleCloseCaseModal = () => {
    setSelectedCaseData(null);
    setSelectedCaseResult(null);
  };

  const handleNavigateToCasesWithFilter = (status?: string, specialty?: string) => {
    setAffectedFilterIds([]);
    setInitialStatusFilter(status || 'All');
    setInitialSpecialtyFilter(specialty || 'All');
    setActiveTab('cases');
  };

  const handleViewAffectedCases = (caseIds: string[]) => {
    // When clicking "Affects N open cases", navigate to Cases
    setAffectedFilterIds(caseIds);
    setInitialStatusFilter('All');
    setInitialSpecialtyFilter('All');
    setActiveTab('cases');
    showToast(`Filtered to open cases affected by policy update (${caseIds.join(', ')})`);
  };

  const handleUpdateTarget = async (target: number) => {
    try {
      await updateCleanClaimsTarget(target);
      showToast(`Target updated to ${target}%`);
      const dash = await fetchDashboard();
      setDashboardData(dash);
    } catch (err) {
      showToast('Failed to update target');
    }
  };

  const handleRunCheckNow = async () => {
    try {
      const res = await triggerRunCheckNow();
      showToast(res.message || 'Check complete: 3 open cases moved to Needs attention.');
      await loadAll();
    } catch (err) {
      showToast('Failed to run check now');
    }
  };

  const handleToggleFail = async () => {
    try {
      const res = await toggleCheckFailure();
      showToast(
        res.is_check_failed
          ? 'Simulated check failure: chip set to Check pending.'
          : 'Check restored: chip set to Access active.'
      );
      const conn = await fetchConnection();
      setConnection(conn);
    } catch (err) {
      showToast('Failed to toggle check failure');
    }
  };

  const handleResetDemo = async () => {
    try {
      await resetDemoState();
      setInitialStatusFilter('All');
      setInitialSpecialtyFilter('All');
      showToast('Demo state reset to initial 40 cases.');
      await loadAll();
    } catch (err) {
      showToast('Failed to reset demo');
    }
  };

  return (
    <div className="min-h-screen bg-white text-[#092328] flex antialiased selection:bg-[#8BBB92]/20">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-6 right-6 z-50 animate-in slide-in-from-top duration-200">
          <div className="bg-[#092328] text-white font-bold text-xs px-4 py-2.5 rounded-xl shadow-xl border border-[#12544F]">
            {toastMessage}
          </div>
        </div>
      )}

      {/* Professional Vertical Sidebar Navigation */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={(tab) => {
          setAffectedFilterIds([]);
          setInitialStatusFilter('All');
          setInitialSpecialtyFilter('All');
          setActiveTab(tab);
        }}
        connection={connection}
        onRunCheckNow={handleRunCheckNow}
        onToggleFail={handleToggleFail}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen">
        {/* If the last check failed, a one-line banner appears that rules may be out of date */}
        {connection?.is_check_failed && (
          <div className="bg-[#FEF3C7] border-b border-[#F59E0B]/30 px-8 py-2 text-center text-xs font-semibold text-[#92400E]">
            Rules may be out of date. Re-check in progress.
          </div>
        )}

        {/* Page Routing */}
        <main className="flex-1 pb-24">
          {activeTab === 'dashboard' && (
            <><WorkflowOverview /><DashboardPage
              data={dashboardData}
              onNavigateToUpdates={() => setActiveTab('updates')}
              onNavigateToCasesWithFilter={handleNavigateToCasesWithFilter}
              onUpdateTarget={handleUpdateTarget}
            /></>
          )}

          {activeTab === 'cases' && <ClaimsWorkspace initialStatusFilter={initialStatusFilter} initialSpecialtyFilter={initialSpecialtyFilter} caseIds={affectedFilterIds} onSelect={handleOpenCase} onClinicalUpload={()=>setIsUploadOpen(true)} onChanged={loadAll} />}
          {activeTab === 'monitoring' && <PolicyMonitoring onReview={id=>{setReviewDocumentId(id);setActiveTab('intelligence');}} onChanged={loadAll} />}

          {activeTab === 'updates' && (
            <><ClaimAlerts cases={cases} onSelect={handleOpenCase}/><UpdatesPage
              updates={updates}
              onViewAffectedCases={handleViewAffectedCases}
            /></>
          )}

          {activeTab === 'intelligence' && (
            <PolicyIntelligence
              initialDocumentId={reviewDocumentId}
              onPolicyApproved={async (affectedIds) => {
                showToast(`Policy approved! ${affectedIds.length} hospital claims updated.`);
                await loadAll();
              }}
              onNavigateToCases={(caseIds) => {
                setInitialStatusFilter('Needs attention');
                setInitialSpecialtyFilter('All');
                setActiveTab('cases');
                showToast(`Filtered to claims affected by policy change (${caseIds.slice(0, 5).join(', ')}...)`);
              }}
            />
          )}
        </main>
      </div>

      {/* Page 3: Case Detail Modal */}
      <CaseDetailModal
        caseData={selectedCaseData}
        checkResult={selectedCaseResult}
        onClose={handleCloseCaseModal}
      />

      {/* Upload Patient File Modal */}
      <UploadPatientFileModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onCaseCreated={(newCase) => {
          showToast(`Case ${newCase.case_id} uploaded and checked!`);
          loadAll();
          handleOpenCase(newCase.case_id);
        }}
      />

      {/* Floating Control Bar (only visible when requested via ?demo=true) */}
      {typeof window !== 'undefined' && window.location.search.includes('demo=true') && (
        <DemoControlDock
          onRunCheckNow={handleRunCheckNow}
          onToggleFail={handleToggleFail}
          onReset={handleResetDemo}
        />
      )}
    </div>
  );
}

export default App;
