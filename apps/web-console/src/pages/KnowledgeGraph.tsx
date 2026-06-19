import { useState, useEffect } from 'react'

interface GraphSearchResult {
  score: number
  source: string
  snippet: string
}

export default function KnowledgeGraph({ currentUser }: { currentUser: { id: string; name: string; role: string } | null }) {
  // Stats state
  const [nodeCount, setNodeCount] = useState<number | null>(null)
  const [statsError, setStatsError] = useState<string | null>(null)
  const [loadingStats, setLoadingStats] = useState(false)

  // Ingest panel state
  const [ingestText, setIngestText] = useState('')
  const [ingestSource, setIngestSource] = useState('doc_provenance.txt')
  const [ingestActor, setIngestActor] = useState(currentUser?.id || 'u1')
  const [ingestStatus, setIngestStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [ingesting, setIngesting] = useState(false)

  // Search panel state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchLimit, setSearchLimit] = useState(10)
  const [searchResults, setSearchResults] = useState<GraphSearchResult[]>([])
  const [searchError, setSearchError] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)

  // Update ingestActor if currentUser changes
  useEffect(() => {
    if (currentUser) {
      setIngestActor(currentUser.id)
    }
  }, [currentUser])

  // Fetch stats from GET /api/v1/graph/stats
  const fetchStats = async () => {
    setLoadingStats(true)
    setStatsError(null)
    try {
      const res = await fetch('/api/v1/graph/stats')
      if (!res.ok) {
        throw new Error(`Failed to fetch stats: ${res.status}`)
      }
      const data = await res.json()
      if (typeof data.node_count === 'number') {
        setNodeCount(data.node_count)
      } else {
        setNodeCount(0)
      }
    } catch (err: any) {
      setStatsError(err.message || 'Error loading stats')
      setNodeCount(null)
    } finally {
      setLoadingStats(false)
    }
  }

  // Load stats on mount
  useEffect(() => {
    fetchStats()
  }, [])

  // Ingest submit handler
  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ingestText.trim()) {
      setIngestStatus({ type: 'error', message: 'Document text cannot be empty' })
      return
    }
    if (!ingestSource.trim()) {
      setIngestStatus({ type: 'error', message: 'Source field cannot be empty' })
      return
    }

    setIngesting(true)
    setIngestStatus(null)

    try {
      const res = await fetch('/api/v1/graph/ingest', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: ingestText,
          source: ingestSource,
          actor_id: ingestActor,
        }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || `Ingestion failed with status ${res.status}`)
      }

      setIngestStatus({
        type: 'success',
        message: `Successfully ingested document! Chunks count: ${data.chunks_count || 0}`,
      })
      setIngestText('')
      // Refresh stats
      fetchStats()
    } catch (err: any) {
      setIngestStatus({
        type: 'error',
        message: err.message || 'An error occurred during ingestion',
      })
    } finally {
      setIngesting(false)
    }
  }

  // Search submit handler
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQuery.trim()) {
      setSearchError('Search query cannot be empty')
      return
    }

    setSearching(true)
    setSearchError(null)
    setSearchResults([])

    try {
      const headers: Record<string, string> = {}
      if (ingestActor) {
        headers['X-Actor-Id'] = ingestActor
      }
      
      const res = await fetch(`/api/v1/graph/search?q=${encodeURIComponent(searchQuery)}&limit=${searchLimit}`, {
        headers,
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || `Search failed with status ${res.status}`)
      }

      setSearchResults(data.results || [])
    } catch (err: any) {
      setSearchError(err.message || 'An error occurred during search')
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header and Stats */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-4 border-b border-kb-primary/10">
        <div>
          <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-kb-primary to-purple-400 bg-clip-text text-transparent">
            Knowledge Graph Console
          </h1>
          <p className="text-kb-muted text-sm mt-1">
            Build and query vector-indexed knowledge graph documents using semantic similarity.
          </p>
        </div>

        {/* Live Node Count Stat Card */}
        <div className="kb-card flex items-center justify-between gap-6 px-5 py-3 rounded-lg border border-kb-primary/20 bg-kb-surface/60 relative overflow-hidden group min-w-[200px]">
          <div className="absolute top-0 left-0 w-1 h-full bg-kb-primary"></div>
          <div>
            <div className="text-[10px] uppercase font-bold tracking-wider text-kb-muted">Live Node Count</div>
            <div className="text-2xl font-semibold tracking-tight mt-1 flex items-center gap-2">
              {loadingStats ? (
                <span className="text-sm text-kb-muted animate-pulse">Loading...</span>
              ) : nodeCount !== null ? (
                <span className="text-kb-primary font-mono drop-shadow-[0_0_8px_rgba(99,102,241,0.5)]">{nodeCount}</span>
              ) : (
                <span className="text-amber-400 font-mono">?</span>
              )}
            </div>
          </div>
          <button
            onClick={fetchStats}
            disabled={loadingStats}
            className="p-1.5 rounded bg-kb-primary/10 hover:bg-kb-primary/20 text-kb-primary transition"
            title="Refresh statistics"
          >
            🔄
          </button>
        </div>
      </div>

      {statsError && (
        <div className="p-3 bg-red-950/40 border border-red-500/20 text-red-300 rounded text-xs">
          ⚠️ Stats Error: {statsError}
        </div>
      )}

      {/* Grid Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Ingest Panel */}
        <div className="kb-card p-5 rounded-lg border border-kb-primary/10 flex flex-col space-y-4">
          <div>
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <span>📥</span> Ingest Document Chunks
            </h2>
            <p className="text-xs text-kb-muted mt-1">
              Ingest plain text documents. Text is automatically chunked and embedded using the sentence-transformers model.
            </p>
          </div>

          <form onSubmit={handleIngest} className="space-y-4 flex-1 flex flex-col justify-between">
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-kb-muted mb-1">Document Text</label>
                <textarea
                  value={ingestText}
                  onChange={(e) => setIngestText(e.target.value)}
                  placeholder="Paste raw text here... Example: The Enterprise Knowledge Graph models high-fidelity entities and relationships. Qdrant serves as the vector backend database."
                  rows={8}
                  className="w-full bg-kb-dark border border-kb-primary/20 hover:border-kb-primary/40 focus:border-kb-primary focus:outline-none rounded px-3 py-2 text-sm text-kb-text placeholder-kb-muted/50 resize-y"
                  required
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-kb-muted mb-1">Source Provenance</label>
                  <input
                    type="text"
                    value={ingestSource}
                    onChange={(e) => setIngestSource(e.target.value)}
                    placeholder="e.g. internal_wiki.txt"
                    className="w-full bg-kb-dark border border-kb-primary/20 hover:border-kb-primary/40 focus:border-kb-primary focus:outline-none rounded px-3 py-2 text-sm text-kb-text"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-kb-muted mb-1">Actor ID (RBAC Mock)</label>
                  <input
                    type="text"
                    value={ingestActor}
                    onChange={(e) => setIngestActor(e.target.value)}
                    placeholder="e.g. u1"
                    className="w-full bg-kb-dark border border-kb-primary/20 hover:border-kb-primary/40 focus:border-kb-primary focus:outline-none rounded px-3 py-2 text-sm text-kb-text"
                    required
                  />
                </div>
              </div>
            </div>

            <div className="pt-4 space-y-3">
              <button
                type="submit"
                disabled={ingesting}
                className={`w-full kb-btn flex items-center justify-center gap-2 ${
                  ingesting
                    ? 'bg-kb-primary/50 cursor-not-allowed text-kb-muted'
                    : 'kb-btn-primary'
                }`}
              >
                {ingesting ? (
                  <>
                    <span className="animate-spin inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full"></span>
                    Ingesting &amp; Embedding...
                  </>
                ) : (
                  'Submit to Graph Index'
                )}
              </button>

              {ingestStatus && (
                <div
                  className={`p-3 rounded text-xs border ${
                    ingestStatus.type === 'success'
                      ? 'bg-green-950/40 border-green-500/20 text-green-300'
                      : 'bg-red-950/40 border-red-500/20 text-red-300'
                  }`}
                >
                  {ingestStatus.type === 'success' ? '✅' : '❌'} {ingestStatus.message}
                </div>
              )}
            </div>
          </form>
        </div>

        {/* Search Panel */}
        <div className="kb-card p-5 rounded-lg border border-kb-primary/10 flex flex-col space-y-4">
          <div>
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <span>🔍</span> Semantic Search
            </h2>
            <p className="text-xs text-kb-muted mt-1">
              Search knowledge graph chunks using vector embeddings. Request contains RBAC authorization header.
            </p>
          </div>

          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter search query..."
              className="flex-1 bg-kb-dark border border-kb-primary/20 hover:border-kb-primary/40 focus:border-kb-primary focus:outline-none rounded px-3 py-2 text-sm text-kb-text"
              required
            />
            <select
              value={searchLimit}
              onChange={(e) => setSearchLimit(Number(e.target.value))}
              className="bg-kb-dark border border-kb-primary/20 hover:border-kb-primary/40 focus:border-kb-primary focus:outline-none rounded px-2 py-2 text-sm text-kb-text"
            >
              <option value={5}>5 results</option>
              <option value={10}>10 results</option>
              <option value={20}>20 results</option>
            </select>
            <button
              type="submit"
              disabled={searching}
              className="kb-btn kb-btn-primary py-2 px-4 flex items-center gap-1"
            >
              {searching ? '...' : 'Search'}
            </button>
          </form>

          {searchError && (
            <div className="p-3 bg-red-950/40 border border-red-500/20 text-red-300 rounded text-xs">
              ⚠️ Search Error: {searchError}
            </div>
          )}

          {/* Results List */}
          <div className="flex-1 overflow-y-auto max-h-[350px] space-y-3 pr-1">
            {searchResults.length > 0 ? (
              searchResults.map((result, idx) => (
                <div
                  key={idx}
                  className="kb-card p-3 rounded border border-kb-primary/10 bg-kb-surface/40 hover:bg-kb-surface/70 transition space-y-2"
                >
                  <div className="flex justify-between items-start text-xs">
                    <span className="font-semibold text-kb-primary bg-kb-primary/10 px-2 py-0.5 rounded border border-kb-primary/20">
                      Score: {result.score.toFixed(4)}
                    </span>
                    <span className="text-kb-muted italic truncate max-w-[200px]" title={result.source}>
                      Source: {result.source}
                    </span>
                  </div>
                  <p className="text-sm text-kb-text leading-relaxed whitespace-pre-wrap">
                    {result.snippet}
                  </p>
                </div>
              ))
            ) : searchQuery && !searching ? (
              <div className="h-full flex items-center justify-center text-xs text-kb-muted py-12">
                No matching results found in the graph collection.
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-kb-muted py-12">
                Search results will appear here.
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}
