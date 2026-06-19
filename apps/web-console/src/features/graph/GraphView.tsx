import { useState } from 'react'
import GraphCanvas, { type GraphNode, type GraphEdge } from '../graph-viz/GraphCanvas'

interface BuildResult {
  entities: GraphNode[]
  relationships: GraphEdge[]
  hyperedges?: { id: string; entity_ids: string[]; relationship_type: string; label?: string; confidence: number }[]
}

const MAX_DISPLAY_NODES = 80

export default function GraphView({ canBuild, currentUser }: {
  canBuild: boolean
  currentUser: { id: string; name: string; role: string } | null
}) {
  const [limit, setLimit] = useState(50)
  const [result, setResult] = useState<BuildResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<string>('all')
  const [tab, setTab] = useState<'visual' | 'json'>('visual')

  const role = currentUser?.role || ''
  const userId = currentUser?.id || 'anonymous'

  const buildGraph = async () => {
    if (!canBuild) return
    setLoading(true)
    setError(null)
    setResult(null)
    const headers: Record<string, string> = {}
    if (role) headers['X-User-Role'] = role
    if (userId) headers['X-User-Id'] = userId
    try {
      const res = await fetch(`/api/v1/graph/build?limit=${limit}`, { method: 'POST', headers })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail || `HTTP ${res.status}`)
      }
      const data: BuildResult = await res.json()
      setResult(data)
    } catch (e: any) {
      setError(e.message || 'Build failed — is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  const entityTypes = result ? Array.from(new Set(result.entities.map(e => e.entity_type))).sort() : []

  const visibleNodes: GraphNode[] = result
    ? (filterType === 'all' ? result.entities : result.entities.filter(e => e.entity_type === filterType))
        .slice(0, MAX_DISPLAY_NODES)
    : []

  const visibleNodeIds = new Set(visibleNodes.map(n => n.id))

  const visibleEdges: GraphEdge[] = result
    ? result.relationships.filter(
        r => visibleNodeIds.has(r.source_entity_id) && visibleNodeIds.has(r.target_entity_id),
      )
    : []

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-2">Graph Explorer</h1>
      <p className="text-sm text-kb-muted mb-4">
        Visual knowledge graph. Builds from approved chunks — requires Reviewer or Auditor role.
        Drag nodes to rearrange, hover for details.
      </p>

      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <div>
          <label className="text-xs text-kb-muted block mb-1">Chunk limit</label>
          <input
            type="number" min={1} max={500}
            value={limit}
            onChange={(e) => setLimit(Math.max(1, +e.target.value))}
            className="w-24 bg-kb-surface border border-kb-primary/30 rounded px-2 py-1 text-sm"
          />
        </div>

        <button
          onClick={buildGraph}
          disabled={loading || !canBuild}
          className={`kb-btn ${canBuild ? 'kb-btn-primary' : 'border border-kb-primary/30 opacity-50 cursor-not-allowed'}`}
          title={canBuild ? '' : 'Requires Reviewer or Auditor role'}
        >
          {loading ? 'Building…' : 'Build Graph'}
        </button>
        {!canBuild && <span className="text-xs text-kb-muted self-center">(permission required)</span>}
      </div>

      {error && (
        <div className="mb-4 text-red-400 text-sm border border-red-400/30 rounded px-3 py-2">{error}</div>
      )}

      {result && (
        <>
          {/* Stats bar */}
          <div className="flex flex-wrap gap-4 mb-4 text-sm">
            <span className="text-kb-muted">
              Entities: <span className="text-kb-text font-medium">{result.entities.length}</span>
            </span>
            <span className="text-kb-muted">
              Relationships: <span className="text-kb-text font-medium">{result.relationships.length}</span>
            </span>
            {(result.hyperedges?.length ?? 0) > 0 && (
              <span className="text-kb-muted">
                Hyperedges: <span className="text-kb-text font-medium">{result.hyperedges!.length}</span>
              </span>
            )}
            {result.entities.length > MAX_DISPLAY_NODES && (
              <span className="text-amber-400 text-xs self-center">
                Showing first {MAX_DISPLAY_NODES} nodes
              </span>
            )}
          </div>

          {/* Filter + tabs */}
          <div className="flex flex-wrap gap-2 mb-3 items-center justify-between">
            <div className="flex gap-1 flex-wrap">
              <button
                onClick={() => setFilterType('all')}
                className={`text-xs px-2 py-0.5 rounded border ${filterType === 'all' ? 'border-kb-primary text-kb-primary' : 'border-kb-primary/20 text-kb-muted'}`}
              >
                All types
              </button>
              {entityTypes.map(t => (
                <button
                  key={t}
                  onClick={() => setFilterType(t)}
                  className={`text-xs px-2 py-0.5 rounded border ${filterType === t ? 'border-kb-primary text-kb-primary' : 'border-kb-primary/20 text-kb-muted'}`}
                >
                  {t}
                </button>
              ))}
            </div>

            <div className="flex gap-1">
              {(['visual', 'json'] as const).map(t => (
                <button key={t} onClick={() => setTab(t)}
                  className={`text-xs px-2 py-0.5 rounded border ${tab === t ? 'border-kb-primary text-kb-primary' : 'border-kb-primary/20 text-kb-muted'}`}
                >
                  {t === 'visual' ? '🕸 Visual' : '{} JSON'}
                </button>
              ))}
            </div>
          </div>

          {tab === 'visual' ? (
            <GraphCanvas nodes={visibleNodes} edges={visibleEdges} />
          ) : (
            <pre className="bg-black/40 p-3 rounded text-[10px] overflow-auto max-h-96">
              {JSON.stringify({ entities: visibleNodes.slice(0, 20), relationships: visibleEdges.slice(0, 20) }, null, 2)}
            </pre>
          )}

          {/* Hyperedge list */}
          {(result.hyperedges?.length ?? 0) > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold mb-2 text-kb-muted">
                N-ary Hyperedges ({result.hyperedges!.length})
              </h3>
              <div className="space-y-1">
                {result.hyperedges!.slice(0, 20).map(h => (
                  <div key={h.id} className="kb-card p-2 text-xs flex gap-2 items-start">
                    <span className="text-kb-primary shrink-0">{h.relationship_type}</span>
                    <span className="text-kb-muted">{h.label || h.entity_ids.slice(0, 4).join(' · ')}</span>
                    <span className="text-kb-muted shrink-0">conf {h.confidence.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
