import { useState, useEffect, useCallback } from 'react'
import { authHeaders } from '../../lib/auth'

interface ReviewItem {
  id: string
  run_id: string
  source_path: string
  content: string
  confidence: number
  status: string
  reviewer_id: string | null
  reviewed_at: string | null
  created_at: string | null
}

const PAGE_SIZE = 20

export default function ReviewView({ currentUser }: { currentUser: { id: string; name: string; role: string } | null }) {
  const [queue, setQueue] = useState<ReviewItem[]>([])
  const [loading, setLoading] = useState(false)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [selected, setSelected] = useState<ReviewItem | null>(null)
  const [modifiedContent, setModifiedContent] = useState('')
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  const role = currentUser?.role || ''
  const isReviewer = role === 'Reviewer'

  const fetchQueue = useCallback(async (pageOffset: number) => {
    setLoading(true)
    setFetchError(null)
    try {
      const res = await fetch(
        `/api/v1/review/queue?limit=${PAGE_SIZE + 1}&offset=${pageOffset}`,
        { headers: authHeaders() },
      )
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail || `HTTP ${res.status}`)
      }
      const data: ReviewItem[] = await res.json()
      setHasMore(data.length > PAGE_SIZE)
      setQueue(data.slice(0, PAGE_SIZE))
      setOffset(pageOffset)
    } catch (e: unknown) {
      setFetchError(e instanceof Error ? e.message : 'Failed to load review queue.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchQueue(0)
  }, [fetchQueue])

  const callAction = async (itemId: string, action: 'APPROVE' | 'REJECT' | 'MODIFY') => {
    if (!isReviewer) { setActionError('403: Reviewer role required'); return }
    setActionLoading(true)
    setActionError(null)
    setActionSuccess(null)
    try {
      const res = await fetch('/api/v1/review/action', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          item_id: itemId,
          action,
          ...(action === 'MODIFY' && { modified_content: modifiedContent }),
        }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        if (res.status === 409) throw new Error('Item already finalized.')
        if (res.status === 403) throw new Error('Reviewer role required.')
        throw new Error(body?.detail || `HTTP ${res.status}`)
      }
      setQueue(q => q.filter(i => i.id !== itemId))
      setSelected(null)
      setActionSuccess(
        action === 'APPROVE' ? 'Approved -- chunk added to vector index.'
        : action === 'MODIFY' ? 'Modified and re-indexed.'
        : 'Rejected -- chunk will not be indexed.',
      )
      setTimeout(() => setActionSuccess(null), 4000)
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Action failed.')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-semibold">Review Queue</h1>
        <button
          onClick={() => fetchQueue(offset)}
          disabled={loading}
          className="kb-btn border border-kb-primary/30 text-xs px-2 py-1"
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>
      <p className="text-kb-muted text-xs mb-4">
        Low-confidence chunks routed for human review. Requires Reviewer role.
      </p>

      {!isReviewer && (
        <div className="mb-4 text-amber-400 text-sm border border-amber-400/30 rounded px-3 py-2">
          Switch to "Reviewer" role in the header to enable actions.
        </div>
      )}

      {actionSuccess && (
        <div className="mb-3 text-green-400 text-sm border border-green-400/30 rounded px-3 py-2">{actionSuccess}</div>
      )}

      {fetchError && (
        <div className="mb-3 text-red-400 text-sm border border-red-400/30 rounded px-3 py-2">
          {fetchError}
          <button onClick={() => fetchQueue(0)} className="ml-3 underline text-xs">Retry</button>
        </div>
      )}

      {/* Split pane: queue list + detail */}
      <div className={selected ? 'split-pane' : ''}>
        {/* Queue list */}
        <div className={selected ? 'split-pane-left' : ''}>
          {loading && queue.length === 0 && (
            <div className="text-kb-muted text-sm py-8 text-center">Loading...</div>
          )}

          {!loading && !fetchError && queue.length === 0 && (
            <div className="text-kb-muted text-sm py-8 text-center">Queue is empty -- no pending items.</div>
          )}

          <div className="space-y-1.5">
            {queue.map(item => (
              <div
                key={item.id}
                onClick={() => { setSelected(item); setModifiedContent(item.content); setActionError(null) }}
                className={`kb-card p-3 cursor-pointer hover:border-kb-primary/40 transition ${selected?.id === item.id ? 'border-kb-primary' : ''}`}
              >
                <div className="flex justify-between items-start">
                  <div className="font-medium text-sm truncate max-w-md">{item.source_path}</div>
                  <div className="flex gap-2 items-center shrink-0 ml-2">
                    <span className="text-xs text-kb-muted">conf {item.confidence.toFixed(2)}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-kb-primary/10 text-kb-primary">{item.status}</span>
                  </div>
                </div>
                <div className="text-xs text-kb-muted mt-1 line-clamp-2">{item.content}</div>
                {item.created_at && (
                  <div className="text-[10px] text-kb-muted mt-1">{new Date(item.created_at).toLocaleString()}</div>
                )}
              </div>
            ))}
          </div>

          {(offset > 0 || hasMore) && (
            <div className="flex gap-2 mt-3 items-center">
              <button
                onClick={() => fetchQueue(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0 || loading}
                className="kb-btn border border-kb-primary/30 text-xs px-3 py-1 disabled:opacity-40"
              >Prev</button>
              <span className="text-xs text-kb-muted">Page {Math.floor(offset / PAGE_SIZE) + 1}</span>
              <button
                onClick={() => fetchQueue(offset + PAGE_SIZE)}
                disabled={!hasMore || loading}
                className="kb-btn border border-kb-primary/30 text-xs px-3 py-1 disabled:opacity-40"
              >Next</button>
            </div>
          )}
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="split-pane-right">
            <div className="kb-card p-4 sticky top-16">
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-semibold text-sm">Review Item</h3>
                <button onClick={() => setSelected(null)} className="text-kb-muted text-xs hover:text-kb-text">Close</button>
              </div>
              <div className="text-[11px] text-kb-muted mb-1 font-mono truncate">{selected.source_path}</div>
              <div className="text-[11px] text-kb-muted mb-3">
                Confidence: <span className="text-kb-text">{selected.confidence.toFixed(3)}</span>
                {' -- '}ID: <span className="font-mono">{selected.id.slice(0, 8)}...</span>
              </div>
              <textarea
                value={modifiedContent}
                onChange={e => setModifiedContent(e.target.value)}
                className="w-full h-32 bg-kb-dark border border-kb-primary/30 rounded p-2 text-xs font-mono resize-y"
                disabled={!isReviewer || actionLoading}
              />
              {actionError && (
                <div className="mt-2 text-red-400 text-xs border border-red-400/20 rounded px-2 py-1">{actionError}</div>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <button onClick={() => callAction(selected.id, 'APPROVE')} disabled={!isReviewer || actionLoading} className="kb-btn kb-btn-primary text-xs py-1.5 disabled:opacity-50">
                  Approve
                </button>
                <button onClick={() => callAction(selected.id, 'MODIFY')} disabled={!isReviewer || actionLoading} className="kb-btn border border-kb-primary/30 text-xs py-1.5 disabled:opacity-50">
                  Modify
                </button>
                <button onClick={() => callAction(selected.id, 'REJECT')} disabled={!isReviewer || actionLoading} className="kb-btn border border-red-400/40 text-red-400 text-xs py-1.5 disabled:opacity-50">
                  Reject
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
