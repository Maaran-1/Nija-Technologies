import { useQuery } from '@tanstack/react-query'
import { analyticsAPI } from '@/api/services'
import clsx from 'clsx'

const BAND_CONFIG: Record<string, { label: string; badge: string; bar: string }> = {
  healthy:      { label: 'Healthy',       badge: 'badge-green',  bar: 'bg-emerald-500' },
  at_risk:      { label: 'At Risk',       badge: 'badge-yellow', bar: 'bg-amber-500'   },
  at_risk_high: { label: 'High Risk',     badge: 'badge-orange', bar: 'bg-orange-500'  },
  critical:     { label: 'Critical',      badge: 'badge-red',    bar: 'bg-red-500'     },
}

function ScoreBar({ score, color }: { score: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-surface-200 rounded-full h-1.5">
        <div className={clsx('h-1.5 rounded-full', color)} style={{ width: `${Math.min(score, 100)}%` }} />
      </div>
      <span className="text-xs text-slate-400 w-8 text-right">{score.toFixed(0)}</span>
    </div>
  )
}

export default function ProjectHealth() {
  const { data, isLoading } = useQuery({
    queryKey: ['portfolio-health'],
    queryFn: () => analyticsAPI.portfolioHealth().then(r => r.data.data),
    refetchInterval: 120_000,
  })

  if (isLoading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin h-8 w-8 border-2 border-brand-500 border-t-transparent rounded-full" />
    </div>
  )

  if (!data) return <div className="card text-slate-400 text-center py-12">No data</div>

  const summary = data.projects.reduce(
    (acc: any, p: any) => {
      const band = p.health_band ?? 'healthy'
      acc[band] = (acc[band] || 0) + 1
      return acc
    },
    {} as Record<string, number>
  )

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-xl font-bold text-white">Project Health</h2>
        <p className="text-sm text-slate-400 mt-1">Portfolio health scores and risk assessment</p>
      </div>

      {/* Summary row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(BAND_CONFIG).map(([band, cfg]) => (
          <div key={band} className="card text-center">
            <p className="text-3xl font-bold text-white">{summary[band] ?? 0}</p>
            <span className={clsx('mt-2', cfg.badge)}>{cfg.label}</span>
          </div>
        ))}
      </div>

      {/* Project table */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-4">
          All Projects ({data.total_projects}) — sorted by health score ↑
        </h3>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Project</th>
                <th>Status</th>
                <th>Health Band</th>
                <th>Overall</th>
                <th>Schedule</th>
                <th>Resource</th>
                <th>Velocity</th>
                <th>End Date</th>
              </tr>
            </thead>
            <tbody>
              {data.projects.map((p: any) => {
                const band = p.health_band ?? 'healthy'
                const cfg = BAND_CONFIG[band] ?? BAND_CONFIG.healthy
                return (
                  <tr key={p.project_id}>
                    <td>
                      <p className="font-medium text-white">{p.project_name}</p>
                      <p className="text-xs text-slate-500">{p.zoho_project_id}</p>
                    </td>
                    <td>
                      <span className="badge-gray capitalize">{p.status}</span>
                    </td>
                    <td><span className={cfg.badge}>{cfg.label}</span></td>
                    <td style={{ minWidth: 140 }}>
                      <ScoreBar score={p.overall_score ?? 0} color={cfg.bar} />
                    </td>
                    <td style={{ minWidth: 120 }}>
                      <ScoreBar score={p.schedule_score ?? 0} color="bg-brand-500" />
                    </td>
                    <td style={{ minWidth: 120 }}>
                      <ScoreBar score={p.resource_score ?? 0} color="bg-emerald-500" />
                    </td>
                    <td style={{ minWidth: 120 }}>
                      <ScoreBar score={p.velocity_score ?? 0} color="bg-amber-500" />
                    </td>
                    <td className="text-slate-400 text-xs">{p.end_date ?? '—'}</td>
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
