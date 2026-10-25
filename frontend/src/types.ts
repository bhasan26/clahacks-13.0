export type CaseStatusType = 'Approved' | 'Needs attention' | 'Missing or wrong info';

export type ItemResultType =
  | 'Covered'
  | 'Not covered'
  | 'Prior approval needed'
  | 'Document missing'
  | 'Value wrong'
  | 'No rule found, verify with the insurer';

export type RuleCategory = 'drug' | 'procedure' | 'service' | 'required_document' | 'prior_approval' | 'document' | 'approval';
export type RuleEffect = 'covered' | 'excluded' | 'requires_prior_approval' | 'requires_documents';
export type RuleStatus = 'announced' | 'effective' | 'delayed' | 'cancelled' | 'superseded';

export interface Target {
  type: string;
  code: string;
  name?: string;
}

export interface Rule {
  rule_id: string;
  version: number;
  insurer_id: string;
  plan_ids: string[];
  category: RuleCategory;
  target: Target;
  effect: RuleEffect;
  conditions?: Record<string, any>;
  status: RuleStatus;
  effective_from: string;
  effective_to?: string | null;
  source_ref: string;
  received_at: string;
}

export interface CaseItem {
  type: string;
  code: string;
  name?: string;
  quantity?: number;
}

export interface Diagnosis {
  code: string;
  description?: string;
}

export interface ItemVerdict {
  item: CaseItem;
  result: ItemResultType;
  verdict?: string;
  severity?: string;
  rule_id?: string;
  rule_version?: number;
  effective_date?: string;
  effective_from?: string;
  source_ref?: string;
  explanation?: string;
  plain_sentence: string;
  rule_reference: string;
  what_to_do: string;
  suggested_officer_action?: string;
  full_issue_text: string;
  source_title?: string;
  source_url?: string;
  official_reference_url?: string;
  why_not_approved?: string;
  bulletin_summary?: string;
  action_guidance?: string[];
}

export interface PolicyBulletin {
  rule_id: string;
  title: string;
  insurer_name: string;
  effective_date: string;
  last_reviewed: string;
  status: string;
  policy_type: string;
  summary: string;
  coverage_criteria: string[];
  denial_risk: string;
  official_reference_url?: string;
}

export interface IntakeAnalysisResult {
  policy_environment?: string;
  success: boolean;
  card: {
    insurer_name: string;
    insurer_id: string;
    member_ref: string;
    group_number?: string;
    plan_id: string;
    plan_name: string;
    copay?: string;
    confidence?: number;
  };
  clinical: {
    patient_name?: string;
    specialty: string;
    service_date: string;
    diagnosis_code: string;
    diagnosis_desc: string;
    items: Array<{ type: string; code: string; name: string; quantity?: number }>;
    documents: string[];
    prior_approval_ref?: string | null;
    confidence?: number;
  };
  check_result: CaseCheckResult;
  bulletin?: PolicyBulletin | null;
}

export interface Case {
  case_id: string;
  insurer_id?: string;
  insurer_name?: string;
  plan_id?: string;
  member_ref: string;
  group_number?: string;
  specialty: string;
  status: CaseStatusType;
  items_count: number;
  service_date: string;
  visit_type?: string;
  diagnoses?: Diagnosis[];
  items: CaseItem[];
  documents?: string[];
  prior_approval_ref?: string | null;
  created_at?: string;
  updated_at?: string;
}

export type CaseOverallStatus = 'clear' | 'needs_attention' | 'cannot_assess';

export interface CaseCheckResult {
  case_id: string;
  specialty: string;
  status: CaseStatusType;
  overall_status?: CaseOverallStatus;
  items_count: number;
  results: ItemVerdict[];
  governing_date?: string;
  checked_at: string;
}

export interface CaseSummary {
  case: Case;
  overall_status: CaseOverallStatus;
  items_count: number;
  findings_count: number;
}

