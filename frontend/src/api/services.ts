import api from './client'
import type { APIResponse, ExecutiveDashboard, TeamUtilizationOverview, Recommendation, Project, User } from '@/types'

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authAPI = {
  login: (email: string, password: string) =>
    api.post<APIResponse<{ access_token: string; refresh_token: string; token_type: string; expires_in: number }>>('/auth/login', { email, password }),
  me: () => api.get<APIResponse<any>>('/auth/me'),
  logout: () => api.post('/auth/logout'),
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export const analyticsAPI = {
  dashboard: () => api.get<APIResponse<ExecutiveDashboard>>('/analytics/dashboard'),
  portfolioHealth: () => api.get<APIResponse<{ total_projects: number; projects: any[] }>>('/analytics/portfolio-health'),
  teamHealth: () => api.get<APIResponse<any>>('/analytics/team-health'),
  workloadDistribution: () => api.get<APIResponse<any>>('/analytics/workload-distribution'),
}

// ── Users ─────────────────────────────────────────────────────────────────────
export const usersAPI = {
  list: (params?: { page?: number; page_size?: number; is_active?: boolean; role?: string }) =>
    api.get<APIResponse<User[]>>('/users', { params }),
  get: (id: string) => api.get<APIResponse<User>>(`/users/${id}`),
  updateCapacity: (id: string, capacity_hours_per_week: number) =>
    api.patch<APIResponse<User>>(`/users/${id}/capacity`, { capacity_hours_per_week }),
  availability: (id: string, forecast_days?: number) =>
    api.get<APIResponse<any>>(`/users/${id}/availability`, { params: { forecast_days } }),
}

// ── Projects ──────────────────────────────────────────────────────────────────
export const projectsAPI = {
  list: (params?: { page?: number; page_size?: number; status?: string }) =>
    api.get<APIResponse<Project[]>>('/projects', { params }),
  get: (id: string) => api.get<APIResponse<Project>>(`/projects/${id}`),
  tasks: (id: string, params?: { page?: number; status?: string }) =>
    api.get<APIResponse<any[]>>(`/projects/${id}/tasks`, { params }),
  milestones: (id: string) => api.get<APIResponse<any[]>>(`/projects/${id}/milestones`),
  score: (id: string) => api.post<APIResponse<any>>(`/projects/${id}/score`),
}

// ── Utilization ───────────────────────────────────────────────────────────────
export const utilizationAPI = {
  team: () => api.get<APIResponse<TeamUtilizationOverview>>('/utilization/team'),
  user: (id: string, weeks_back?: number) =>
    api.get<APIResponse<any>>(`/utilization/user/${id}`, { params: { weeks_back } }),
  recompute: () => api.post<APIResponse<any>>('/utilization/recompute'),
}

// ── Recommendations ───────────────────────────────────────────────────────────
export const recommendationsAPI = {
  list: (params?: { page?: number; status?: string; type?: string }) =>
    api.get<APIResponse<Recommendation[]>>('/recommendations', { params }),
  get: (id: string) => api.get<APIResponse<Recommendation>>(`/recommendations/${id}`),
  approve: (id: string) => api.post<APIResponse<Recommendation>>(`/recommendations/${id}/approve`),
  reject: (id: string) => api.post<APIResponse<Recommendation>>(`/recommendations/${id}/reject`),
  defer: (id: string, reason?: string) =>
    api.post<APIResponse<Recommendation>>(`/recommendations/${id}/defer`, { reason }),
  generate: () => api.post<APIResponse<any>>('/recommendations/generate'),
}

// ── Sync ──────────────────────────────────────────────────────────────────────
export const syncAPI = {
  status: () => api.get<APIResponse<any[]>>('/sync/status'),
  triggerFull: () => api.post<APIResponse<any>>('/sync/full'),
  triggerIncremental: () => api.post<APIResponse<any>>('/sync/incremental'),
}
