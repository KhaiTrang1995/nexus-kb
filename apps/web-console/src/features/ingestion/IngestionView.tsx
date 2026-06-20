import { useState } from 'react'

interface IngestionResult {
  run_id: string
  status: string
  documents_seen: number
  documents_indexed: number
  chunks_indexed: number
  error_message?: string | null
}

const SOURCE_TYPES = [
  { value: 'local_file', label: 'Local File / Directory' },
  { value: 'obsidian', label: 'Obsidian Vault' },
]

export default function IngestionView({ currentUser }: { currentUser: { id: string; name: string; role: string } | null }) {
  const [sourcePath, setSourcePath] = useState('')
  const [sourceType, setSourceType] = useState('local_file')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<IngestionResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<IngestionResult[]>([])

  const role = currentUser?.role || ''
  const userId = currentUser?.id || 'anonymous'
  const canIngest = role === 'Reviewer' || role === 'Auditor'

  const runIngestion = async () => {
    if (!sourcePath.trim()) {
      setError('Source path is required.')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)

    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (role) headers['X-User-Role'] = role
    if (userId) headers['X-User-Id'] = userId

    try {
      const res = await fetch('/api/v1/ingest', {
        method: 'POST',
        headers,
        body: JSON.stringify({ source_path: sourcePath.trim(), source_type: sourceType }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail || `HTTP ${res.status}`)
      }
      const data: IngestionResult = await res.json()
      setResult(data)
      setHistory((h) => [data, ...h].slice(0, 10))
      setSourcePath('')
    } catch (e: any) {
      setError(e.message || 'Ingestion failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-1">Document Ingestion</h1>
      <p className="text-kb-muted text-sm mb-4">
        Ingest local files or an Obsidian vault into the vector index and knowledge graph.
        Requires Reviewer or Auditor role.
      </p>

      {!canIngest && (
        <div className="mb-4 text-amber-400 text-sm border border-amber-400/30 rounded px-3 py-2">
          Switch to Reviewer or Auditor role to run ingestion.
        </div>
      )}

      <div className="kb-card p-5 mb-6">
        <div className="flex flex-col gap-3">
          <div>
            <label className="text-xs text-kb-muted block mb-1">Source type</label>
            <select
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value)}
              disabled={!canIngest || loading}
              className="w-full bg-kb-dark border border-kb-primary/30 rounded px-3 py-2 text-sm"
            >
              {SOURCE_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs text-kb-muted block mb-1">Source path</label>
            <input
              type="text"
              value={sourcePath}
              onChange={(e) => setSourcePath(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && canIngest && !loading && runIngestion()}
              placeholder="/path/to/documents or C:\vault"
              disabled={!canIngest || loading}
              className="w-full bg-kb-dark border border-kb-primary/30 rounded px-3 py-2 text-sm font-mono"
            />
          </div>

          <button
            onClick={runIngestion}
            disabled={!canIngest || loading}
            className={`kb-btn w-fit ${canIngest ? 'kb-btn-primary' : 'opacity-50 cursor-not-allowed border border-kb-primary/30'}`}
          >
            {loading ? 'Ingesting…' : 'Run Ingestion'}
          </button>
        </div>

        {error && (
          <div className="mt-3 text-red-400 text-sm border border-red-400/30 rounded px-3 py-2">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-4 border border-kb-primary/30 rounded p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-xs px-2 py-0.5 rounded ${result.status === 'completed' ? 'bg-green-500/20 text-green-400' : result.status === 'failed' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                {result.status.toUpperCase()}
              </span>
              <span className="text-xs text-kb-muted font-mono">{result.run_id}</span>
            </div>

            <div className="grid grid-cols-3 gap-3 text-sm">
              <div className="kb-card p-3 text-center">
                <div className="text-2xl font-bold text-kb-primary">{result.documents_seen}</div>
                <div className="text-xs text-kb-muted mt-1">Documents seen</div>
              </div>
              <div className="kb-card p-3 text-center">
                <div className="text-2xl font-bold text-kb-primary">{result.documents_indexed}</div>
                <div className="text-xs text-kb-muted mt-1">Indexed</div>
              </div>
              <div className="kb-card p-3 text-center">
                <div className="text-2xl font-bold text-kb-primary">{result.chunks_indexed}</div>
                <div className="text-xs text-kb-muted mt-1">Chunks</div>
              </div>
            </div>

            {result.error_message && (
              <div className="mt-3 text-red-400 text-xs">{result.error_message}</div>
            )}
          </div>
        )}
      </div>

      {history.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-kb-muted mb-2">Recent runs (this session)</h2>
          <div className="space-y-1">
            {history.map((h) => (
              <div key={h.run_id} className="kb-card p-3 text-sm flex items-center justify-between">
                <span className="font-mono text-xs text-kb-muted truncate max-w-xs">{h.run_id}</span>
                <div className="flex gap-4 text-xs text-kb-muted shrink-0">
                  <span>{h.documents_indexed} docs</span>
                  <span>{h.chunks_indexed} chunks</span>
                  <span className={h.status === 'completed' ? 'text-green-400' : 'text-red-400'}>{h.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
