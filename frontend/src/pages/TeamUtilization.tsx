import { useQuery } from '@tanstack/react-query'
import { analyticsAPI } from '@/api/services'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts'
import clsx from 'clsx'

const BAND_BADGE: Record<string, string> = {
  underutilized: 'badge-green',
  optimal:       'badge-blue',
  overloaded:    'badge-yellow',
  critical:      'badge-red',
}

export default function TeamUtilization() {
  const { data, isLoading } = useQuery({
    queryKey: ['workload-distribution'],
    queryFn: () => analyticsAPI.workloadDistribution().then(r => r.data.data),
    refetchInterval: 60_000,
  })

  if (isLoading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin h-8 w-8 border-2 border-brand-500 border-t-transparent rounded-full" />
    </div>
  )

  if (!data) return <div className="card text-slate-400 text-center py-12">No data</div>

  // Aggregate by role for radar
  const byRole: Record<string, { total: number; count: number }> = {}
  data.users.forEach((u: any) => {
    const role = u.role || 'Unknown'
    if (!byRole[role]) byRole[role] = { total: 0, count: 0 }
    byRole[role].total += u.utilization_pct
    byRole[role].count += 1
  })
  const radarData = Object.entries(byRole).map(([role, d]) => ({
    role: role.charAt(0).toUpperCase() + role.slice(1, 12),
    pct: Math.round(d.total / d.count),
  }))

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-xl font-bold text-white">Team Utilization</h2>
        <p className="text-sm text-slate-400 mt-1">
          Snapshot: {data.snapshot_date} · {data.total_users} active employees
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Radar by role */}
        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-4">Utilization by Role</h3>
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#2d3148" />
              <PolarAngleAxis dataKey="role" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Radar dataKey="pct" stroke="#6366f1" fill="#6366f1" fillOpacity={0.25} />
              <Tooltip
                contentStyle={{ background: '#1a1d27', border: '1px solid #2d3148', borderRadius: 8, color: '#f1f5f9' }}
                formatter={(val: number) => [`${val}%`, 'Avg Utilization']}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Workload heatmap-like grid */}
        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-4">Employee Workload Overview</h3>
          <div className="grid grid-cols-4 gap-2 max-h-72 overflow-y-auto">
            {data.users.map((u: any) => {
              const pct = u.utilization_pct ?? 0
              const band = u.utilization_band ?? 'underutilized'
              const intensity = Math.min(pct / 100, 1)
              return (
                <div
                  key={u.user_id}
                  title={`${u.user_name}: ${pct.toFixed(0)}%`}
                  className="aspect-square rounded-lg flex flex-col items-center justify-center gap-1 cursor-default transition-transform hover:scale-110"
                  style={{
                    background: band === 'critical' ? `rgba(239,68,68,${0.3 + intensity * 0.5})`
                      : band === 'overloaded' ? `rgba(245,158,11,${0.3 + intensity * 0.4})`
                      : band === 'optimal'    ? `rgba(99,102,241,${0.3 + intensity * 0.3})`
                      : `rgba(16,185,129,${0.2 + intensity * 0.2})`,
                  }}
                >
                  <span className="text-xs font-bold text-white">{pct.toFixed(0)}%</span>
                  <span className="text-[9px] text-white/60 text-center leading-tight px-0.5">
                    {u.user_name.split(' ')[0]}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Detailed table */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-4">Detailed Utilization</h3>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Utilization</th>
                <th>Band</th>
                <th>Allocated</th>
                <th>Capacity</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {data.users.map((u: any) => (
                <tr key={u.user_id}>
                  <td>
                    <p className="font-medium text-white">{u.user_name}</p>
                    <p className="text-xs text-slate-500">{u.role}</p>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="w-20 bg-surface-200 rounded-full h-1.5">
                        <div
                          className={clsx('h-1.5 rounded-full', {
                            'bg-emerald-500': u.utilization_band === 'underutilized',
                            'bg-brand-500':   u.utilization_band === 'optimal',
                            'bg-amber-500':   u.utilization_band === 'overloaded',
                            'bg-red-500':     u.utilization_band === 'critical',
                          })}
                          style={{ width: `${Math.min(u.utilization_pct ?? 0, 100)}%` }}
                        />
                      </div>
                      <span className="text-xs text-white">{(u.utilization_pct ?? 0).toFixed(1)}%</span>
                    </div>
                  </td>
                  <td>
                    <span className={BAND_BADGE[u.utilization_band ?? 'underutilized']}>
                      {(u.utilization_band ?? '').replace('_', ' ')}
                    </span>
                  </td>
                  <td className="text-slate-400">{(u.allocated_hours ?? 0).toFixed(0)}h</td>
                  <td className="text-slate-400">{(u.capacity_hours ?? 80).toFixed(0)}h</td>
                  <td className="text-slate-500 text-xs">{u.snapshot_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
