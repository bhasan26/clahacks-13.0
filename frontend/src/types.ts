export type RuleCategory = 'drug' | 'procedure' | 'service' | 'required_document' | 'prior_approval';
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

export interface Case {
  case_id: string;
  insurer_id: string;
  plan_id: string;
  member_ref: string;
  service_date: string;
  visit_type: string;
  diagnoses: Diagnosis[];
  items: CaseItem[];
  documents: string[];
  prior_approval_ref?: string | null;
  status: 'open' | 'submitted' | 'closed';
  officer_id?: string;
  created_at: string;
  updated_at: string;
}

export type VerdictType = 'covered' | 'excluded' | 'prior_approval_needed' | 'documents_missing' | 'no_rule_found' | 'cannot_assess';
export type SeverityType = 'clear' | 'action_needed' | 'verify' | 'info';

export interface ItemVerdict {
  item: CaseItem;
  verdict: VerdictType;
  severity: SeverityType;
  rule_id?: string;
  rule_version?: number;
  effective_from?: string;
  source_ref?: string;
  explanation: string;
  suggested_officer_action?: string;
}

export type CaseOverallStatus = 'clear' | 'needs_attention' | 'cannot_assess';

export interface CaseCheckResult {
  case_id: string;
  governing_date: string;
  overall_status: CaseOverallStatus;
  results: ItemVerdict[];
  checked_at: string;
}

export interface CaseSummary {
  case: Case;
  overall_status: CaseOverallStatus;
  items_count: number;
  findings_count: number;
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
