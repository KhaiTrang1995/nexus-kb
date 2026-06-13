import { useState } from 'react'

// Minimal Graph view (Phase C start). Shows document links (new LINKS_TO) + entity graph context.
// For real: call /api/v1/graph/build and /graph/chunks/{id} or reuse from search.

export default function GraphView({ canBuild, currentUser }: { canBuild: boolean; currentUser: { id: string; name: string; role: string } | null }) {
  const [limit, setLimit] = useState(20)
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const role = currentUser?.role || ''
  const userId = currentUser?.id || 'anonymous'

  const buildGraph = async () => {
    if (!canBuild) {
      alert('Permission denied: Requires Reviewer or Auditor role')
      return
    }
    setLoading(true)
    const headers: Record<string, string> = {}
    if (role) headers['X-User-Role'] = role
    if (userId) headers['X-User-Id'] = userId
    try {
      const res = await fetch(`/api/v1/graph/build?limit=${limit}`, { headers })
      const data = await res.json()
      setResult(data)
    } catch (e) {
      setResult({ error: 'Backend not reachable (run uvicorn + proxy). Using synthetic for demo.' })
    }
    setLoading(false)
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-2">Graph Explorer</h1>
      <p className="text-sm text-kb-muted mb-4">Builds from approved chunks. Now includes document-to-document LINKS_TO from wikilinks (see Phase 4 enhancement).</p>

      <div className="flex gap-3 mb-4">
        <input type="number" value={limit} onChange={(e) => setLimit(+e.target.value)} className="w-24 bg-kb-surface border border-kb-primary/30 rounded px-2" />
        <button 
          onClick={buildGraph} 
          disabled={loading || !canBuild} 
          className={`kb-btn ${canBuild ? 'kb-btn-primary' : 'border border-kb-primary/30 opacity-50 cursor-not-allowed'}`}
          title={canBuild ? '' : 'Requires Reviewer or Auditor role'}
        >
          Build Graph
        </button>
        {!canBuild && <span className="self-center text-xs text-kb-muted">(permission required)</span>}
      </div>

      {loading && <div className="text-kb-muted">Building...</div>}

      {result && (
        <div className="kb-card p-4">
          {result.error ? (
            <div className="text-amber-400">{result.error}</div>
          ) : (
            <>
              <div>Entities: {result.entities?.length || 0} (incl. DOCUMENT nodes)</div>
              <div>Relationships: {result.relationships?.length || 0}</div>
              <div className="mt-3 text-xs">
                {result.relationships?.filter((r: any) => r.relationship_type === 'LINKS_TO').length > 0 && (
                  <div className="text-kb-primary">Document links (LINKS_TO) present — see search results for per-chunk view.</div>
                )}
                <pre className="mt-2 bg-black/40 p-2 rounded text-[10px] overflow-auto max-h-64">{JSON.stringify(result, null, 2)}</pre>
              </div>
            </>
          )}
        </div>
      )}

      <div className="mt-8 text-xs text-kb-muted">Simple list view for MVP (per ASCII design). Add force-graph lib in Phase D if needed. Synthetic data recommended.</div>
    </div>
  )
}
