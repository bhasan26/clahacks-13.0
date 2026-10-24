import {
  Alert,
  AuditEntry,
  Case,
  CaseCheckResult,
  CaseSummary,
  HealthStatus,
  Rule,
} from './types';

const BASE = '/api';

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}

export async function fetchCases(): Promise<CaseSummary[]> {
  const res = await fetch(`${BASE}/cases`);
  return res.json();
}

export async function fetchCaseDetail(caseId: string): Promise<{
  case: Case;
  check_result: CaseCheckResult;
  alerts: Alert[];
}> {
  const res = await fetch(`${BASE}/cases/${caseId}`);
  if (!res.ok) throw new Error('Failed to load case');
  return res.json();
}

export async function createCase(c: Partial<Case>): Promise<{ case: Case; check_result: CaseCheckResult }> {
  const res = await fetch(`${BASE}/cases`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(c),
  });
  return res.json();
}

export async function recheckCase(caseId: string): Promise<CaseCheckResult> {
  const res = await fetch(`${BASE}/cases/${caseId}/check`, { method: 'POST' });
  return res.json();
}

export async function fetchRules(): Promise<Rule[]> {
  const res = await fetch(`${BASE}/rules`);
  return res.json();
}

export async function fetchAlerts(status?: string): Promise<Alert[]> {
  const url = status ? `${BASE}/alerts?status=${status}` : `${BASE}/alerts`;
  const res = await fetch(url);
  return res.json();
}

export async function acknowledgeAlert(alertId: string, officerNote?: string): Promise<Alert> {
  const res = await fetch(`${BASE}/alerts/${alertId}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ officer_note: officerNote }),
  });
  return res.json();
}

export async function triggerSync(): Promise<{ success: boolean; synced_at: string; alerts_affected: number }> {
  const res = await fetch(`${BASE}/sync`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Sync failed');
  }
  return res.json();
}

export async function fetchAudit(): Promise<AuditEntry[]> {
  const res = await fetch(`${BASE}/audit`);
  return res.json();
}

export async function extractCaseFromText(documentText: string): Promise<{
  extracted_case: any;
  confidence: number;
  redacted_fields: string[];
}> {
  const res = await fetch(`${BASE}/cases/extract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_text: documentText }),
  });
  return res.json();
}

// Simulator triggers
export async function simExcludeDrugA() {
  const res = await fetch(`${BASE}/simulator/exclude-drug-a`, { method: 'POST' });
  return res.json();
}

export async function simDelayDrugA() {
  const res = await fetch(`${BASE}/simulator/delay-drug-a`, { method: 'POST' });
  return res.json();
}

export async function simCancelDrugA() {
  const res = await fetch(`${BASE}/simulator/cancel-drug-a`, { method: 'POST' });
  return res.json();
}

export async function simToggleOutage() {
  const res = await fetch(`${BASE}/simulator/toggle-outage`, { method: 'POST' });
  return res.json();
}

export async function simReset() {
  const res = await fetch(`${BASE}/simulator/reset`, { method: 'POST' });
  return res.json();
}
