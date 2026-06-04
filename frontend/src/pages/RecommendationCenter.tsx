import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { recommendationsAPI } from '@/api/services'
import { CheckCircle, XCircle, Clock, ChevronRight, Zap, TrendingDown, TrendingUp } from 'lucide-react'
import clsx from 'clsx'
import type { Recommendation } from '@/types'

const STATUS_TABS = ['pending', 'approved', 'rejected', 'deferred'] as const

function RecommendationCard({ rec, onApprove, onReject, onDefer, loading }: {
  rec: Recommendation
  onApprove: (id: string) => void
  onReject: (id: string) => void
  onDefer: (id: string) => void
  loading: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const impactColor = (rec.impact_score ?? 0) >= 15 ? 'text-emerald-400' : (rec.impact_score ?? 0) >= 8 ? 'text-amber-400' : 'text-slate-400'
  const confColor  = (rec.confidence_score ?? 0) >= 70 ? 'text-emerald-400' : (rec.confidence_score ?? 0) >= 50 ? 'text-amber-400' : 'text-red-400'

  return (
    <div className="card-hover animate-slide-up">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="badge-blue">{rec.type.replace('_', ' ')}</span>
            <span className={clsx('text-xs font-medium', impactColor)}>
              Impact: {(rec.impact_score ?? 0).toFixed(1)}
            </span>
            <span className={clsx('text-xs font-medium', confColor)}>
              Confidence: {(rec.confidence_score ?? 0).toFixed(0)}%
            </span>
          </div>

          <p className="text-sm font-semibold text-white mb-1">
            {rec.task_title ?? 'Unspecified task'}
            {rec.task_estimated_hours && (
              <span className="text-slate-500 font-normal ml-1">({rec.task_estimated_hours}h)</span>
            )}
          </p>

          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="text-amber-400 font-medium">{rec.source_user_name}</span>
            <span>({(rec.source_user_current_util ?? 0).toFixed(0)}%)</span>
            <ChevronRight size={12} />
            <span className="text-emerald-400 font-medium">{rec.target_user_name}</span>
            <span>({(rec.target_user_current_util ?? 0).toFixed(0)}%)</span>
          </div>

          {/* Impact visualization */}
          <div className="flex items-center gap-4 mt-3 text-xs">
            <div className="flex items-center gap-1 text-slate-400">
              <TrendingDown size={12} className="text-emerald-400" />
              <span>{rec.source_user_name?.split(' ')[0]}: </span>
              <span className="text-white font-medium">{(rec.projected_source_util ?? 0).toFixed(0)}%</span>
            </div>
            <div className="flex items-center gap-1 text-slate-400">
              <TrendingUp size={12} className="text-brand-400" />
              <span>{rec.target_user_name?.split(' ')[0]}: </span>
              <span className="text-white font-medium">{(rec.projected_target_util ?? 0).toFixed(0)}%</span>
            </div>
          </div>
        </div>

        {rec.status === 'pending' && (
          <div className="flex flex-col gap-2 flex-shrink-0">
            <button onClick={() => onApprove(rec.id)} disabled={loading} className="btn-primary text-xs px-3 py-1.5">
              <CheckCircle size={12} /> Approve
            </button>
            <button onClick={() => onReject(rec.id)} disabled={loading} className="btn-danger text-xs px-3 py-1.5">
              <XCircle size={12} /> Reject
            </button>
            <button onClick={() => onDefer(rec.id)} disabled={loading} className="btn-ghost text-xs px-3 py-1.5">
              <Clock size={12} /> Defer
            </button>
          </div>
        )}
      </div>

      {/* Rationale toggle */}
      {rec.rationale && (
        <div className="mt-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-brand-400 hover:text-brand-300 transition-colors flex items-center gap-1"
          >
            <Zap size={10} /> {expanded ? 'Hide' : 'Show'} AI rationale
          </button>
          {expanded && (
            <p className="mt-2 text-xs text-slate-400 bg-surface-100 rounded-lg p-3 leading-relaxed animate-fade-in">
              {rec.rationale}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default function RecommendationCenter() {
  const [activeTab, setActiveTab] = useState<typeof STATUS_TABS[number]>('pending')
  const [page, setPage] = useState(1)
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['recommendations', activeTab, page],
    queryFn: () => recommendationsAPI.list({ status: activeTab, page, page_size: 20 }).then(r => r.data),
  })

  const approveMutation = useMutation({
    mutationFn: (id: string) => recommendationsAPI.approve(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['recommendations'] }),
  })
  const rejectMutation = useMutation({
    mutationFn: (id: string) => recommendationsAPI.reject(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['recommendations'] }),
  })
  const deferMutation = useMutation({
    mutationFn: (id: string) => recommendationsAPI.defer(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['recommendations'] }),
  })

  const mutating = approveMutation.isPending || rejectMutation.isPending || deferMutation.isPending

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Recommendation Center</h2>
          <p className="text-sm text-slate-400 mt-1">AI-generated task redistribution insights</p>
        </div>
        <button
          onClick={() => recommendationsAPI.generate().then(() => qc.invalidateQueries({ queryKey: ['recommendations'] }))}
          className="btn-primary text-xs"
        >
          <Zap size={12} /> Generate New
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-50 p-1 rounded-xl border border-surface-200 w-fit">
        {STATUS_TABS.map(tab => (
          <button
            key={tab}
            onClick={() => { setActiveTab(tab); setPage(1) }}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium transition-all duration-150 capitalize',
              activeTab === tab
                ? 'bg-brand-600 text-white shadow-glow'
                : 'text-slate-400 hover:text-white'
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin h-8 w-8 border-2 border-brand-500 border-t-transparent rounded-full" />
        </div>
      ) : data?.data.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-slate-400">No {activeTab} recommendations</p>
        </div>
      ) : (
        <div className="space-y-4">
          {data?.data.map(rec => (
            <RecommendationCard
              key={rec.id}
              rec={rec}
              loading={mutating}
              onApprove={id => approveMutation.mutate(id)}
              onReject={id => rejectMutation.mutate(id)}
              onDefer={id => deferMutation.mutate(id)}
            />
          ))}

          {/* Pagination */}
          {data?.meta.total_pages && data.meta.total_pages > 1 && (
            <div className="flex justify-center gap-2 pt-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-ghost text-xs">← Prev</button>
              <span className="text-xs text-slate-400 self-center">Page {page} of {data.meta.total_pages}</span>
              <button onClick={() => setPage(p => p + 1)} disabled={page >= (data?.meta.total_pages ?? 1)} className="btn-ghost text-xs">Next →</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
