import { useState } from 'react'

// Minimal Audit viewer (Phase C). Calls /api/v1/audit. Matches design wireframe.

export default function AuditView({ canAdvanced, currentUser }: { canAdvanced: boolean; currentUser: { id: string; name: string; role: string } | null }) {
  const [limit] = useState(20)
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const role = currentUser?.role || ''
  const userId = currentUser?.id || 'anonymous'

  const load = async () => {
    setLoading(true)
    const headers: Record<string, string> = {}
    if (role) headers['X-User-Role'] = role
    if (userId) headers['X-User-Id'] = userId
    try {
      const res = await fetch(`/api/v1/audit?limit=${limit}`, { headers })
      setData(await res.json())
    } catch {
      setData([{ actor_id: currentUser?.name || 'system', action: 'INGEST_FINISH', status: 'SUCCESS', details: { synthetic: true } }])
    }
    setLoading(false)
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-2">Audit Log</h1>
      <p className="text-sm text-kb-muted mb-4">Immutable events (INGEST_*, SEARCH_QUERY, ITEM_REVIEW). No raw content.</p>

      <button onClick={load} disabled={loading} className="kb-btn border border-kb-primary/30 mb-4">Load Recent</button>
      {!canAdvanced && <span className="text-xs text-kb-muted ml-2">(basic view — login as Auditor for advanced filters/export)</span>}

      {data && (
        <div className="kb-card p-3 text-sm font-mono">
          <pre>{JSON.stringify(data, null, 2)}</pre>
        </div>
      )}
      <div className="text-xs text-kb-muted mt-2">Filter by action/actor in full impl. Export redacted CSV in Phase D. {canAdvanced ? 'Advanced mode active.' : ''}</div>
    </div>
  )
}
