import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { authHeaders } from '../../lib/auth'

interface GraphEntity {
  id: string
  name: string
  entity_type: string
  confidence: number
  provenance: Record<string, unknown>
}

interface GraphRelationship {
  id: string
  source_entity_id: string
  target_entity_id: string
  relationship_type: string
  confidence: number
  provenance: Record<string, unknown>
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
  metadata: Record<string, unknown>
  graph_entities: GraphEntity[]
  graph_relationships: GraphRelationship[]
}

interface Stats {
  graphNodes: number | null
  pendingReviews: number | null
}

export default function SearchView() {
  const [query, setQuery] = useState('governed retrieval')
  const [tags, setTags] = useState<string[]>(['rag'])
  const [selected, setSelected] = useState<SearchResult | null>(null)
  const [stats, setStats] = useState<Stats>({ graphNodes: null, pendingReviews: null })

  useEffect(() => {
    Promise.allSettled([
      fetch('/api/v1/graph/stats', { headers: authHeaders() }).then(r => r.json()),
      fetch('/api/v1/review/queue?limit=1', { headers: authHeaders() }).then(r => r.json()),
    ]).then(([gResult, rResult]) => {
      setStats({
        graphNodes: gResult.status === 'fulfilled' ? (gResult.value?.node_count ?? null) : null,
        pendingReviews: rResult.status === 'fulfilled' && Array.isArray(rResult.value) ? rResult.value.length : null,
      })
    })
  }, [])

  const searchWithAuth = async (req: { query: string; limit: number; tags: string[] }) => {
    const res = await fetch('/api/v1/search', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(req),
    })
    if (!res.ok) throw new Error(`Search failed: ${res.status}`)
    return res.json()
  }

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['search', query, tags],
    queryFn: () => searchWithAuth({ query, limit: 10, tags }),
    enabled: !!query,
  })

  const results = data?.results || []
  const filtered = results.filter((r: SearchResult) =>
    tags.length === 0 || tags.some((t: string) => r.tags.includes(t))
  )

  return (
    <div>
      {/* Header */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Search</h1>
          <p className="text-kb-muted text-xs mt-0.5">Hybrid vector + rerank + graph context</p>
        </div>
        <div className="flex gap-2 text-xs">
          {stats.graphNodes !== null && (
            <div className="kb-card px-3 py-1.5 flex gap-1.5 items-center">
              <span className="text-kb-muted">Graph nodes</span>
              <span className="font-semibold text-kb-primary">{stats.graphNodes.toLocaleString()}</span>
            </div>
          )}
          {stats.pendingReviews !== null && stats.pendingReviews > 0 && (
            <div className="kb-card px-3 py-1.5 flex gap-1.5 items-center border-amber-500/30">
              <span className="text-kb-muted">Pending</span>
              <span className="font-semibold text-amber-400">{stats.pendingReviews}+</span>
            </div>
          )}
        </div>
      </div>

      {/* Query bar */}
      <div className="kb-card p-4 mb-5">
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-xs text-kb-muted mb-1">Query</label>
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && refetch()}
              maxLength={500}
              className="w-full bg-kb-dark border border-kb-primary/30 rounded px-3 py-2 text-sm focus:outline-none focus:border-kb-primary"
              placeholder="governed retrieval in enterprise"
            />
          </div>
          <button onClick={() => refetch()} className="kb-btn kb-btn-primary py-2">Search</button>
          <button onClick={() => { setQuery(''); setTags([]) }} className="kb-btn border border-kb-primary/30 py-2">Clear</button>
        </div>
        <div className="mt-2 flex gap-2 items-center text-xs">
          <span className="text-kb-muted">Tags:</span>
          {['rag', 'enterprise', 'audit'].map(t => (
            <button
              key={t}
              onClick={() => setTags(tags.includes(t) ? tags.filter(x => x !== t) : [...tags, t])}
              className={`px-2 py-0.5 rounded border text-xs ${tags.includes(t) ? 'bg-kb-primary/20 border-kb-primary' : 'border-kb-primary/30'}`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <div className="text-kb-muted text-sm">Searching...</div>}
      {error && <div className="text-red-400 text-sm">Error: {(error as Error).message}</div>}

      {/* Split pane: results + detail */}
      <div className={selected ? 'split-pane' : ''}>
        {/* Results list */}
        <div className={selected ? 'split-pane-left' : ''}>
          <div className="space-y-2">
            {filtered.map((r: SearchResult) => (
              <div
                key={r.chunk_id}
                onClick={() => setSelected(r)}
                className={`kb-card p-3 cursor-pointer hover:border-kb-primary/40 transition ${selected?.chunk_id === r.chunk_id ? 'border-kb-primary' : ''}`}
              >
                <div className="flex justify-between items-start gap-2">
                  <div className="min-w-0">
                    <div className="font-medium text-sm truncate">{r.title}</div>
                    <div className="text-[11px] text-kb-muted truncate">{r.source_path}</div>
                  </div>
                  <div className="text-right text-[11px] text-kb-muted shrink-0">
                    <div>score {r.score.toFixed(2)}</div>
                    <div>vec {r.vector_score.toFixed(2)}</div>
                  </div>
                </div>
                <div className="mt-1.5 text-xs text-kb-text/80 line-clamp-2">{r.snippet}</div>
                <div className="mt-1.5 flex flex-wrap gap-1 text-[11px]">
                  {r.tags.map((t: string) => (
                    <span key={t} className="px-1.5 py-0.5 bg-white/5 rounded">#{t}</span>
                  ))}
                  {r.graph_entities.length > 0 && (
                    <span className="text-kb-muted">{r.graph_entities.length} entities</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="split-pane-right">
            <div className="kb-card p-4 sticky top-16">
              <div className="flex justify-between items-start mb-3">
                <h3 className="font-semibold text-sm">{selected.title}</h3>
                <button onClick={() => setSelected(null)} className="text-kb-muted text-xs hover:text-kb-text">
                  Close
                </button>
              </div>
              <div className="text-[11px] text-kb-muted mb-3">
                {selected.source_path} -- score {selected.score.toFixed(2)}
              </div>

              <div className="text-xs whitespace-pre-wrap mb-4 max-h-48 overflow-y-auto">
                {selected.content}
              </div>

              {(selected.graph_entities.length > 0 || selected.graph_relationships.length > 0) && (
                <div className="border-t border-kb-primary/10 pt-3">
                  <div className="text-xs font-medium mb-2">
                    Graph context
                    <span className="ml-2 text-[11px] text-kb-muted font-normal">
                      {selected.graph_entities.length} entities, {selected.graph_relationships.length} rels
                    </span>
                  </div>

                  {selected.graph_entities.length > 0 && (
                    <div className="mb-2">
                      {Object.entries(
                        selected.graph_entities.reduce<Record<string, GraphEntity[]>>((acc, e) => {
                          ;(acc[e.entity_type] ||= []).push(e)
                          return acc
                        }, {})
                      ).map(([type, ents]) => (
                        <div key={type} className="flex flex-wrap gap-1 mb-1 items-center">
                          <span className="text-[10px] text-kb-muted w-20 shrink-0">{type}</span>
                          {ents.map(e => (
                            <span key={e.id} className="graph-node text-[11px]">{e.name}</span>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}

                  {selected.graph_relationships.length > 0 && (
                    <div className="space-y-1">
                      {selected.graph_relationships.map((r, i) => {
                        const src = selected.graph_entities.find(e => e.id === r.source_entity_id)
                        const tgt = selected.graph_entities.find(e => e.id === r.target_entity_id)
                        return (
                          <div key={i} className="flex items-center gap-1 text-[11px]">
                            <span className="font-medium">{src?.name ?? r.source_entity_id.slice(0, 8)}</span>
                            <span className="text-kb-primary/60 text-[10px] px-1">&mdash;{r.relationship_type}&rarr;</span>
                            <span className="font-medium">{tgt?.name ?? r.target_entity_id.slice(0, 8)}</span>
                            <span className="text-kb-muted text-[10px] ml-1">conf {r.confidence.toFixed(2)}</span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}

              {selected.graph_entities.length === 0 && (
                <div className="text-[11px] text-kb-muted">No graph context for this chunk.</div>
              )}
            </div>
          </div>
        )}
      </div>

      {!isLoading && filtered.length === 0 && query && (
        <div className="text-kb-muted text-sm mt-6">No results. Try broadening the query.</div>
      )}
    </div>
  )
}
