import {
  Case,
  CaseDetailResponse,
  InsurerUpdateEntry,
  Alert,
  IntakeAnalysisResult,
  ReviewedIntakeClaim,
  PolicyBulletin,
  ExtractedDocumentResult,
  ProposedPolicyChange,
  ImpactPreviewResult,
  OfficialPolicySource,
  SourceCheckHistory,
} from './types';

const API_BASE = '/api';

async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  headers.set('X-Synthetic-Data', 'true');
  const token = sessionStorage.getItem('coverageguard-reviewer-token');
  if (token) headers.set('X-Reviewer-Token', token);
  return fetch(input, { ...init, headers });
}

// -------------------------------------------------------------
// New Clean Specification API Methods
// -------------------------------------------------------------

export async function fetchCases(status?: string, specialty?: string): Promise<Case[]> {
  const params = new URLSearchParams();
  if (status && status !== 'All') params.set('status', status);
  if (specialty && specialty !== 'All') params.set('specialty', specialty);

  const res = await apiFetch(`${API_BASE}/cases?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch cases');
  return res.json();
}

export async function fetchCaseDetail(caseId: string): Promise<CaseDetailResponse> {
  const res = await apiFetch(`${API_BASE}/cases/${caseId}`);
  if (!res.ok) throw new Error(`Failed to fetch case detail for ${caseId}`);
  return res.json();
}

export async function analyzeIntake(data: {
  policy_environment?: "auto" | "official" | "demo";
  reviewed_claim?: Partial<ReviewedIntakeClaim>;
  sample_id?: string;
  card_image_b64?: string;
  card_text?: string;
  clinical_doc_b64?: string;
  clinical_text?: string;
  selected_insurer_id?: string;
  selected_insurer_name?: string;
  selected_plan_id?: string;
  refresh_sources?: boolean;
}): Promise<IntakeAnalysisResult> {
  const res = await apiFetch(`${API_BASE}/intake/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) { const error = await res.json(); throw new Error(typeof error.detail === 'string' ? error.detail : 'Invalid intake fields. Please check your entries.'); }
  return res.json();
}

export async function fetchPolicyBulletin(ruleId: string): Promise<PolicyBulletin> {
  const cleanId = encodeURIComponent(ruleId.trim());
  const res = await apiFetch(`${API_BASE}/bulletins/${cleanId}`);
  if (!res.ok) throw new Error(`Failed to fetch policy bulletin for ${ruleId}`);
  return res.json();
}

export async function uploadPatientFile(data: {
  specialty: string;
  policy_environment?: string;
  jurisdiction?: string;
  code_system?: string;
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
  items?: ReviewedIntakeClaim["items"];
}): Promise<any> {
  const res = await apiFetch(`${API_BASE}/cases/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) { const error = await res.json(); throw new Error(typeof error.detail === 'string' ? error.detail : 'Invalid claim fields. Please check your entries.'); }
  return res.json();
}

export async function clearUploadedClaims(): Promise<{ removed: number }> {
  const res = await apiFetch(`${API_BASE}/claims/uploads`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Unable to clear uploaded claims.');
  return res.json();
}

export async function fetchUpdates(itemType?: string): Promise<InsurerUpdateEntry[]> {
  const params = new URLSearchParams();
  if (itemType && itemType !== 'All') params.set('item_type', itemType.toLowerCase());

  const res = await apiFetch(`${API_BASE}/updates?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch insurer updates');
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
    const res = await apiFetch(`${API_BASE}/policies/extract`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || 'Failed to process document');
    }
    return res.json();
  } else {
    const res = await apiFetch(`${API_BASE}/policies/extract`, {
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
  const res = await apiFetch(`${API_BASE}/policies/preview-impact`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ proposals }),
  });
  if (!res.ok) throw new Error('Failed to preview policy impact');
  return res.json();
}

