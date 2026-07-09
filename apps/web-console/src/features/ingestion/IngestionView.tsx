import { useState } from 'react'
import { authHeaders } from '../../lib/auth'
import UploadPanel from './UploadPanel'

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

type IngestTab = 'upload' | 'path'

export default function IngestionView({ currentUser }: { currentUser: { id: string; name: string; role: string; is_admin?: boolean; workspace_ids?: string[] } | null }) {
  // Default tab stays 'path' (the pre-existing server-side scan flow) so the
  // primary workflow doesn't change out from under existing users/tests;
  // "Upload files" is the new E2/E3/E5-backed flow, additive.
  const [tab, setTab] = useState<IngestTab>('path')

  const [sourcePath, setSourcePath] = useState('')
  const [sourceType, setSourceType] = useState('local_file')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<IngestionResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<IngestionResult[]>([])

  const role = currentUser?.role || ''
  const canIngest = role === 'Reviewer' || role === 'Auditor'

  const runIngestion = async () => {
    if (!sourcePath.trim()) {
      setError('Source path is required.')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const res = await fetch('/api/v1/ingest', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ source_path: sourcePath.trim(), source_type: sourceType }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail || `HTTP ${res.status}`)
      }
      const data: IngestionResult = await res.json()
      setResult(data)
      setHistory(h => [data, ...h].slice(0, 10))
      setSourcePath('')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Ingestion failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold mb-1">Document Ingestion</h1>
      <p className="text-kb-muted text-xs mb-4">
        Upload files into your workspace, or ingest from a server-side path.
      </p>

      <div className="flex border-b border-kb-primary/10 mb-4">
        {([
          { key: 'upload' as const, label: 'Upload Files' },
          { key: 'path' as const, label: 'Server Path' },
        ]).map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`tab-btn ${tab === t.key ? 'active' : ''}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'upload' && <UploadPanel currentUser={currentUser} />}

      {tab === 'path' && (
        <div>
      {!canIngest && (
        <div className="mb-4 text-amber-400 text-sm border border-amber-400/30 rounded px-3 py-2">
          Switch to Reviewer or Auditor role to run ingestion.
        </div>
      )}

      <div className="kb-card p-5 mb-5 max-w-2xl">
        <div className="flex flex-col gap-3">
          <div>
            <label className="text-xs text-kb-muted block mb-1">Source type</label>
            <select
              value={sourceType}
              onChange={e => setSourceType(e.target.value)}
              disabled={!canIngest || loading}
              className="w-full bg-kb-dark border border-kb-primary/30 rounded px-3 py-2 text-sm"
            >
              {SOURCE_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs text-kb-muted block mb-1">Source path</label>
            <input
              type="text"
              value={sourcePath}
              onChange={e => setSourcePath(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && canIngest && !loading && runIngestion()}
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
            {loading ? 'Ingesting...' : 'Run Ingestion'}
          </button>
        </div>

        {error && (
          <div className="mt-3 text-red-400 text-sm border border-red-400/30 rounded px-3 py-2">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-4 border border-kb-primary/30 rounded p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className={`text-xs px-2 py-0.5 rounded ${result.status === 'completed' ? 'bg-green-500/20 text-green-400' : result.status === 'failed' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                {result.status.toUpperCase()}
              </span>
              <span className="text-xs text-kb-muted font-mono">{result.run_id}</span>
            </div>

            <div className="grid grid-cols-3 gap-3 text-sm">
              <div className="kb-card p-3 text-center">
                <div className="text-2xl font-bold text-kb-primary">{result.documents_seen}</div>
                <div className="text-[10px] text-kb-muted mt-1">Documents seen</div>
              </div>
              <div className="kb-card p-3 text-center">
                <div className="text-2xl font-bold text-kb-primary">{result.documents_indexed}</div>
                <div className="text-[10px] text-kb-muted mt-1">Indexed</div>
              </div>
              <div className="kb-card p-3 text-center">
                <div className="text-2xl font-bold text-kb-primary">{result.chunks_indexed}</div>
                <div className="text-[10px] text-kb-muted mt-1">Chunks</div>
              </div>
            </div>

            {result.error_message && (
              <div className="mt-3 text-red-400 text-xs">{result.error_message}</div>
            )}
          </div>
        )}
      </div>

      {history.length > 0 && (
        <div className="max-w-2xl">
          <h2 className="text-sm font-semibold text-kb-muted mb-2">Recent runs</h2>
          <div className="kb-card overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-kb-primary/20 text-kb-muted">
                  <th className="text-left px-3 py-2">Run ID</th>
                  <th className="text-right px-3 py-2">Docs</th>
                  <th className="text-right px-3 py-2">Chunks</th>
                  <th className="text-right px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {history.map(h => (
                  <tr key={h.run_id} className="border-b border-kb-primary/10">
                    <td className="px-3 py-2 font-mono text-kb-muted truncate max-w-[12rem]">{h.run_id}</td>
                    <td className="px-3 py-2 text-right">{h.documents_indexed}</td>
                    <td className="px-3 py-2 text-right">{h.chunks_indexed}</td>
                    <td className="px-3 py-2 text-right">
                      <span className={h.status === 'completed' ? 'text-green-400' : 'text-red-400'}>{h.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
        </div>
      )}
    </div>
  )
}
