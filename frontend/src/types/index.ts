// ── Auth ──────────────────────────────────────────────────────────────────────
export interface LoginRequest { email: string; password: string }
export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}
export interface PlatformUser {
  id: string
  name: string
  email: string
  role: 'admin' | 'manager' | 'viewer'
  is_active: boolean
  last_login_at: string | null
  created_at: string
}

// ── Users ─────────────────────────────────────────────────────────────────────
export interface User {
  id: string
  zoho_user_id: string
  name: string
  email: string
  role: string | null
  capacity_hours_per_week: number
  is_active: boolean
  synced_at: string | null
  created_at: string
  current_utilization_pct?: number | null
  utilization_band?: string | null
  consecutive_overload_weeks?: number | null
}

// ── Projects ──────────────────────────────────────────────────────────────────
export interface Project {
  id: string
  zoho_project_id: string
  name: string
  status: string
  start_date: string | null
  end_date: string | null
  budget_hours: number | null
  description: string | null
  synced_at: string | null
  created_at: string
  latest_health_score?: number | null
  health_band?: string | null
  risk_level?: string | null
}

export interface Task {
  id: string
  zoho_task_id: string
  project_id: string
  assigned_to: string | null
  title: string
  status: string
  priority: number | null
  estimated_hours: number | null
  actual_hours: number | null
  due_date: string | null
  completed_at: string | null
  tags: string | null
  synced_at: string | null
  created_at: string
}

export interface Milestone {
  id: string
  zoho_milestone_id: string
  project_id: string
  name: string
  due_date: string | null
  is_completed: boolean
  completed_at: string | null
}

// ── Analytics ─────────────────────────────────────────────────────────────────
export interface UtilizationSnapshot {
  id: string
  user_id: string
  snapshot_date: string
  window_weeks: number
  capacity_hours: number | null
  allocated_hours: number | null
  logged_hours: number | null
  utilization_pct: number | null
  utilization_band: string | null
  created_at: string
}

export interface TeamUtilizationOverview {
  total_users: number
  underutilized_count: number
  optimal_count: number
  overloaded_count: number
  critical_count: number
  average_utilization_pct: number
  users: Array<{
    user_id: string
    user_name: string
    user_email: string
    current_utilization_pct: number | null
    utilization_band: string | null
    capacity_hours_per_week: number
    allocated_hours: number | null
    consecutive_overload_weeks: number
  }>
}

// ── Recommendations ───────────────────────────────────────────────────────────
export interface Recommendation {
  id: string
  type: string
  source_user_id: string | null
  source_user_name: string | null
  source_user_current_util: number | null
  target_user_id: string | null
  target_user_name: string | null
  target_user_current_util: number | null
  task_id: string | null
  task_title: string | null
  task_estimated_hours: number | null
  projected_source_util: number | null
  projected_target_util: number | null
  impact_score: number | null
  confidence_score: number | null
  status: string
  rationale: string | null
  reviewed_by: string | null
  reviewed_at: string | null
  created_at: string
}

// ── API Response ──────────────────────────────────────────────────────────────
export interface APIResponse<T> {
  data: T
  meta: {
    page?: number
    page_size?: number
    total?: number
    total_pages?: number
  }
  errors: Array<{ message: string; code: string }>
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export interface ExecutiveDashboard {
  utilization: {
    total_users: number
    average_pct: number
    distribution: Record<string, number>
  }
  projects: {
    total_active: number
    average_health_score: number
    health_distribution: Record<string, number>
  }
  recommendations: {
    pending_count: number
  }
  team_health: {
    burnout_risk_count: number
    workload_concentration_count: number
    unassigned_high_priority_count: number
  }
}
