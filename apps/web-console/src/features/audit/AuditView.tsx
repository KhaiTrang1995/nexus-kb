import { useState, useEffect, useCallback } from 'react'
import { authHeaders } from '../../lib/auth'

interface AuditRecord {
  id: string
  actor_id: string
  action: string
  status: string
  details: Record<string, unknown>
  created_at: string | null
}

const ACTION_COLORS: Record<string, string> = {
  INGEST_START:    'bg-blue-500/20 text-blue-300 border-blue-500/30',
  INGEST_FINISH:   'bg-blue-400/20 text-blue-200 border-blue-400/30',
  DOCUMENT_READ:   'bg-sky-500/20 text-sky-300 border-sky-500/30',
  CHUNK_GENERATED: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
  SEARCH_QUERY:    'bg-purple-500/20 text-purple-300 border-purple-500/30',
  ITEM_REVIEW:     'bg-green-500/20 text-green-300 border-green-500/30',
  GRAPH_WRITE:     'bg-amber-500/20 text-amber-300 border-amber-500/30',
}

const ACTION_TYPES = [
  'ALL',
  'INGEST_START', 'INGEST_FINISH', 'DOCUMENT_READ', 'CHUNK_GENERATED',
  'SEARCH_QUERY', 'ITEM_REVIEW', 'GRAPH_WRITE',
]

const PAGE_SIZE = 20

