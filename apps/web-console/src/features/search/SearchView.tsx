import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'

// Minimal types matching backend contracts (Graph)

interface GraphEntity {
  id: string
  name: string
  entity_type: string
  confidence: number
  provenance: Record<string, any>
}

interface GraphRelationship {
  id: string
  source_entity_id: string
  target_entity_id: string
  relationship_type: string
  confidence: number
  provenance: Record<string, any>
}

interface SearchResult {
  chunk_id: string
  document_id: string
  title: string
  source_path: string
  score: number
  vector_score: number
  snippet: string
  content: string
  tags: string[]
  wikilinks: string[]
  metadata: Record<string, any>
  graph_entities: GraphEntity[]
  graph_relationships: GraphRelationship[]
}


interface Stats {
  graphNodes: number | null
  pendingReviews: number | null
}

export default function SearchView({ currentUser }: { currentUser: { id: string; name: string; role: string } | null }) {
  const [query, setQuery] = useState('governed retrieval')
  const [tags, setTags] = useState<string[]>(['rag'])
  const [selected, setSelected] = useState<SearchResult | null>(null)
  const [stats, setStats] = useState<Stats>({ graphNodes: null, pendingReviews: null })

  const role = currentUser?.role || ''
  const userId = currentUser?.id || 'anonymous'

  useEffect(() => {
    const headers: Record<string, string> = {}
    if (role) headers['X-User-Role'] = role
    if (userId) headers['X-User-Id'] = userId

    Promise.allSettled([
      fetch('/api/v1/graph/stats').then((r) => r.json()),
      fetch('/api/v1/review/queue?limit=1', { headers }).then((r) => r.json()),
    ]).then(([gResult, rResult]) => {
      setStats({
        graphNodes: gResult.status === 'fulfilled' ? (gResult.value?.node_count ?? null) : null,
        pendingReviews: rResult.status === 'fulfilled' && Array.isArray(rResult.value) ? rResult.value.length : null,
      })
    })
  }, [role, userId])

  const searchWithAuth = async (req: any) => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (role) headers['X-User-Role'] = role
    if (userId) headers['X-User-Id'] = userId
    const res = await fetch(`/api/v1/search`, {
      method: 'POST',
      headers,
      body: JSON.stringify(req),
    })
    if (!res.ok) throw new Error(`Search failed: ${res.status}`)
    return res.json()
  }

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['search', query, tags, role],
    queryFn: () => searchWithAuth({ query, limit: 10, tags }),
    enabled: !!query,
  })

  const results = data?.results || []

  // Simple filter for demo (tags)
  const filtered = results.filter((r: SearchResult) =>
    tags.length === 0 || tags.some((t: string) => r.tags.includes(t))
  )

  return (
    <div>
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Search</h1>
          <p className="text-kb-muted text-sm">Hybrid (vector + rerank) + graph context</p>
        </div>
        {/* Stats bar */}
        <div className="flex gap-3 text-xs mt-1">
          {stats.graphNodes !== null && (
            <div className="kb-card px-3 py-1.5 flex gap-1.5 items-center">
              <span className="text-kb-muted">Graph nodes</span>
              <span className="font-semibold text-kb-primary">{stats.graphNodes.toLocaleString()}</span>
            </div>
          )}
          {stats.pendingReviews !== null && stats.pendingReviews > 0 && (
            <div className="kb-card px-3 py-1.5 flex gap-1.5 items-center border-amber-500/30">
              <span className="text-kb-muted">Pending review</span>
              <span className="font-semibold text-amber-400">{stats.pendingReviews}+</span>
            </div>
          )}
        </div>
      </div>

      {/* Query bar - matches ASCII wireframe */}
      <div className="kb-card p-4 mb-6">
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-xs text-kb-muted mb-1">Query</label>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && refetch()}
              className="w-full bg-kb-dark border border-kb-primary/30 rounded px-3 py-2 text-lg focus:outline-none focus:border-kb-primary"
              placeholder="governed retrieval in enterprise"
            />
          </div>
          <button onClick={() => refetch()} className="kb-btn kb-btn-primary">Search</button>
          <button onClick={() => { setQuery(''); setTags([]); }} className="kb-btn border border-kb-primary/30">Clear</button>
        </div>

        <div className="mt-3 flex gap-2 items-center text-sm">
          <span className="text-kb-muted">Tags:</span>
          {['rag', 'enterprise', 'audit'].map((t) => (
            <button
              key={t}
              onClick={() => setTags(tags.includes(t) ? tags.filter((x) => x !== t) : [...tags, t])}
              className={`px-2 py-0.5 rounded border text-xs ${tags.includes(t) ? 'bg-kb-primary/20 border-kb-primary' : 'border-kb-primary/30'}`}
            >
              {t}
            </button>
          ))}
          <span className="text-[10px] text-kb-muted ml-2">(synthetic data in dev)</span>
        </div>
      </div>

      {isLoading && <div className="text-kb-muted">Searching...</div>}
      {error && <div className="text-red-400">Error: {(error as Error).message}</div>}

      {/* Results list - matches ASCII wireframe */}
      <div className="space-y-3">
        {filtered.map((r: SearchResult) => (
          <div
            key={r.chunk_id}
            onClick={() => setSelected(r)}
            className="kb-card p-4 cursor-pointer hover:border-kb-primary/40"
          >
            <div className="flex justify-between items-start">
              <div>
                <div className="font-medium">{r.title}</div>
                <div className="text-xs text-kb-muted">{r.source_path} • score {r.score.toFixed(2)}</div>
              </div>
              <div className="text-right text-xs">
                <div>vector {r.vector_score.toFixed(2)}</div>
                {r.metadata?.confidence && <div>conf {Number(r.metadata.confidence).toFixed(2)}</div>}
              </div>
            </div>

            <div className="mt-2 text-sm" dangerouslySetInnerHTML={{ __html: r.snippet }} />

            <div className="mt-2 flex flex-wrap gap-1 text-xs">
              {r.tags.map((t: string) => <span key={t} className="px-1.5 py-0.5 bg-white/5 rounded">#{t}</span>)}
              {r.wikilinks.length > 0 && <span className="text-kb-muted">wikilinks: {r.wikilinks.join(', ')}</span>}
            </div>

            {/* Graph context summary (incl. document links) */}
            {(r.graph_entities.length > 0 || r.graph_relationships.length > 0) && (
              <div className="mt-3 pt-3 border-t border-kb-primary/10 text-xs">
                <div className="text-kb-muted mb-1">Graph context ({r.graph_entities.length} entities, {r.graph_relationships.length} rels)</div>
                <div className="flex flex-wrap gap-1">
                  {r.graph_entities.slice(0, 4).map((e: GraphEntity) => (
                    <span key={e.id} className="graph-node">{e.name} ({e.entity_type})</span>
                  ))}
                </div>
                {/* Document links (new from wikilinks) */}
                {r.graph_relationships.filter((rel: GraphRelationship) => rel.relationship_type === 'LINKS_TO').length > 0 && (
                  <div className="mt-1 text-[10px] text-kb-primary">
                    Document links: {r.graph_relationships.filter((rel: GraphRelationship) => rel.relationship_type === 'LINKS_TO').length} (see Graph tab for details)
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Selected detail + full graph panel (matches ASCII) */}
      {selected && (
        <div className="mt-8 kb-card p-5">
          <div className="flex justify-between">
            <h3 className="font-semibold">{selected.title}</h3>
            <button onClick={() => setSelected(null)} className="text-kb-muted">close</button>
          </div>
          <div className="text-sm mt-2 whitespace-pre-wrap">{selected.content}</div>

          {(selected.graph_entities.length > 0 || selected.graph_relationships.length > 0) && (
            <div className="mt-4">
              <div className="text-sm font-medium mb-2">
                Graph context
                <span className="ml-2 text-xs text-kb-muted font-normal">
                  {selected.graph_entities.length} entities · {selected.graph_relationships.length} relationships
                </span>
              </div>

              {/* Entity badges grouped by type */}
              {selected.graph_entities.length > 0 && (
                <div className="mb-3">
                  {Object.entries(
                    selected.graph_entities.reduce<Record<string, GraphEntity[]>>((acc, e: GraphEntity) => {
                      ;(acc[e.entity_type] ||= []).push(e)
                      return acc
                    }, {})
                  ).map(([type, ents]: [string, GraphEntity[]]) => (
                    <div key={type} className="flex flex-wrap gap-1 mb-1 items-center">
                      <span className="text-[10px] text-kb-muted w-24 shrink-0">{type}</span>
                      {ents.map((e: GraphEntity) => (
                        <span
                          key={e.id}
                          title={`conf ${e.confidence.toFixed(2)}`}
                          className="graph-node text-xs"
                        >
                          {e.name}
                        </span>
                      ))}
                    </div>
                  ))}
                </div>
              )}

              {/* Relationships as readable arrows */}
              {selected.graph_relationships.length > 0 && (
                <div className="space-y-1">
                  {selected.graph_relationships.map((r: GraphRelationship, i: number) => {
                    const src = selected.graph_entities.find((e: GraphEntity) => e.id === r.source_entity_id)
                    const tgt = selected.graph_entities.find((e: GraphEntity) => e.id === r.target_entity_id)
                    return (
                      <div key={i} className="flex items-center gap-1 text-xs">
                        <span className="text-kb-text font-medium">{src?.name ?? r.source_entity_id.slice(0, 8)}</span>
                        <span className="text-kb-primary/60 text-[10px] px-1">—{r.relationship_type}→</span>
                        <span className="text-kb-text font-medium">{tgt?.name ?? r.target_entity_id.slice(0, 8)}</span>
                        <span className="text-kb-muted text-[10px] ml-1">conf {r.confidence.toFixed(2)}</span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
          {selected.graph_entities.length === 0 && (
            <div className="mt-4 text-xs text-kb-muted">No graph context extracted for this chunk.</div>
          )}
        </div>
      )}

      {!isLoading && filtered.length === 0 && query && (
        <div className="text-kb-muted mt-8">No results. Try broadening or check backend is running (uvicorn).</div>
      )}
    </div>
  )
}
