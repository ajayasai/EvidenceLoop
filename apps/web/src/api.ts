import type { Applicability, CaseState, Coverage, EffectDirection, EvidenceStatus, OperatorState, Route, SystemStatus } from '../../../contracts/state-types';
export type { Route } from '../../../contracts/state-types';

export type Mode = 'replay' | 'live' | 'manual';
export type StepState = 'planned' | 'done_self_reported' | 'deferred' | 'abandoned' | 'needs_revision';
export type Intent = {
  action_kind: string;
  current_care_relationship: string;
  endorsement: string;
  actor?: string;
  target?: string;
  timing?: string;
};
export interface Session {
  public_demo?: boolean;
  storage_resets_on_restart?: boolean;
  csrf_token: string;
  mode: Mode;
  reviewer: boolean;
  live_available: boolean;
  extraction_available?: boolean;
  alignment_available?: boolean;
  preferred_mode?: 'live' | 'replay';
  extraction_scope?: 'local' | 'remote' | null;
  retention_days: number;
  editor?: boolean;
  clinical_reviewer?: boolean;
  synthetic?: boolean;
  clinical_review?: 'verified_publication' | 'not_performed' | 'unavailable';
  publication_id?: string | null;
  library_status?: 'current' | 'under_review';
}
export interface Example { id: string; title: string; text: string; intent: Intent }
export interface Field {
  value: unknown;
  provenance?: unknown[];
  source_span?: { start: number; end: number };
  [key: string]: unknown;
}
export interface Proposition {
  proposition_id: string;
  intervention?: Field;
  population?: Field;
  comparator?: Field;
  measured_outcome?: Field;
  claimed_clinical_outcome?: Field;
  condition_context?: Field;
  certainty?: Field;
  polarity?: Field;
  timeframe?: Field;
  speaker?: string;
  speech_act?: string;
  [key: string]: unknown;
}
export interface Draft {
  draft_id: string;
  revision: number;
  claim: { propositions: Proposition[]; [key: string]: unknown };
  intent: Record<string, unknown>;
  route: Route;
  reason_codes: string[];
  system_status: SystemStatus;
  mode: Mode;
  confirmed?: boolean;
  snapshot?: {selected_proposition_id: string; confirmed_proposition: Proposition; version_id: string; [key: string]: unknown};
}
export interface Finding {
  operator_id?: string;
  operator_state: OperatorState;
  title?: string;
  explanation?: string;
  claim_facet?: string;
  source_facet?: string;
  [key: string]: unknown;
}
export interface EvidenceItem {
  title?: string;
  source_id?: string;
  source_version_id?: string;
  conclusion_id?: string;
  conclusion?: string;
  text?: string;
  publisher?: string;
  canonical_url?: string;
  passage?: string;
  excerpt?: string;
  review_date?: string;
  [key: string]: unknown;
}
export interface Receipt {
  receipt_id: string;
  case_state: CaseState;
  route: Route;
  coverage: Coverage;
  evidence_status: EvidenceStatus;
  applicability: Applicability;
  effect_direction_by_outcome?: {outcome_id: string; effect_direction: EffectDirection; conclusion_ids: string[]}[];
  system_status: SystemStatus;
  personal_suitability?: string;
  reason_codes: string[];
  evidence: EvidenceItem[];
  operator_findings: Finding[];
  limitations: unknown[];
  action_boundary: unknown;
  mode: Mode;
  extraction_mode?: Mode;
  alignment_mode?: 'extraction_only' | 'live' | 'deterministic_library_rules' | 'not_permitted' | 'not_required' | 'failed';
  snapshot: Record<string, unknown>;
  intent: Record<string, unknown>;
  assessed_at: string;
  synthetic?: boolean;
  clinical_review?: boolean;
  argument_graph?: unknown;
  [key: string]: unknown;
}
export interface Envelope {
  receipt_id: string;
  receipt: Receipt;
  persistence: 'ephemeral' | 'saved';
  current_trust: {state: string; checked_at: string; affected_dependency_ids: string[]};
  current_claim?: {state: 'current' | 'superseded' | 'needs_confirmation'};
  current_comparison?: {state: 'current' | 'unqualified'; reason_codes: string[]; message: string};
}
export interface Preview {preview_id: string; preview_hash: string; text: string; expires_at: string}
export interface SavedStep {
  id: string;
  case_id: string;
  receipt_id: string;
  question: string;
  state: StepState;
  version: number;
  created_at: string;
  check_ins: unknown[];
  current_trust?: Envelope['current_trust'];
  current_claim?: Envelope['current_claim'];
  current_comparison?: Envelope['current_comparison'];
  receipt?: Receipt;
}
export interface CheckInResponse {
  step: SavedStep;
  route: Route;
  feedback: string;
  exercise?: {question: string; choices: unknown[]};
}
export interface ReviewSource {
  source_id: string;
  title: string;
  state?: string;
  trust_state?: string;
  revision?: number;
  [key: string]: unknown;
}
export interface LibrarySource {
  source_version_id: string;
  source_id: string;
  editor_identity: string;
  content_hash: string;
  packet_hash: string;
  payload: Record<string, unknown>;
  imported_at: string;
  state?: string;
  revision?: number;
}
export interface LibraryBrief {
  brief_version_id: string;
  family_id: string;
  editor_identity: string;
  payload: Record<string, unknown>;
  target_hash: string;
  latest_decision: 'approved' | 'changes_requested' | 'rejected' | null;
}
export interface ReviewQueue {
  sources: LibrarySource[];
  briefs: LibraryBrief[];
  publication: {publication_id: string | null; revision: number};
  clinical_enabled: boolean;
  qualified_reviewer_count: number;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}
let csrfToken = '';
export function setCsrfToken(value: string) { csrfToken = value; }

function errorText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(errorText).join('; ');
  if (value && typeof value === 'object') {
    const object = value as Record<string, unknown>;
    if (typeof object.message === 'string') return object.message;
    if (typeof object.msg === 'string') return object.msg;
    if (typeof object.code === 'string') return object.code.replaceAll('_', ' ');
  }
  return 'The request could not be completed. Please try again.';
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set('Content-Type', 'application/json');
  if (options.method && options.method !== 'GET') headers.set('X-CSRF-Token', csrfToken);
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {...options, headers, credentials: 'same-origin'});
  } catch {
    throw new ApiError('The workspace is offline. Your unsaved input is still here. Reconnect and try again.', 0);
  }
  if (response.status === 204) return undefined as T;
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body && typeof body === 'object' && 'error' in body ? body.error : body && typeof body === 'object' && 'detail' in body ? body.detail : body;
    throw new ApiError(errorText(detail), response.status);
  }
  return body as T;
}
export function post<T>(path: string, body: unknown, headers?: HeadersInit) {
  return request<T>(path, {method: 'POST', body: JSON.stringify(body), headers});
}
export async function loadSession() {
  const result = await request<Session>('/session');
  setCsrfToken(result.csrf_token);
  return result;
}
export function fieldText(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (typeof value === 'object') {
    const item = value as Record<string, unknown>;
    if ('surface' in item) return fieldText(item.surface);
    if ('value' in item) return fieldText(item.value);
    if ('text' in item) return fieldText(item.text);
    if ('description' in item) return fieldText(item.description);
    if ('explanation' in item) return fieldText(item.explanation);
  }
  return '';
}
export function humanize(value: string): string {
  return value.replaceAll('_', ' ').replace(/^./, character => character.toUpperCase());
}
export function safeLink(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) ? url.href : undefined;
  } catch { return undefined; }
}
export function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleDateString(undefined, {day: 'numeric', month: 'short', year: 'numeric'});
}
