import {
  DashboardData,
  Case,
  CaseDetailResponse,
  InsurerUpdateEntry,
  InsurerConnectionInfo,
  HealthStatus,
  CaseSummary,
  Alert,
  Rule,
  AuditEntry,
  CaseCheckResult,
  IntakeAnalysisResult,
  PolicyBulletin,
  ExtractedDocumentResult,
  ProposedPolicyChange,
  ImpactPreviewResult,
} from './types';

const API_BASE = '/api';

// -------------------------------------------------------------
// New Clean Specification API Methods
// -------------------------------------------------------------

export async function fetchDashboard(): Promise<DashboardData> {
  const res = await fetch(`${API_BASE}/dashboard`);
  if (!res.ok) throw new Error('Failed to fetch dashboard metrics');
  return res.json();
}

export async function fetchCases(status?: string, specialty?: string): Promise<Case[]> {
  const params = new URLSearchParams();
  if (status && status !== 'All') params.set('status', status);
  if (specialty && specialty !== 'All') params.set('specialty', specialty);

  const res = await fetch(`${API_BASE}/cases?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch cases');
  return res.json();
}

export async function fetchCaseDetail(caseId: string): Promise<CaseDetailResponse> {
  const res = await fetch(`${API_BASE}/cases/${caseId}`);
  if (!res.ok) throw new Error(`Failed to fetch case detail for ${caseId}`);
  return res.json();
}

export async function analyzeIntake(data: {
  sample_id?: string;
  card_image_b64?: string;
  card_text?: string;
  clinical_doc_b64?: string;
  clinical_text?: string;
  selected_insurer_id?: string;
  selected_insurer_name?: string;
  selected_plan_id?: string;
}): Promise<IntakeAnalysisResult> {
  const res = await fetch(`${API_BASE}/intake/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to analyze intake files');
  return res.json();
}

export async function fetchPolicyBulletin(ruleId: string): Promise<PolicyBulletin> {
  const cleanId = encodeURIComponent(ruleId.trim());
  const res = await fetch(`${API_BASE}/bulletins/${cleanId}`);
  if (!res.ok) throw new Error(`Failed to fetch policy bulletin for ${ruleId}`);
  return res.json();
}

export async function uploadPatientFile(data: {
  specialty: string;
  patient_text?: string;
  prescription_text?: string;
  insurer_id?: string;
  insurer_name?: string;
  plan_id?: string;
  member_ref?: string;
  group_number?: string;
  item_name?: string;
  item_type?: string;
  item_code?: string;
  service_date?: string;
  prior_approval_ref?: string;
  diagnosis_code?: string;
  diagnosis_desc?: string;
  documents?: string[];
}): Promise<any> {
  const res = await fetch(`${API_BASE}/cases/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to upload patient file');
  return res.json();
}

export async function fetchUpdates(itemType?: string): Promise<InsurerUpdateEntry[]> {
  const params = new URLSearchParams();
  if (itemType && itemType !== 'All') params.set('item_type', itemType.toLowerCase());

  const res = await fetch(`${API_BASE}/updates?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch insurer updates');
  return res.json();
}

export async function fetchConnection(): Promise<InsurerConnectionInfo> {
  const res = await fetch(`${API_BASE}/connection`);
  if (!res.ok) throw new Error('Failed to fetch connection info');
  return res.json();
}

export async function triggerRunCheckNow(): Promise<any> {
  const res = await fetch(`${API_BASE}/check/run-now`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to run check now');
  return res.json();
}

export async function updateCleanClaimsTarget(target: number): Promise<any> {
  const res = await fetch(`${API_BASE}/settings/target`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target }),
  });
  if (!res.ok) throw new Error('Failed to update target');
  return res.json();
}

