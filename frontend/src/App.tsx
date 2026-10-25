import React, { useState, useEffect } from 'react';
import { PolicyMonitoring } from './components/PolicyMonitoring';
import { ClaimsWorkspace } from './components/ClaimsWorkspace';
import { Sidebar, Tab } from './components/Sidebar';
import { AlertsPage } from './components/AlertsPage';
import { CaseDetailModal } from './components/CaseDetailModal';
import { PolicyIntelligence } from './components/PolicyIntelligence';
import { fetchCases, fetchCaseDetail, fetchUpdates } from './api';
import { Case, CaseCheckResult, ClaimFindingsReport, InsurerUpdateEntry } from './types';

export function App() {
  const [activeTab, setActiveTab] = useState<Tab>('cases');
  const [reviewDocumentId, setReviewDocumentId] = useState<string | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [updates, setUpdates] = useState<InsurerUpdateEntry[]>([]);

  // Claims list narrowed to the claims a rule change affected (cleared on any tab change).
  const [affectedFilterIds, setAffectedFilterIds] = useState<string[]>([]);

  // Claim detail popup
  const [selectedCaseData, setSelectedCaseData] = useState<Case | null>(null);
  const [selectedCaseResult, setSelectedCaseResult] = useState<CaseCheckResult | null>(null);
  const [selectedFindings, setSelectedFindings] = useState<ClaimFindingsReport | null>(null);

  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const loadAll = async () => {
    try {
      const [cs, ups] = await Promise.all([fetchCases(), fetchUpdates()]);
      setCases(cs);
      setUpdates(ups);
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
      setSelectedFindings(detail.findings || null);
      setSelectedCaseData(detail.case);
      setSelectedCaseResult(detail.check_result);
    } catch (err) {
      showToast('Could not load claim details');
    }
  };

  const handleCloseCaseModal = () => {
    setSelectedFindings(null);
    setSelectedCaseData(null);
    setSelectedCaseResult(null);
  };

  const showAffectedClaims = (caseIds: string[]) => {
    setAffectedFilterIds(caseIds);
    setActiveTab('cases');
  };

  return (
    <div className="flex min-h-screen bg-canvas text-ink">
      {toastMessage && (
        <div className="fixed top-6 right-6 z-50 animate-in slide-in-from-top duration-200">
          <div className="bg-cta text-white font-bold text-xs px-4 py-2.5 rounded-xl shadow-xl border border-line-strong">
            {toastMessage}
          </div>
        </div>
      )}

      <Sidebar
        activeTab={activeTab}
        setActiveTab={(tab) => {
          setAffectedFilterIds([]);
          setActiveTab(tab);
        }}
      />

      <div className="flex-1 flex flex-col min-w-0 min-h-screen">
        <main className="flex-1 pb-24">
          {activeTab === 'cases' && (
            <ClaimsWorkspace
              caseIds={affectedFilterIds}
              onClearCaseFilter={() => setAffectedFilterIds([])}
              onSelect={handleOpenCase}
              onChanged={loadAll}
            />
          )}
          {activeTab === 'monitoring' && (
            <PolicyMonitoring
              onReview={(id) => {
                setReviewDocumentId(id);
                setActiveTab('intelligence');
              }}
              onChanged={loadAll}
            />
          )}
          {activeTab === 'updates' && (
            <AlertsPage cases={cases} updates={updates} onSelect={handleOpenCase} onViewAffectedCases={showAffectedClaims} />
          )}
          {activeTab === 'intelligence' && (
            <PolicyIntelligence
              initialDocumentId={reviewDocumentId}
              onPolicyApproved={async (affectedIds) => {
                showToast(`Rule approved. ${affectedIds.length} claim(s) re-checked.`);
                await loadAll();
              }}
              onNavigateToCases={showAffectedClaims}
            />
          )}
        </main>
      </div>

      <CaseDetailModal
        findings={selectedFindings}
        caseData={selectedCaseData}
        checkResult={selectedCaseResult}
        onClose={handleCloseCaseModal}
      />
    </div>
  );
}

export default App;
