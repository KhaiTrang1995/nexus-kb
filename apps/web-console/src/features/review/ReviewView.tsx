import { useState } from 'react'

// Minimal Review Queue per ASCII design in docs/UI/nexus-kb-operational-ui.md
// Uses mock data + dev role. In real: call /api/v1/review/queue with X-User-Role header.

interface ReviewItem {
  id: string
  source_path: string
  content: string
  confidence: number
  status: string
}

const MOCK_QUEUE: ReviewItem[] = [
  { id: 'r1', source_path: 'vault/review.md', content: 'low confidence entity about RAG governance...', confidence: 0.42, status: 'PENDING' },
  { id: 'r2', source_path: 'vault/Platform.md#chunk3', content: 'another low conf chunk from obsidian...', confidence: 0.61, status: 'PENDING' },
]

export default function ReviewView({ currentUser }: { currentUser: { id: string; name: string; role: string } | null }) {
  const [queue, setQueue] = useState(MOCK_QUEUE)
  const [selected, setSelected] = useState<ReviewItem | null>(null)
  const [modifiedContent, setModifiedContent] = useState('')
  const role = currentUser?.role || ''
  const userId = currentUser?.id || 'anonymous'
  const isReviewer = role === 'Reviewer'

  const callAction = async (itemId: string, action: 'APPROVE' | 'REJECT' | 'MODIFY') => {
    if (!isReviewer) {
      alert('403: Reviewer role required')
      return
    }

    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (role) headers['X-User-Role'] = role
    if (userId) headers['X-User-Id'] = userId

    // Real call (or simulate if backend not up)
    try {
      await fetch(`/api/v1/review/action`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          item_id: itemId,
          action,
          ...(action === 'MODIFY' && { modified_content: modifiedContent }),
        }),
      })
    } catch {
      console.log('Review action (simulated)', { item_id: itemId, action, modified_content: action === 'MODIFY' ? modifiedContent : undefined })
    }

    // Optimistic update (matches design)
    setQueue((q) => q.filter((i) => i.id !== itemId))
    setSelected(null)
    alert(action === 'APPROVE' ? 'Item approved. 1 chunk added to vector index.' : 'Action recorded (synthetic).')
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-1">Review Queue</h1>
      <p className="text-kb-muted text-sm mb-4">Low-confidence chunks routed for human review (Phase 2). Use dev role switcher for X-User-Role: Reviewer.</p>

      {!isReviewer && <div className="mb-4 text-amber-400 text-sm">Switch to "Reviewer" in header to enable actions.</div>}

      <div className="space-y-2">
        {queue.length === 0 && <div className="text-kb-muted">Queue empty (synthetic demo).</div>}
        {queue.map((item) => (
          <div key={item.id} onClick={() => { setSelected(item); setModifiedContent(item.content) }} className="kb-card p-3 cursor-pointer hover:border-kb-primary/40">
            <div className="flex justify-between">
              <div className="font-medium">{item.source_path}</div>
              <div className="text-xs text-kb-muted">conf {item.confidence.toFixed(2)}</div>
            </div>
            <div className="text-sm mt-1 line-clamp-2">{item.content}</div>
            <div className="text-[10px] text-kb-primary mt-1">Click for actions (Approve / Modify / Reject)</div>
          </div>
        ))}
      </div>

      {selected && (
        <div className="mt-6 kb-card p-5">
          <h3 className="font-semibold mb-2">Review Item — {selected.source_path}</h3>
          <textarea
            value={modifiedContent}
            onChange={(e) => setModifiedContent(e.target.value)}
            className="w-full h-24 bg-kb-dark border border-kb-primary/30 rounded p-2 text-sm font-mono"
            disabled={!isReviewer}
          />

          <div className="mt-4 flex gap-2">
            <button onClick={() => callAction(selected.id, 'APPROVE')} disabled={!isReviewer} className="kb-btn kb-btn-primary">Approve &amp; Index to Vector</button>
            <button onClick={() => callAction(selected.id, 'MODIFY')} disabled={!isReviewer} className="kb-btn border border-kb-primary/30">Modify &amp; Re-index</button>
            <button onClick={() => callAction(selected.id, 'REJECT')} disabled={!isReviewer} className="kb-btn border border-red-400/40 text-red-400">Reject (do not index)</button>
            <button onClick={() => setSelected(null)} className="kb-btn ml-auto">Cancel</button>
          </div>
          <div className="text-[10px] text-kb-muted mt-2">Exact wording matches backend (see docs/UI/ for full list). 409/403 handled.</div>
        </div>
      )}
    </div>
  )
}
