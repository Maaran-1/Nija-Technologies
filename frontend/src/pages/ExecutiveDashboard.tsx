import { useQuery } from '@tanstack/react-query'
import { analyticsAPI } from '@/api/services'
import { Users, FolderKanban, Lightbulb, AlertTriangle, TrendingUp, Activity } from 'lucide-react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import clsx from 'clsx'

const UTIL_COLORS: Record<string, string> = {
  underutilized: '#10b981',
  optimal:       '#6366f1',
  overloaded:    '#f59e0b',
  critical:      '#ef4444',
}

const HEALTH_COLORS: Record<string, string> = {
  healthy:     '#10b981',
  at_risk:     '#f59e0b',
  at_risk_high:'#f97316',
  critical:    '#ef4444',
}

function StatCard({ label, value, icon: Icon, color, sublabel }: {
  label: string; value: string | number; icon: any; color: string; sublabel?: string
}) {
  return (
    <div className="card-hover group animate-slide-up">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm text-slate-400">{label}</p>
        <div className={clsx('p-2 rounded-lg', color)}>
          <Icon size={16} className="text-white" />
        </div>
      </div>
      <p className="stat-value">{value}</p>
      {sublabel && <p className="text-xs text-slate-500 mt-1">{sublabel}</p>}
    </div>
  )
}

function AlertCard({ label, count, type }: { label: string; count: number; type: 'warning' | 'danger' | 'info' }) {
  const styles = {
    warning: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
    danger:  'bg-red-500/10  border-red-500/30  text-red-400',
    info:    'bg-brand-500/10 border-brand-500/30 text-brand-400',
  }
  return (
    <div className={clsx('flex items-center justify-between p-3 rounded-lg border', styles[type])}>
      <div className="flex items-center gap-2 text-sm">
        <AlertTriangle size={14} />
        {label}
      </div>
      <span className="font-bold text-lg">{count}</span>
    </div>
  )
}

export default function ExecutiveDashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => analyticsAPI.dashboard().then(r => r.data.data),
    refetchInterval: 60_000,
  })

  if (isLoading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin h-8 w-8 border-2 border-brand-500 border-t-transparent rounded-full" />
    </div>
  )

  if (error || !data) return (
    <div className="card text-center text-slate-400 py-12">
      Failed to load dashboard data
    </div>
  )

  const utilDistribution = Object.entries(data.utilization.distribution).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value,
    fill: UTIL_COLORS[name] ?? '#6366f1',
  }))

  const healthDistribution = Object.entries(data.projects.health_distribution).map(([name, value]) => ({
    name: name.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase()),
    value,
    fill: HEALTH_COLORS[name] ?? '#6366f1',
  }))

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-xl font-bold text-white">Executive Dashboard</h2>
        <p className="text-sm text-slate-400 mt-1">Real-time workforce and project health overview</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Employees"
          value={data.utilization.total_users}
          icon={Users}
          color="bg-brand-600"
          sublabel={`${data.utilization.average_pct.toFixed(1)}% avg utilization`}
        />
        <StatCard
          label="Active Projects"
          value={data.projects.total_active}
          icon={FolderKanban}
          color="bg-emerald-600"
          sublabel={`${data.projects.average_health_score.toFixed(1)} avg health score`}
        />
        <StatCard
          label="Pending Recommendations"
          value={data.recommendations.pending_count}
          icon={Lightbulb}
          color="bg-amber-600"
          sublabel="AI-generated insights"
        />
        <StatCard
          label="Burnout Risks"
          value={data.team_health.burnout_risk_count}
          icon={Activity}
          color="bg-red-600"
          sublabel="Sustained overload"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Utilization Breakdown */}
        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingUp size={14} className="text-brand-400" />
            Team Utilization Breakdown
          </h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={utilDistribution} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={3} dataKey="value">
                {utilDistribution.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: '#1a1d27', border: '1px solid #2d3148', borderRadius: 8, color: '#f1f5f9' }}
                formatter={(val: number) => [`${val} employees`, '']}
              />
              <Legend formatter={(val) => <span className="text-slate-400 text-xs">{val}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Project Health Breakdown */}
        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <FolderKanban size={14} className="text-emerald-400" />
            Project Health Distribution
          </h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={healthDistribution} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={3} dataKey="value">
                {healthDistribution.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: '#1a1d27', border: '1px solid #2d3148', borderRadius: 8, color: '#f1f5f9' }}
                formatter={(val: number) => [`${val} projects`, '']}
              />
              <Legend formatter={(val) => <span className="text-slate-400 text-xs">{val}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Team Health Alerts */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
          <AlertTriangle size={14} className="text-amber-400" />
          Team Health Signals
        </h3>
        <div className="space-y-3">
          <AlertCard label="Employees at Burnout Risk" count={data.team_health.burnout_risk_count} type="danger" />
          <AlertCard label="Workload Concentration Issues" count={data.team_health.workload_concentration_count} type="warning" />
          <AlertCard label="Unassigned High-Priority Tasks" count={data.team_health.unassigned_high_priority_count} type="info" />
        </div>
      </div>
    </div>
  )
}