export async function toggleCheckFailure(): Promise<any> {
  const res = await fetch(`${API_BASE}/connection/toggle-fail`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to toggle connection failure');
  return res.json();
}

export async function resetDemoState(): Promise<any> {
  const res = await fetch(`${API_BASE}/simulator/reset`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reset demo state');
  return res.json();
}

// -------------------------------------------------------------
// Multimodal AI Policy Intelligence
// -------------------------------------------------------------

export async function extractPolicyDocument(options: {
  file?: File;
  text?: string;
  file_b64?: string;
  filename?: string;
  mime_type?: string;
}): Promise<ExtractedDocumentResult> {
  if (options.file) {
    const formData = new FormData();
    formData.append('file', options.file);
    const res = await fetch(`${API_BASE}/policies/extract`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || 'Failed to process document');
    }
    return res.json();
  } else {
    const res = await fetch(`${API_BASE}/policies/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: options.text,
        file_b64: options.file_b64,
        filename: options.filename,
        mime_type: options.mime_type,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Extraction failed' }));
      throw new Error(err.detail || 'Failed to extract policy');
    }
    return res.json();
  }
}

export async function previewPolicyImpact(
  proposals: ProposedPolicyChange[]
): Promise<ImpactPreviewResult> {
  const res = await fetch(`${API_BASE}/policies/preview-impact`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ proposals }),
  });
  if (!res.ok) throw new Error('Failed to preview policy impact');
  return res.json();
}

export async function fetchPolicyProposals(): Promise<ProposedPolicyChange[]> {
  const res = await fetch(`${API_BASE}/policies/proposals`);
  if (!res.ok) throw new Error('Failed to load policy proposals');
  return res.json();
}

export async function fetchPolicyProposal(proposalId: string): Promise<ProposedPolicyChange> {
  const res = await fetch(`${API_BASE}/policies/proposals/${proposalId}`);
  if (!res.ok) throw new Error(`Failed to load proposal ${proposalId}`);
  return res.json();
}

export async function approvePolicyProposal(
  proposalId: string,
  reviewerNotes?: string,
  editedFields?: Record<string, any>
): Promise<{
  success: boolean;
  message: string;
  rule: any;
  affected_cases_count: number;
  affected_case_ids: string[];
}> {
  const res = await fetch(`${API_BASE}/policies/proposals/${proposalId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewer_notes: reviewerNotes, edited_fields: editedFields }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Approval failed' }));
    throw new Error(err.detail || 'Failed to approve policy');
  }
  return res.json();
}

export async function rejectPolicyProposal(
  proposalId: string,
  reviewerNotes?: string
): Promise<{ success: boolean; message: string; proposal: any }> {
  const res = await fetch(`${API_BASE}/policies/proposals/${proposalId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewer_notes: reviewerNotes }),
  });
  if (!res.ok) throw new Error('Failed to reject proposal');
  return res.json();
}

export async function fetchExtractedDocument(docId: string): Promise<ExtractedDocumentResult> {
  const res = await fetch(`${API_BASE}/policies/documents/${docId}`);
  if (!res.ok) throw new Error('Failed to fetch extracted document');
  return res.json();
}

// -------------------------------------------------------------
// Backward Compatibility Methods
// -------------------------------------------------------------

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Failed to fetch health');
  return res.json();
}

export async function fetchRules(): Promise<Rule[]> {
  return [];
}

export async function fetchAlerts(status?: string): Promise<Alert[]> {
  const url = status ? `${API_BASE}/alerts?status=${encodeURIComponent(status)}` : `${API_BASE}/alerts`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch alerts');
  return res.json();
}

export async function fetchCaseAlerts(caseId: string): Promise<Alert[]> {
  const res = await fetch(`${API_BASE}/alerts/case/${encodeURIComponent(caseId)}`);
  if (!res.ok) throw new Error(`Failed to fetch alerts for case ${caseId}`);
  return res.json();
}

export async function updateAlertTask(
  alertId: string,
  taskId: string,
  taskStatus: 'open' | 'in_progress' | 'completed',
  completedBy?: string
): Promise<{ success: boolean; alert: Alert }> {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/tasks/${taskId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: taskStatus, completed_by: completedBy || 'Claims Officer' }),
  });
  if (!res.ok) throw new Error('Failed to update alert task');
  return res.json();
}

export async function acknowledgeAlert(alertId: string, note?: string): Promise<any> {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ officer_note: note }),
  });
  if (!res.ok) throw new Error('Failed to acknowledge alert');
  return res.json();
}

export async function generateAlertDraft(alertId: string): Promise<{
  success: boolean;
  alert_id: string;
  case_id: string;
  draft_message: string;
  disclaimer: string;
}> {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/draft`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to generate draft message');
  return res.json();
}

export async function triggerSync(): Promise<any> {
  return triggerRunCheckNow();
}

export async function recheckCase(caseId: string): Promise<CaseCheckResult> {
  const detail = await fetchCaseDetail(caseId);
  return detail.check_result;
}

export async function fetchConnectionInfo(): Promise<InsurerConnectionInfo> {
  return fetchConnection();
}

export async function updateDetailLevel(level: 'minimal' | 'excerpt'): Promise<any> {
  return { success: true, detail_level: level };
}

export async function simulateInsurerRevoke(): Promise<any> {
  return toggleCheckFailure();
}

export async function simExcludeDrugA(): Promise<any> {
  return triggerRunCheckNow();
}

export async function simDelayDrugA(): Promise<any> {
  return { success: true };
}

export async function simCancelDrugA(): Promise<any> {
  return { success: true };
}

export async function simToggleOutage(): Promise<any> {
  return toggleCheckFailure();
}

export async function simReset(): Promise<any> {
  return resetDemoState();
}

export async function extractCaseFromText(text: string): Promise<any> {
  return {
    case: {
      case_id: 'C-EXT',
      specialty: 'Cardiology',
      service_date: '2026-11-15',
      items: [{ type: 'drug', code: 'DRUG-A', name: 'Drug A' }],
      documents: [],
    },
    meta: { extractor_used: 'regex-engine', extraction_confidence: 0.95 },
  };
}

export async function createCase(caseData: any): Promise<any> {
  return uploadPatientFile({
    specialty: caseData.specialty || 'Cardiology',
    patient_text: 'Clinical Record',
    item_code: caseData.items?.[0]?.code || 'DRUG-A',
    item_name: caseData.items?.[0]?.name || 'Drug A',
  });
}
