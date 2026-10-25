export type Page = 'check' | 'requests' | 'connection' | 'updates';
export type ResultStatus = 'Ready' | 'Missing information' | 'Coverage alert' | 'Accepted' | 'Policy mismatch' | 'Needs policy review';
export interface RequestSummary {
  request_id: string;
  insurer_name: string | null;
  treatment_name: string | null;
  submitted_at: string;
  status: ResultStatus;
}
export interface PolicySource {
  url: string;
  title: string;
  insurer_name: string;
  treatment_name: string;
  effective_date: string | null;
  excerpt: string;
  checked_at: string;
}
export interface CheckReport extends RequestSummary {
  message: string;
  coverage_note: string;
  physician_note: string;
  sources: PolicySource[];
  policy_findings?: { outcome: 'matched' | 'not_matched' | 'unknown' | 'upcoming'; policy_title: string; policy_id: string | null; source_url: string; reason: string }[];
  documents: { type: string; filename: string | null; information: Record<string, string> }[];
}
export interface Connection {
  status: string;
  database_name: string;
  access_mode: string;
  permission: string;
  description: string;
}
export interface PolicyUpdate {
  title: string;
  insurer_name: string;
  treatment_name: string;
  effective_date: string;
  description: string;
  source_url: string;
  checked_at: string;
}