export async function fetchPolicyProposals(): Promise<ProposedPolicyChange[]> {
  const res = await apiFetch(`${API_BASE}/policies/proposals`);
  if (!res.ok) throw new Error('Failed to load policy proposals');
  return res.json();
}

export async function fetchPolicyProposal(proposalId: string): Promise<ProposedPolicyChange> {
  const res = await apiFetch(`${API_BASE}/policies/proposals/${proposalId}`);
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
  const res = await apiFetch(`${API_BASE}/policies/proposals/${proposalId}/approve`, {
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
  const res = await apiFetch(`${API_BASE}/policies/proposals/${proposalId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewer_notes: reviewerNotes }),
  });
  if (!res.ok) throw new Error('Failed to reject proposal');
  return res.json();
}

export async function fetchExtractedDocument(docId: string): Promise<ExtractedDocumentResult> {
  const res = await apiFetch(`${API_BASE}/policies/documents/${docId}`);
  if (!res.ok) throw new Error('Failed to fetch extracted document');
  return res.json();
}

// -------------------------------------------------------------
// Alerts
// -------------------------------------------------------------

export async function fetchAlerts(status?: string): Promise<Alert[]> {
  const url = status ? `${API_BASE}/alerts?status=${encodeURIComponent(status)}` : `${API_BASE}/alerts`;
  const res = await apiFetch(url);
  if (!res.ok) throw new Error('Failed to fetch alerts');
  return res.json();
}

export async function fetchCaseAlerts(caseId: string): Promise<Alert[]> {
  const res = await apiFetch(`${API_BASE}/alerts/case/${encodeURIComponent(caseId)}`);
  if (!res.ok) throw new Error(`Failed to fetch alerts for case ${caseId}`);
  return res.json();
}

export async function updateAlertTask(
  alertId: string,
  taskId: string,
  taskStatus: 'open' | 'in_progress' | 'completed',
  completedBy?: string
): Promise<{ success: boolean; alert: Alert }> {
  const res = await apiFetch(`${API_BASE}/alerts/${alertId}/tasks/${taskId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: taskStatus, completed_by: completedBy || 'Claims Officer' }),
  });
  if (!res.ok) throw new Error('Failed to update alert task');
  return res.json();
}

// -------------------------------------------------------------
// Official External Policy Sources & Demo Mode (Feature 8)
// -------------------------------------------------------------

export async function fetchOfficialSources(): Promise<OfficialPolicySource[]> {
  const res = await apiFetch(`${API_BASE}/sources`);
  if (!res.ok) throw new Error('Failed to fetch official policy sources');
  return res.json();
}

export async function checkOfficialSource(sourceId?: string): Promise<SourceCheckHistory> {
  const res = await apiFetch(`${API_BASE}/sources/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_id: sourceId }),
  });
  if (!res.ok) throw new Error('Failed to check official policy source');
  return res.json();
}

export async function fetchSourcesStatus(): Promise<{
  total_sources: number;
  connected_sources: number;
  sources: OfficialPolicySource[];
  latest_check?: SourceCheckHistory | null;
  is_real_external_connection: boolean;
}> {
  const res = await apiFetch(`${API_BASE}/sources/status`);
  if (!res.ok) throw new Error('Failed to fetch sources status');
  return res.json();
}

export async function fetchDemoMode(): Promise<{ demo_mode: boolean }> {
  const res = await apiFetch(`${API_BASE}/settings/demo-mode`);
  if (!res.ok) throw new Error('Failed to fetch demo mode setting');
  return res.json();
}

export async function setDemoMode(demoMode: boolean): Promise<{ success: boolean; demo_mode: boolean }> {
  const res = await apiFetch(`${API_BASE}/settings/demo-mode`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ demo_mode: demoMode }),
  });
  if (!res.ok) throw new Error('Failed to update demo mode');
  return res.json();
}


export async function workflowRequest(path: string, body?: unknown): Promise<any> {
  const res = await apiFetch(`${API_BASE}${path}`, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail));
  }
  return res.json();
}