export interface CaseDetailResponse {
  case: Case;
  check_result: CaseCheckResult;
  alerts?: Alert[];
}

export interface AlertChange {
  from_version?: number;
  to_version: number;
  change_type?: string;
  details?: string;
}

export interface AlertTask {
  task_id: string;
  title: string;
  status: 'open' | 'in_progress' | 'completed';
  completed_by?: string | null;
  completed_at?: string | null;
}

export interface Alert {
  alert_id: string;
  case_id: string;
  item_code: string;
  rule_id: string;
  change: AlertChange;
  status: 'open' | 'superseded' | 'closed';
  supersedes?: string | null;
  closed_reason?: string | null;
  created_at: string;
  headline?: string;
  explanation?: string;
  suggested_action?: string;
  acknowledged: boolean;
  officer_note?: string;
  evidence_quote?: string | null;
  effective_date?: string | null;
  source_document?: string | null;
  tasks?: AlertTask[];
  draft_message?: string | null;
}

export interface InsurerUpdateEntry {
  update_id: string;
  headline: string;
  item_type: 'drug' | 'procedure' | 'document' | 'approval';
  effective_date: string;
  status: 'Announced' | 'Effective' | 'Delayed' | 'Cancelled';
  affected_cases_count: number;
  affected_case_ids: string[];
  rule_id: string;
  rule_version: number;
  published_at: string;
}

export interface HealthStatus {
  status: 'healthy' | 'warning';
  feed_connected: boolean;
  last_sync_time: string;
  age_seconds: number;
  is_stale: boolean;
  stale_threshold_seconds: number;
  total_rules: number;
  total_cases: number;
  open_alerts: number;
}

export interface AuditEntry {
  entry_id: string;
  timestamp: string;
  actor: string;
  action: string;
  details: Record<string, any>;
}

export type UserRole = 'employee' | 'admin';

export interface InsurerPermissionItem {
  permission: string;
  status: 'Allowed' | 'Not allowed';
  enforcement_detail: string;
}

export interface InsurerCheckLogEntry {
  check_id: string;
  timestamp: string;
  endpoint: string;
  status_code: number;
  rule_digest: string;
  latency_ms: number;
  summary?: string;
}

export interface InsurerConnectionInfo {
  insurer_name: string;
  status: string;
  access_status: string;
  read_only: boolean;
  last_check_time: string;
  is_check_failed: boolean;
  warning_banner?: string | null;
  // Backward compatibility fields
  insurer_id?: string;
  service_name?: string;
  connection_status?: 'connected' | 'degraded' | 'revoked_by_insurer';
  is_revoked_by_insurer?: boolean;
  token_scope?: string;
  token_held_by?: string;
  allowed_endpoints?: string[];
  last_sync_time?: string;
  rules_count?: number;
  detail_level?: 'minimal' | 'excerpt';
  permissions?: InsurerPermissionItem[];
  recent_checks?: InsurerCheckLogEntry[];
  rate_limit?: {
    max_checks_per_minute: number;
    current_checks_last_minute: number;
    is_throttled: boolean;
  };
  anomaly_status?: {
    anomalies_detected: number;
    status: 'clean' | 'warning';
    anti_scraping_active: boolean;
  };
}

export interface SpecialtyBarData {
  specialty: string;
  total: number;
  approved: number;
  needs_attention: number;
  missing_or_wrong_info: number;
}

export interface DashboardData {
  counts: {
    approved: number;
    needs_attention: number;
    missing_or_wrong_info: number;
    total_checked: number;
  };
  clean_claims: {
    percentage: number;
    approved_count: number;
    total_checked: number;
    target: number;
  };
  specialties: SpecialtyBarData[];
  latest_updates: InsurerUpdateEntry[];
}

export type ReviewStateType = 'pending_review' | 'approved' | 'rejected' | 'needs_correction';
export type PolicyChangeType = 'new_rule' | 'modification' | 'delayed' | 'cancelled';

