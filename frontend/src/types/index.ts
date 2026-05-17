// User types
export interface User {
  id: string;
  email: string;
  display_name: string | null;
  role: UserRole;
  status: UserStatus;
  org_id: string;
  settings: Record<string, unknown>;
}

export type UserRole = 'super_admin' | 'org_admin' | 'developer' | 'viewer';
export type UserStatus = 'active' | 'inactive' | 'suspended';

// Session types
export interface Session {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  status: SessionStatus;
  model: string;
  system_prompt: string | null;
  tools: string[];
  settings: Record<string, unknown>;
  thread_id: string | null;
  message_count: number;
  token_usage: TokenUsage;
  created_at: string;
  updated_at: string;
  last_activity_at: string;
}

export type SessionStatus = 'active' | 'paused' | 'terminated' | 'error';

export interface TokenUsage {
  input: number;
  output: number;
  total: number;
}

export interface SessionListResponse {
  items: Session[];
  total: number;
  page: number;
  page_size: number;
}

// Message types
export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  tool_calls?: ToolCall[];
  created_at: string;
}

export type MessageRole = 'user' | 'assistant' | 'system';

export interface ToolCall {
  id: string;
  type: 'function';
  function: {
    name: string;
    arguments: string;
  };
}

export interface ChatMessageResponse {
  id: string;
  role: MessageRole;
  content: string;
  tool_calls: ToolCall[] | null;
  created_at: string;
}

export interface ChatHistoryResponse {
  session_id: string;
  messages: ChatMessageResponse[];
  total: number;
}

// Streaming types
export interface StreamChunk {
  type: 'content' | 'tool_call' | 'tool_result' | 'error' | 'done';
  content?: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: string;
  error?: string;
}

// Task types
export interface Task {
  id: string;
  session_id: string;
  type: TaskType;
  status: TaskStatus;
  prompt: string;
  progress: number;
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export type TaskType = 'sync' | 'async' | 'scheduled' | 'recurring';
export type TaskStatus = 'pending' | 'queued' | 'running' | 'waiting_hitl' | 'completed' | 'failed' | 'cancelled';

// Task Event types
export interface TaskEvent {
  id: string;
  task_id: string;
  type: TaskEventType;
  data: Record<string, unknown>;
  message: string | null;
  created_at: string;
}

export type TaskEventType =
  | 'task_created'
  | 'task_queued'
  | 'task_started'
  | 'planning_started'
  | 'planning_completed'
  | 'step_started'
  | 'step_completed'
  | 'step_failed'
  | 'tool_calling'
  | 'tool_result'
  | 'hitl_required'
  | 'hitl_resolved'
  | 'task_completed'
  | 'task_failed'
  | 'task_cancelled';

// Approval types
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired' | 'escalated' | 'cancelled';
export type ApprovalDecision = 'approve' | 'reject';
export type ApprovalStrategy = 'any' | 'all' | 'majority';

export interface ApprovalRequest {
  id: string;
  task_id: string | null;
  session_id: string;
  thread_id: string | null;
  checkpoint_ns: string | null;
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_input_hash: string;
  risk_level: RiskLevel;
  description: string | null;
  context_summary: string | null;
  approvers: Approver[];
  strategy: ApprovalStrategy;
  min_approvals_required: number;
  status: ApprovalStatus;
  decisions: Decision[];
  approval_count: number;
  rejection_count: number;
  is_expired: boolean;
  requires_more_approvals: boolean;
  requested_at: string;
  expires_at: string;
  decided_at: string | null;
}

export interface Approver {
  user_id: string;
  user_email?: string;
  user_name?: string;
}

export interface Decision {
  user_id: string;
  decision: ApprovalDecision;
  reason: string | null;
  timestamp: string;
}

export interface ApprovalListItem {
  id: string;
  tool_name: string;
  risk_level: RiskLevel;
  status: ApprovalStatus;
  description: string | null;
  approval_count: number;
  rejection_count: number;
  requested_at: string;
  expires_at: string;
  is_expired: boolean;
}

export interface ApprovalListResponse {
  items: ApprovalListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApprovalDecisionRequest {
  decision: ApprovalDecision;
  reason?: string;
  user_id: string;
}

export interface ApprovalDecisionResponse {
  id: string;
  status: ApprovalStatus;
  decisions: Decision[];
  approval_count: number;
  rejection_count: number;
  requires_more_approvals: boolean;
  decided_at: string | null;
}

// Integration types (Forge × DeerFlow)
export interface IntegrationStatus {
  version: string
  models: {
    available: number
    default: string
  }
  features: {
    summarization: boolean
    memory: boolean
    loop_detection: boolean
    tool_search: boolean
    title_generation: boolean
    token_usage: boolean
  }
  database: {
    backend: string
  }
  skills_path: string
}

export interface ModelInfo {
  name: string
  display_name: string
  supports_thinking: boolean
  supports_vision: boolean
}

export interface SkillInfo {
  name: string
  description: string
  is_active: boolean
  has_instructions: boolean
}

export interface MemoryFact {
  content: string
  category: string
  confidence: number
  timestamp: number
}

export interface MCPServerInfo {
  name: string
  enabled: boolean
  type: string
}
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginResponse {
  user: User;
  tokens: TokenResponse;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  display_name?: string;
  org_name?: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

// API Response types
export interface ApiError {
  detail: string;
  status_code?: number;
}

export interface ApiResponse<T> {
  data: T;
  status: number;
  message?: string;
}

// WebSocket/SSE types
export interface SSEEvent {
  type: string;
  data: unknown;
}

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

// UI types
export interface NavItem {
  label: string;
  href: string;
  icon?: string;
}

export type ToastType = 'info' | 'success' | 'warning' | 'error';

export interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
}