function ActionPill({ action }: { action: string }) {
  const cls = ACTION_COLORS[action] ?? 'bg-kb-primary/10 text-kb-muted border-kb-primary/20'
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${cls}`}>
      {action}
    </span>
  )
}

function relativeTime(iso: string | null): string {
  if (!iso) return '--'
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return new Date(iso).toLocaleDateString()
}

export default function AuditView({
  canAdvanced,
}: {
  canAdvanced: boolean
}) {
  const [records, setRecords] = useState<AuditRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [actionFilter, setActionFilter] = useState('ALL')
  const [actorFilter, setActorFilter] = useState('')
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)

  const fetchAudit = useCallback(async (pageOffset: number) => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE + 1),
      offset: String(pageOffset),
    })
    if (actionFilter !== 'ALL') params.set('action_filter', actionFilter)
    if (actorFilter.trim()) params.set('actor_filter', actorFilter.trim())

    try {
      const res = await fetch(`/api/v1/audit?${params}`, { headers: authHeaders() })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: AuditRecord[] = await res.json()
      setHasMore(data.length > PAGE_SIZE)
      setRecords(data.slice(0, PAGE_SIZE))
      setOffset(pageOffset)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load audit log')
    } finally {
      setLoading(false)
    }
  }, [actionFilter, actorFilter])

  useEffect(() => {
    fetchAudit(0)
  }, [fetchAudit])

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-semibold">Audit Log</h1>
        <button
          onClick={() => fetchAudit(offset)}
          disabled={loading}
          className="kb-btn border border-kb-primary/30 text-xs px-2 py-1"
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>
      <p className="text-kb-muted text-xs mb-4">
        Immutable events.
        {!canAdvanced && (
          <span className="ml-2 text-amber-400/70">(Auditor role enables actor filtering)</span>
        )}
      </p>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <div>
          <label className="text-xs text-kb-muted block mb-1">Action type</label>
          <div className="flex flex-wrap gap-1">
            {ACTION_TYPES.map(a => (
              <button
                key={a}
                onClick={() => setActionFilter(a)}
                className={`text-xs px-2 py-0.5 rounded border ${
                  actionFilter === a
                    ? 'border-kb-primary text-kb-primary'
                    : 'border-kb-primary/20 text-kb-muted hover:border-kb-primary/40'
                }`}
              >
                {a === 'ALL' ? 'All' : a.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        {canAdvanced && (
          <div>
            <label className="text-xs text-kb-muted block mb-1">Actor</label>
            <input
              value={actorFilter}
              onChange={e => setActorFilter(e.target.value)}
              placeholder="filter by actor..."
              className="bg-kb-dark border border-kb-primary/30 rounded px-2 py-1 text-xs w-40 focus:outline-none focus:border-kb-primary"
            />
          </div>
        )}
      </div>

      {error && (
        <div className="mb-3 text-red-400 text-sm border border-red-400/30 rounded px-3 py-2">
          {error}
          <button onClick={() => fetchAudit(0)} className="ml-2 underline text-xs">Retry</button>
        </div>
      )}

      {/* Table */}
      <div className="kb-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-kb-primary/20 text-xs text-kb-muted">
              <th className="text-left px-3 py-2 w-24">Time</th>
              <th className="text-left px-3 py-2 w-28">Actor</th>
              <th className="text-left px-3 py-2">Action</th>
              <th className="text-left px-3 py-2 w-20">Status</th>
              <th className="px-3 py-2 w-6"></th>
            </tr>
          </thead>
          <tbody>
            {loading && records.length === 0 && (
              <tr>
                <td colSpan={5} className="text-center text-kb-muted py-8 text-sm">Loading...</td>
              </tr>
            )}
            {!loading && records.length === 0 && (
              <tr>
                <td colSpan={5} className="text-center text-kb-muted py-8 text-sm">
                  No audit events found.
                  {actionFilter !== 'ALL' && ' Try "All" filter.'}
                </td>
              </tr>
            )}
            {records.map(rec => (
              <tr
                key={rec.id}
                onClick={() => setExpanded(expanded === rec.id ? null : rec.id)}
                className="border-b border-kb-primary/10 hover:bg-white/[0.02] cursor-pointer"
              >
                <td className="px-3 py-2 text-xs text-kb-muted whitespace-nowrap">
                  {relativeTime(rec.created_at)}
                </td>
                <td className="px-3 py-2 text-xs font-mono truncate max-w-[7rem]" title={rec.actor_id}>
                  {rec.actor_id}
                </td>
                <td className="px-3 py-2">
                  <ActionPill action={rec.action} />
                </td>
                <td className="px-3 py-2">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                    rec.status === 'SUCCESS' || rec.status === 'success'
                      ? 'bg-green-500/15 text-green-300'
                      : 'bg-red-500/15 text-red-300'
                  }`}>
                    {rec.status}
                  </span>
                </td>
                <td className="px-3 py-2 text-kb-muted text-[10px]">
                  {expanded === rec.id ? 'Hide' : 'Show'}
                </td>
              </tr>
            ))}
            {expanded && records.filter(r => r.id === expanded).map(rec => (
              <tr key={`${rec.id}-detail`} className="bg-black/20">
                <td colSpan={5} className="px-4 py-3">
                  <div className="text-[10px] text-kb-muted mb-2 font-mono">
                    {rec.created_at && new Date(rec.created_at).toLocaleString()}
                    <span className="ml-3 opacity-50">{rec.id}</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(rec.details || {}).map(([k, v]) => (
                      <span key={k} className="text-[10px] bg-kb-surface rounded px-2 py-0.5 text-kb-muted border border-kb-primary/10">
                        <span className="text-kb-primary">{k}</span>
                        {': '}
                        {String(v).slice(0, 100)}
                      </span>
                    ))}
                    {Object.keys(rec.details || {}).length === 0 && (
                      <span className="text-[10px] text-kb-muted italic">no details</span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {(offset > 0 || hasMore) && (
        <div className="flex gap-2 mt-3 items-center">
          <button
            onClick={() => fetchAudit(Math.max(0, offset - PAGE_SIZE))}
            disabled={offset === 0 || loading}
            className="kb-btn border border-kb-primary/30 text-xs px-3 py-1 disabled:opacity-40"
          >
            Prev
          </button>
          <span className="text-xs text-kb-muted">Page {Math.floor(offset / PAGE_SIZE) + 1}</span>
          <button
            onClick={() => fetchAudit(offset + PAGE_SIZE)}
            disabled={!hasMore || loading}
            className="kb-btn border border-kb-primary/30 text-xs px-3 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