export interface ProposedPolicyChange {
  requires_billing_articles?: boolean;
  billing_articles_verified?: boolean;
  jurisdictions?: string[];
  code_system?: string | null;
  scope_verified?: boolean;
  extraction_method?: string;

  evidence_verified?: boolean;
  evidence_confirmed_by_reviewer?: boolean;
  proposal_id: string;
  document_id: string;
  document_name: string;
  insurer_id: string | null;
  insurer_name: string | null;
  plan_ids: string[];
  policy_title: string;
  policy_reference?: string | null;
  target_type: 'drug' | 'procedure' | 'service' | null;
  target_code: string | null;
  target_name?: string | null;
  previous_effect?: string | null;
  proposed_effect: 'covered' | 'excluded' | 'requires_prior_approval' | 'requires_documents' | null;
  effective_from?: string | null;
  effective_to?: string | null;
  change_type: PolicyChangeType;
  conditions?: Record<string, any> | null;
  supporting_quote: string;
  source_page: number;
  confidence?: number | null;
  validation_warnings: string[];
  review_state: ReviewStateType;
  reviewer_notes?: string | null;
  created_at: string;
  approved_at?: string | null;
  resulting_rule_id?: string | null;
  resulting_rule_version?: number | null;
}

export interface PolicyDiff {
  proposal_id: string;
  has_existing_rule: boolean;
  existing_rule_id?: string | null;
  existing_rule_version?: number | null;
  previous_effect?: string | null;
  proposed_effect: string;
  previous_effective_from?: string | null;
  proposed_effective_from?: string | null;
  is_delay: boolean;
  is_cancellation: boolean;
  diff_summary: string;
  change_category: string;
}

export interface ImpactCaseItem {
  case_id: string;
  member_ref: string;
  specialty: string;
  service_date: string;
  item_code: string;
  item_name: string;
  previous_verdict: string;
  simulated_verdict: string;
  reason: string;
  supporting_quote?: string | null;
  action_steps: string[];
}

export interface ImpactPreviewResult {
  total_cases_checked: number;
  affected_cases: number;
  new_risks: number;
  unchanged_cases: number;
  cases: ImpactCaseItem[];
  simulation_timestamp: string;
  is_demo_mode?: boolean;
  notice?: string | null;
}

export interface DocumentPageInfo {
  page: number;
  text: string;
  preview_image?: string | null;
  is_scanned: boolean;
  spans?: Array<{ word: string; bbox: number[] }>;
}

export interface ExtractedDocumentResult {
  document_id: string;
  filename: string;
  file_type: string;
  page_count: number;
  pages_text: DocumentPageInfo[];
  raw_text: string;
  proposals: ProposedPolicyChange[];
  diffs: PolicyDiff[];
  impact_preview?: ImpactPreviewResult | null;
  extracted_at: string;
  extraction_method?: string;
  extraction_error?: string | null;
  warnings?: string[];
}

export interface OfficialPolicySource {
  source_id: string;
  name: string;
  insurer_name: string;
  official_url: string;
  policy_scope: string;
  last_checked_at?: string | null;
  last_changed_at?: string | null;
  content_hash?: string | null;
  status: 'active' | 'connected' | 'checking' | 'unchanged' | 'change_detected' | 'error' | 'fetched' | 'processing' | 'pending_review' | 'extraction_failed' | 'source_unavailable' | 'disabled';
  latest_document_title?: string | null;
  pending_proposal_ids: string[];
  error_message?: string | null;
  is_real_external_source: boolean;
  source_type: string;
}

export interface SourceCheckHistory {
  check_id: string;
  source_id: string;
  source_name?: string | null;
  checked_at: string;
  status: string;
  content_hash?: string | null;
  changed: boolean;
  summary: string;
  proposals_created: string[];
  affected_claims_count: number;
  error_message?: string | null;
}
