import { useQuery } from '@tanstack/react-query'
import { utilizationAPI } from '@/api/services'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import clsx from 'clsx'

const BAND_CONFIG: Record<string, { color: string; badge: string; bg: string }> = {
  underutilized: { color: '#10b981', badge: 'badge-green',  bg: 'bg-emerald-500' },
  optimal:       { color: '#6366f1', badge: 'badge-blue',   bg: 'bg-brand-500'   },
  overloaded:    { color: '#f59e0b', badge: 'badge-yellow', bg: 'bg-amber-500'   },
  critical:      { color: '#ef4444', badge: 'badge-red',    bg: 'bg-red-500'     },
}

function UtilBar({ pct }: { pct: number }) {
  const band = pct < 60 ? 'underutilized' : pct <= 85 ? 'optimal' : pct <= 110 ? 'overloaded' : 'critical'
  const cfg = BAND_CONFIG[band]
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 bg-surface-200 rounded-full h-2">
        <div
          className={clsx('h-2 rounded-full transition-all duration-500', cfg.bg)}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-xs font-medium text-slate-300 w-12 text-right">{pct.toFixed(0)}%</span>
    </div>
  )
}

export default function ManagerDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ['team-utilization'],
    queryFn: () => utilizationAPI.team().then(r => r.data.data),
    refetchInterval: 60_000,
  })

  if (isLoading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin h-8 w-8 border-2 border-brand-500 border-t-transparent rounded-full" />
    </div>
  )

  if (!data) return <div className="card text-slate-400 text-center py-12">No data available</div>

  const chartData = data.users.map(u => ({
    name: u.user_name.split(' ')[0],
    pct: u.current_utilization_pct ?? 0,
    band: u.utilization_band ?? 'underutilized',
    fill: BAND_CONFIG[u.utilization_band ?? 'underutilized']?.color ?? '#6366f1',
  })).sort((a, b) => b.pct - a.pct).slice(0, 20)

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-xl font-bold text-white">Manager Dashboard</h2>
        <p className="text-sm text-slate-400 mt-1">Team workload distribution and individual utilization</p>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Team', value: data.total_users, color: 'text-brand-400' },
          { label: 'Underutilized', value: data.underutilized_count, color: 'text-emerald-400' },
          { label: 'Overloaded', value: data.overloaded_count, color: 'text-amber-400' },
          { label: 'Critical', value: data.critical_count, color: 'text-red-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card text-center">
            <p className={clsx('text-3xl font-bold', color)}>{value}</p>
            <p className="text-xs text-slate-400 mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Bar chart */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-4">Utilization by Employee (Top 20)</h3>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 20 }}>
            <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} angle={-35} textAnchor="end" />
            <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} domain={[0, 120]} unit="%" />
            <Tooltip
              contentStyle={{ background: '#1a1d27', border: '1px solid #2d3148', borderRadius: 8, color: '#f1f5f9' }}
              formatter={(val: number) => [`${val.toFixed(1)}%`, 'Utilization']}
            />
            {/* Optimal zone reference */}
            <Bar dataKey="pct" radius={[4, 4, 0, 0]}>
              {chartData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Team table */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-4">Full Team Overview</h3>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Role</th>
                <th>Utilization</th>
                <th>Band</th>
                <th>Overload Weeks</th>
                <th>Allocated Hrs</th>
              </tr>
            </thead>
            <tbody>
              {data.users.map(user => {
                const band = user.utilization_band ?? 'underutilized'
                const cfg = BAND_CONFIG[band]
                return (
                  <tr key={user.user_id}>
                    <td>
                      <div>
                        <p className="font-medium text-white">{user.user_name}</p>
                        <p className="text-xs text-slate-500">{user.user_email}</p>
                      </div>
                    </td>
                    <td className="text-slate-400">{user.user_email}</td>
                    <td style={{ minWidth: 180 }}>
                      <UtilBar pct={user.current_utilization_pct ?? 0} />
                    </td>
                    <td><span className={cfg.badge}>{band.replace('_', ' ')}</span></td>
                    <td className={user.consecutive_overload_weeks > 1 ? 'text-red-400 font-medium' : 'text-slate-400'}>
                      {user.consecutive_overload_weeks}
                    </td>
                    <td className="text-slate-400">{(user.allocated_hours ?? 0).toFixed(0)}h</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
