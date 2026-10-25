import type { CheckReport, Connection, PolicyUpdate, RequestSummary } from './types';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 28000);
  try {
    const response = await fetch(`/api${path}`, { ...options, signal: controller.signal });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(typeof body?.detail === 'string' ? body.detail : 'Could not complete the request.');
    }
    return await response.json();
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('The check timed out. Please check the connection.');
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export const fetchRequests = () => request<RequestSummary[]>('/requests');
export const fetchReport = (id: string) => request<CheckReport>(`/requests/${encodeURIComponent(id)}`);
export const fetchConnection = () => request<Connection>('/connection');
export const fetchUpdates = () => request<PolicyUpdate[]>('/updates');
export function checkDocuments(card: File | null, prescription: File | null) {
  const body = new FormData();
  if (card) body.append('insurance_card', card);
  if (prescription) body.append('prescription', prescription);
  return request<CheckReport>('/requests/check', { method: 'POST', body });
}
