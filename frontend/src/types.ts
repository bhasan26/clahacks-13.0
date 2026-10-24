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
