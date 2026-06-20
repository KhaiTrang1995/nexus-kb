import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

interface GraphStats {
  node_count: number
  edge_count: number
  entity_type_breakdown?: Record<string, number>
  relationship_type_breakdown?: Record<string, number>
}

interface BuildResult {
  entities_created: number
  relationships_created: number
  chunks_processed: number
  duration_seconds?: number
}

export default function KnowledgeGraph({
  currentUser,
}: {
  currentUser: { id: string; name: string; role: string } | null
}) {
  const [stats, setStats] = useState<GraphStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [statsError, setStatsError] = useState<string | null>(null)

  const [buildLimit, setBuildLimit] = useState(100)
  const [building, setBuilding] = useState(false)
  const [buildResult, setBuildResult] = useState<BuildResult | null>(null)
  const [buildError, setBuildError] = useState<string | null>(null)

  const role = currentUser?.role || ''
  const canBuild = role === 'Reviewer' || role === 'Auditor'

  const fetchStats = async () => {
    setStatsLoading(true)
    setStatsError(null)
    try {
      const res = await fetch('/api/v1/graph/stats')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setStats(await res.json())
    } catch (e: any) {
      setStatsError(e.message)
    } finally {
      setStatsLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
  }, [])

  const handleBuild = async () => {
    if (!canBuild) return
    setBuilding(true)
    setBuildError(null)
    setBuildResult(null)
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (role) headers['X-User-Role'] = role
      if (currentUser?.id) headers['X-User-Id'] = currentUser.id

      const res = await fetch(`/api/v1/graph/build?limit=${buildLimit}`, {
        method: 'POST',
        headers,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setBuildResult(data)
      await fetchStats()
    } catch (e: any) {
      setBuildError(e.message)
    } finally {
      setBuilding(false)
    }
  }

  const total = stats ? stats.node_count + stats.edge_count : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Graph Management</h1>
        <p className="text-kb-muted text-sm mt-1">
          Trigger graph builds, view entity/relationship statistics, and monitor the knowledge graph.
          For ingestion use{' '}
          <Link to="/ingest" className="text-kb-primary hover:underline">
            Ingest
          </Link>
          ; for semantic search use{' '}
          <Link to="/" className="text-kb-primary hover:underline">
            Search
          </Link>
          ; for the graph visualizer use{' '}
          <Link to="/graph" className="text-kb-primary hover:underline">
            Graph
          </Link>
          .
        </p>
      </div>

      {/* Stats Banner */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {
            label: 'Entities (nodes)',
            value: stats ? stats.node_count.toLocaleString() : '—',
            color: 'text-kb-primary',
          },
          {
            label: 'Relationships (edges)',
            value: stats ? stats.edge_count.toLocaleString() : '—',
            color: 'text-purple-400',
          },
          {
            label: 'Total graph items',
            value: stats ? total.toLocaleString() : '—',
            color: 'text-cyan-400',
          },
          {
            label: 'Entity types',
            value: stats?.entity_type_breakdown
              ? Object.keys(stats.entity_type_breakdown).length
              : '—',
            color: 'text-amber-400',
          },
        ].map((s) => (
          <div key={s.label} className="kb-card p-4">
            <div className="text-[10px] uppercase tracking-wider text-kb-muted mb-1">{s.label}</div>
            <div className={`text-2xl font-mono font-semibold ${s.color}`}>{s.value}</div>
          </div>
        ))}
      </div>

      {statsError && (
        <div className="text-red-400 text-sm border border-red-400/20 rounded px-3 py-2">
          Stats error: {statsError}{' '}
          <button onClick={fetchStats} className="underline text-xs ml-2">
            Retry
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Build Graph Panel */}
        <div className="kb-card p-5 space-y-4">
          <div>
            <h2 className="font-semibold">Build Graph</h2>
            <p className="text-xs text-kb-muted mt-1">
              Runs the graph builder over approved chunks. Extracts entities and relationships, merges
              duplicates, and writes to the graph tables (including hyperedges if LLM_ENABLED=true).
            </p>
          </div>

          {!canBuild && (
            <div className="text-xs text-amber-400/80 border border-amber-400/20 rounded px-3 py-2">
              Reviewer or Auditor role required to trigger graph builds.
            </div>
          )}

          <div className="flex items-center gap-3">
            <label className="text-xs text-kb-muted shrink-0">Chunk limit</label>
            <input
              type="number"
              min={1}
              max={1000}
              value={buildLimit}
              onChange={(e) => setBuildLimit(Number(e.target.value))}
              disabled={!canBuild}
              className="w-24 bg-kb-dark border border-kb-primary/30 rounded px-2 py-1 text-sm focus:outline-none focus:border-kb-primary disabled:opacity-40"
            />
            <button
              onClick={handleBuild}
              disabled={!canBuild || building}
              className="kb-btn kb-btn-primary px-4 py-1.5 text-sm disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {building ? 'Building…' : 'Run Build'}
            </button>
            <button
              onClick={fetchStats}
              disabled={statsLoading}
              className="kb-btn border border-kb-primary/30 px-3 py-1.5 text-xs disabled:opacity-40"
            >
              {statsLoading ? '…' : 'Refresh'}
            </button>
          </div>

          {buildError && (
            <div className="text-red-400 text-xs border border-red-400/20 rounded px-3 py-2">
              Build failed: {buildError}
            </div>
          )}

          {buildResult && (
            <div className="text-xs border border-green-500/20 bg-green-500/5 rounded px-3 py-3 space-y-1">
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

        {/* Entity & Relationship Breakdown */}
        <div className="kb-card p-5 space-y-4">
          <h2 className="font-semibold">Type Breakdown</h2>

          {stats?.entity_type_breakdown && Object.keys(stats.entity_type_breakdown).length > 0 ? (
            <div>
              <div className="text-xs text-kb-muted mb-2 uppercase tracking-wider">Entities by type</div>
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
                          <div
                            className="h-full bg-kb-primary/60 rounded-full"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="font-mono text-kb-muted w-8 text-right">{count}</span>
                      </div>
                    )
                  })}
              </div>
            </div>
          ) : (
            <div className="text-xs text-kb-muted">
              {statsLoading ? 'Loading…' : 'No entity type breakdown available. Run a graph build first.'}
            </div>
          )}

          {stats?.relationship_type_breakdown &&
            Object.keys(stats.relationship_type_breakdown).length > 0 && (
              <div>
                <div className="text-xs text-kb-muted mb-2 uppercase tracking-wider mt-4">
                  Relationships by type
                </div>
                <div className="space-y-1.5">
                  {Object.entries(stats.relationship_type_breakdown)
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 8)
                    .map(([type, count]) => (
                      <div key={type} className="flex items-center justify-between text-xs">
                        <span className="text-kb-primary/80 text-[10px] font-mono">—{type}→</span>
                        <span className="font-mono text-kb-muted">{count}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}

          {!stats?.entity_type_breakdown && !statsLoading && (
            <div className="mt-2 text-[10px] text-kb-muted border border-kb-primary/10 rounded p-3">
              Tip: The graph builds from approved chunks in the review queue. Use the{' '}
              <Link to="/review" className="text-kb-primary">
                Review Queue
              </Link>{' '}
              to approve documents, then trigger a build here.
            </div>
          )}
        </div>
      </div>

      {/* Quick links */}
      <div className="kb-card p-4 text-xs text-kb-muted">
        <span className="font-medium text-kb-text">Quick links: </span>
        <Link to="/graph" className="text-kb-primary hover:underline mr-4">
          🕸️ Graph visualizer
        </Link>
        <Link to="/" className="text-kb-primary hover:underline mr-4">
          🔍 Semantic search
        </Link>
        <Link to="/ingest" className="text-kb-primary hover:underline mr-4">
          📥 Document ingest
        </Link>
        <Link to="/audit" className="text-kb-primary hover:underline">
          📜 Audit log
        </Link>
      </div>
    </div>
  )
}
