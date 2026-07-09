import { useState, useEffect } from 'react'
import GraphCanvas, { type GraphNode, type GraphEdge } from '../graph-viz/GraphCanvas'
import { authHeaders } from '../../lib/auth'

interface HyperEdge {
  id: string
  entity_ids: string[]
  relationship_type: string
  label?: string
  confidence: number
}

interface BuildResult {
  entities: GraphNode[]
  relationships: GraphEdge[]
  hyperedges?: HyperEdge[]
}

interface GraphStats {
  node_count: number
  edge_count: number
  entity_type_breakdown?: Record<string, number>
  relationship_type_breakdown?: Record<string, number>
}

interface EntityContextChunk {
  chunk_id: string
  document_id: string
  document_title: string
  source_path: string
  content: string
}

interface EntityContext {
  entity: GraphNode
  chunks: EntityContextChunk[]
}

const MAX_DISPLAY_NODES = 80

type Tab = 'explorer' | 'statistics' | 'build'

export default function GraphView({ canBuild }: {
  canBuild: boolean
}) {
  const [tab, setTab] = useState<Tab>('explorer')

  // Explorer state
  const [limit, setLimit] = useState(50)
  const [result, setResult] = useState<BuildResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<string>('all')
  const [viewMode, setViewMode] = useState<'visual' | 'json'>('visual')

  // Node search
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<GraphNode[]>([])
  const [searching, setSearching] = useState(false)
  const [highlightNodeId, setHighlightNodeId] = useState<string | null>(null)

  // Node click -> content panel
  const [entityContext, setEntityContext] = useState<EntityContext | null>(null)
  const [contextLoading, setContextLoading] = useState(false)
  const [contextError, setContextError] = useState<string | null>(null)

  // Stats state
  const [stats, setStats] = useState<GraphStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [statsError, setStatsError] = useState<string | null>(null)

  // Build state
  const [buildLimit, setBuildLimit] = useState(100)
  const [building, setBuilding] = useState(false)
  const [buildResult, setBuildResult] = useState<{ entities_created: number; relationships_created: number; chunks_processed: number; duration_seconds?: number } | null>(null)
  const [buildError, setBuildError] = useState<string | null>(null)

  const fetchStats = async () => {
    setStatsLoading(true)
    setStatsError(null)
    try {
      const res = await fetch('/api/v1/graph/stats')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setStats(await res.json())
    } catch (e: unknown) {
      setStatsError(e instanceof Error ? e.message : 'Failed to load stats')
    } finally {
      setStatsLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
  }, [])

  // Load the already-built graph on first visit to Explorer, without
  // forcing an extraction re-run (that's what the Build Graph button/tab is for).
  useEffect(() => {
    let cancelled = false
    const loadView = async () => {
      try {
        const res = await fetch(`/api/v1/graph/view?limit=${limit}`, { headers: authHeaders() })
        if (!res.ok) return
        const data = await res.json()
        if (!cancelled) setResult({ entities: data.entities, relationships: data.relationships, hyperedges: [] })
      } catch {
        // Silent: the explorer just stays empty until "Build Graph" is used.
      }
    }
    loadView()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const searchNodes = async (query: string) => {
    setSearchQuery(query)
    if (!query.trim()) {
      setSearchResults([])
      return
    }
    setSearching(true)
    try {
      const res = await fetch(`/api/v1/graph/entities/search?q=${encodeURIComponent(query)}&limit=10`, {
        headers: authHeaders(),
      })
      if (!res.ok) return
      setSearchResults(await res.json())
    } catch {
      setSearchResults([])
    } finally {
      setSearching(false)
    }
  }

  const focusOnNode = async (node: GraphNode) => {
    setHighlightNodeId(node.id)
    setSearchResults([])
    setSearchQuery(node.name)
    try {
      const res = await fetch(`/api/v1/graph/entities/${node.id}/neighbors`, { headers: authHeaders() })
      if (!res.ok) return
      const data = await res.json()
      setResult({ entities: data.entities, relationships: data.relationships, hyperedges: [] })
    } catch {
      // Keep the currently-displayed graph if the neighbor lookup fails.
    }
  }

  const openNodeContext = async (node: GraphNode) => {
    setContextLoading(true)
    setContextError(null)
    setEntityContext(null)
    try {
      const res = await fetch(`/api/v1/graph/entities/${node.id}/context`, { headers: authHeaders() })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail || `HTTP ${res.status}`)
      }
      setEntityContext(await res.json())
    } catch (e: unknown) {
      setContextError(e instanceof Error ? e.message : 'Failed to load node content')
    } finally {
      setContextLoading(false)
    }
  }

  const buildGraph = async () => {
    if (!canBuild) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch(`/api/v1/graph/build?limit=${limit}`, { method: 'POST', headers: authHeaders() })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail || `HTTP ${res.status}`)
      }
      const data: BuildResult = await res.json()
      setResult(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Build failed')
    } finally {
      setLoading(false)
    }
  }

  const handleBuild = async () => {
    if (!canBuild) return
    setBuilding(true)
    setBuildError(null)
    setBuildResult(null)
    try {
      const res = await fetch(`/api/v1/graph/build?limit=${buildLimit}`, {
        method: 'POST',
        headers: authHeaders(),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      setBuildResult(await res.json())
      await fetchStats()
    } catch (e: unknown) {
      setBuildError(e instanceof Error ? e.message : 'Build failed')
    } finally {
      setBuilding(false)
    }
  }

  const entityTypes = result ? Array.from(new Set(result.entities.map(e => e.entity_type))).sort() : []
  const visibleNodes: GraphNode[] = result
    ? (filterType === 'all' ? result.entities : result.entities.filter(e => e.entity_type === filterType))
        .slice(0, MAX_DISPLAY_NODES)
    : []
  const visibleNodeIds = new Set(visibleNodes.map(n => n.id))
  const visibleEdges: GraphEdge[] = result
    ? result.relationships.filter(r => visibleNodeIds.has(r.source_entity_id) && visibleNodeIds.has(r.target_entity_id))
    : []

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Graph</h1>
        <p className="text-xs text-kb-muted mt-0.5">Knowledge graph explorer, statistics, and build management</p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-kb-primary/10 mb-4">
        {([
          { key: 'explorer', label: 'Explorer' },
          { key: 'statistics', label: 'Statistics' },
          { key: 'build', label: 'Build' },
        ] as const).map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`tab-btn ${tab === t.key ? 'active' : ''}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Explorer tab */}
      {tab === 'explorer' && (
        <div>
          <div className="flex flex-wrap gap-3 mb-4 items-end">
            <div>
              <label className="text-xs text-kb-muted block mb-1">Chunk limit</label>
              <input
                type="number" min={1} max={500}
                value={limit}
                onChange={e => setLimit(Math.max(1, +e.target.value))}
                className="w-24 bg-kb-surface border border-kb-primary/30 rounded px-2 py-1 text-sm"
              />
            </div>
            <button
              onClick={buildGraph}
              disabled={loading || !canBuild}
              className={`kb-btn ${canBuild ? 'kb-btn-primary' : 'border border-kb-primary/30 opacity-50 cursor-not-allowed'}`}
              title={canBuild ? '' : 'Requires Reviewer or Auditor role'}
            >
              {loading ? 'Building...' : 'Build Graph'}
            </button>
            {!canBuild && <span className="text-xs text-kb-muted self-center">(permission required)</span>}

            <div className="relative">
              <label className="text-xs text-kb-muted block mb-1">Find node</label>
              <input
                type="text"
                value={searchQuery}
                onChange={e => searchNodes(e.target.value)}
                placeholder="Search entity by name..."
                className="w-56 bg-kb-surface border border-kb-primary/30 rounded px-2 py-1 text-sm"
              />
              {searching && <span className="text-[10px] text-kb-muted absolute -bottom-4 left-0">Searching...</span>}
              {searchResults.length > 0 && (
                <ul className="absolute z-10 top-full mt-1 w-64 max-h-56 overflow-auto bg-kb-surface border border-kb-primary/30 rounded shadow-lg">
                  {searchResults.map(node => (
                    <li key={node.id}>
                      <button
                        onClick={() => focusOnNode(node)}
                        className="w-full text-left px-2 py-1.5 text-xs hover:bg-kb-primary/10 flex justify-between gap-2"
                      >
                        <span>{node.name}</span>
                        <span className="text-kb-muted">{node.entity_type}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {error && (
            <div className="mb-4 text-red-400 text-sm border border-red-400/30 rounded px-3 py-2">{error}</div>
          )}

          {result && (
            <>
              <div className="flex flex-wrap gap-4 mb-3 text-sm">
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
                    <button key={t} onClick={() => setViewMode(t)}
                      className={`text-xs px-2 py-0.5 rounded border ${viewMode === t ? 'border-kb-primary text-kb-primary' : 'border-kb-primary/20 text-kb-muted'}`}
                    >
                      {t === 'visual' ? 'Visual' : 'JSON'}
                    </button>
                  ))}
                </div>
              </div>

              {viewMode === 'visual' ? (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                  <div className="lg:col-span-2">
                    <GraphCanvas
                      nodes={visibleNodes}
                      edges={visibleEdges}
                      onNodeClick={openNodeContext}
                      highlightNodeId={highlightNodeId}
                    />
                  </div>
                  <div className="kb-card p-3 text-xs max-h-[560px] overflow-auto">
                    <div className="uppercase tracking-wider text-kb-muted mb-2">Node content</div>
                    {contextLoading && <div className="text-kb-muted">Loading...</div>}
                    {contextError && <div className="text-red-400">{contextError}</div>}
                    {!contextLoading && !contextError && !entityContext && (
                      <div className="text-kb-muted">Click a node to see the document it came from.</div>
                    )}
                    {entityContext && (
                      <div>
                        <div className="font-medium text-kb-text mb-2">{entityContext.entity.name}</div>
                        {entityContext.chunks.length === 0 && (
                          <div className="text-kb-muted">No source chunk found for this entity.</div>
                        )}
                        {entityContext.chunks.map(chunk => (
                          <div key={chunk.chunk_id} className="mb-3 pb-3 border-b border-kb-primary/10 last:border-0">
                            <div className="text-kb-primary text-[11px] mb-1">{chunk.document_title}</div>
                            <div className="text-kb-muted text-[10px] mb-1">{chunk.source_path}</div>
                            <p className="whitespace-pre-wrap">{chunk.content}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <pre className="bg-black/40 p-3 rounded text-[10px] overflow-auto max-h-96">
                  {JSON.stringify({ entities: visibleNodes.slice(0, 20), relationships: visibleEdges.slice(0, 20) }, null, 2)}
                </pre>
              )}

              {(result.hyperedges?.length ?? 0) > 0 && (
                <div className="mt-5">
                  <h3 className="text-sm font-semibold mb-2 text-kb-muted">
                    N-ary Hyperedges ({result.hyperedges!.length})
                  </h3>
                  <div className="space-y-1">
                    {result.hyperedges!.slice(0, 20).map(h => (
                      <div key={h.id} className="kb-card p-2 text-xs flex gap-2 items-start">
                        <span className="text-kb-primary shrink-0">{h.relationship_type}</span>
                        <span className="text-kb-muted">{h.label || h.entity_ids.slice(0, 4).join(' / ')}</span>
                        <span className="text-kb-muted shrink-0">conf {h.confidence.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Statistics tab */}
      {tab === 'statistics' && (
        <div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            {[
              { label: 'Entities', value: stats ? stats.node_count.toLocaleString() : '--', color: 'text-kb-primary' },
              { label: 'Relationships', value: stats ? stats.edge_count.toLocaleString() : '--', color: 'text-purple-400' },
              { label: 'Total', value: stats ? (stats.node_count + stats.edge_count).toLocaleString() : '--', color: 'text-cyan-400' },
              { label: 'Entity types', value: stats?.entity_type_breakdown ? Object.keys(stats.entity_type_breakdown).length : '--', color: 'text-amber-400' },
            ].map(s => (
              <div key={s.label} className="kb-card p-4">
                <div className="text-[10px] uppercase tracking-wider text-kb-muted mb-1">{s.label}</div>
                <div className={`text-2xl font-mono font-semibold ${s.color}`}>{s.value}</div>
              </div>
            ))}
          </div>

          {statsError && (
            <div className="text-red-400 text-sm border border-red-400/20 rounded px-3 py-2 mb-4">
              {statsError}
              <button onClick={fetchStats} className="underline text-xs ml-2">Retry</button>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="kb-card p-4">
              <div className="text-xs text-kb-muted mb-3 uppercase tracking-wider">Entities by type</div>
              {stats?.entity_type_breakdown && Object.keys(stats.entity_type_breakdown).length > 0 ? (
                <div className="space-y-1.5">
                  {Object.entries(stats.entity_type_breakdown)
                    .sort(([, a], [, b]) => b - a)
                    .map(([type, count]) => {
                      const max = Math.max(...Object.values(stats.entity_type_breakdown!))
                      const pct = max > 0 ? (count / max) * 100 : 0
                      return (
                        <div key={type} className="flex items-center gap-2 text-xs">
                          <span className="graph-node text-[10px]">{type}</span>
                          <div className="flex-1 bg-kb-dark rounded-full h-1.5 overflow-hidden">
                            <div className="h-full bg-kb-primary/60 rounded-full" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="font-mono text-kb-muted w-8 text-right">{count}</span>
                        </div>
                      )
                    })}
                </div>
              ) : (
                <div className="text-xs text-kb-muted">
                  {statsLoading ? 'Loading...' : 'No data. Run a graph build first.'}
                </div>
              )}
            </div>

            <div className="kb-card p-4">
              <div className="text-xs text-kb-muted mb-3 uppercase tracking-wider">Relationships by type</div>
              {stats?.relationship_type_breakdown && Object.keys(stats.relationship_type_breakdown).length > 0 ? (
                <div className="space-y-1.5">
                  {Object.entries(stats.relationship_type_breakdown)
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 10)
                    .map(([type, count]) => (
                      <div key={type} className="flex items-center justify-between text-xs">
                        <span className="text-kb-primary/80 text-[10px] font-mono">--{type}--&gt;</span>
                        <span className="font-mono text-kb-muted">{count}</span>
                      </div>
                    ))}
                </div>
              ) : (
                <div className="text-xs text-kb-muted">
                  {statsLoading ? 'Loading...' : 'No data.'}
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 flex justify-end">
            <button onClick={fetchStats} disabled={statsLoading} className="kb-btn border border-kb-primary/30 text-xs py-1">
              {statsLoading ? 'Loading...' : 'Refresh Stats'}
            </button>
          </div>
        </div>
      )}

      {/* Build tab */}
      {tab === 'build' && (
        <div>
          <div className="kb-card p-5 max-w-2xl">
            <h2 className="font-semibold text-sm mb-1">Build Graph</h2>
            <p className="text-xs text-kb-muted mb-4">
              Extracts entities and relationships from approved chunks, merges duplicates, and writes to graph tables.
            </p>

            {!canBuild && (
              <div className="text-xs text-amber-400/80 border border-amber-400/20 rounded px-3 py-2 mb-4">
                Reviewer or Auditor role required to trigger graph builds.
              </div>
            )}

            <div className="flex items-center gap-3 mb-4">
              <label className="text-xs text-kb-muted shrink-0">Chunk limit</label>
              <input
                type="number" min={1} max={1000}
                value={buildLimit}
                onChange={e => setBuildLimit(Number(e.target.value))}
                disabled={!canBuild}
                className="w-24 bg-kb-dark border border-kb-primary/30 rounded px-2 py-1 text-sm disabled:opacity-40"
              />
              <button
                onClick={handleBuild}
                disabled={!canBuild || building}
                className="kb-btn kb-btn-primary text-xs py-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {building ? 'Building...' : 'Run Build'}
              </button>
              <button onClick={fetchStats} disabled={statsLoading} className="kb-btn border border-kb-primary/30 text-xs py-1.5 disabled:opacity-40">
                {statsLoading ? '...' : 'Refresh'}
              </button>
            </div>

            {buildError && (
              <div className="text-red-400 text-xs border border-red-400/20 rounded px-3 py-2 mb-3">
                Build failed: {buildError}
              </div>
            )}

            {buildResult && (
              <div className="text-xs border border-green-500/20 bg-green-500/5 rounded px-3 py-3">
                <div className="text-green-400 font-medium mb-2">Build complete</div>
                <div className="grid grid-cols-2 gap-x-6 gap-y-1">
                  {[
                    ['Chunks processed', buildResult.chunks_processed],
                    ['Entities created', buildResult.entities_created],
                    ['Relationships created', buildResult.relationships_created],
                    ...(buildResult.duration_seconds !== undefined
                      ? [['Duration', `${buildResult.duration_seconds.toFixed(2)}s`]]
                      : []),
                  ].map(([k, v]) => (
                    <div key={String(k)} className="flex justify-between">
                      <span className="text-kb-muted">{k}</span>
                      <span className="font-mono text-kb-text">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
