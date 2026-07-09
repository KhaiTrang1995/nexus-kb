import { useState, useEffect, useRef, useCallback } from 'react'
import { authHeaders, authHeadersForUpload } from '../../lib/auth'

interface Workspace {
  id: string
  name: string
  slug: string
}

interface UploadJobSummary {
  job_id: string
  original_filename: string
  status: string
}

interface DuplicateNotice {
  original_filename: string
  raw_content_hash: string
  existing_document_id: string
  existing_document_title: string
}

interface UploadResponse {
  jobs: UploadJobSummary[]
  rejected: string[]
  duplicates: DuplicateNotice[]
}

interface JobStatus {
  id: string
  original_filename: string
  status: 'queued' | 'extracting' | 'indexed' | 'failed'
  attempt: number
  max_attempts: number
  error_message?: string | null
  document_id?: string | null
  queue_position?: number | null
}

const TERMINAL_STATUSES = new Set(['indexed', 'failed'])

export default function UploadPanel({ currentUser }: {
  currentUser: { id: string; name: string; role: string; is_admin?: boolean; workspace_ids?: string[] } | null
}) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [workspaceId, setWorkspaceId] = useState('')
  const [workspaceError, setWorkspaceError] = useState<string | null>(null)

  const [files, setFiles] = useState<File[]>([])
  const pendingFiles = useRef<Map<string, File>>(new Map())

  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [rejected, setRejected] = useState<string[]>([])
  const [duplicates, setDuplicates] = useState<DuplicateNotice[]>([])
  const [jobs, setJobs] = useState<JobStatus[]>([])
  const [ackMessages, setAckMessages] = useState<Record<string, string>>({})

  useEffect(() => {
    let cancelled = false
    const loadWorkspaces = async () => {
      try {
        const res = await fetch('/api/v1/workspaces', { headers: authHeaders() })
        if (!res.ok) return
        const data = await res.json()
        if (!cancelled) {
          setWorkspaces(data.workspaces || [])
          if (data.workspaces?.length > 0) setWorkspaceId(data.workspaces[0].id)
        }
      } catch {
        // Silent -- the workspace picker just stays empty.
      }
    }
    loadWorkspaces()
    return () => { cancelled = true }
  }, [])

  const pollJob = useCallback(async (jobId: string) => {
    const res = await fetch(`/api/v1/jobs/${jobId}`, { headers: authHeaders() })
    if (!res.ok) return null
    return (await res.json()) as JobStatus
  }, [])

  useEffect(() => {
    const activeIds = jobs.filter(j => !TERMINAL_STATUSES.has(j.status)).map(j => j.id)
    if (activeIds.length === 0) return
    const interval = setInterval(async () => {
      const updates = await Promise.all(activeIds.map(pollJob))
      setJobs(prev => prev.map(job => {
        const updated = updates.find(u => u && u.id === job.id)
        return updated || job
      }))
    }, 2000)
    return () => clearInterval(interval)
  }, [jobs, pollJob])

  const doUpload = async (uploadFiles: File[], confirmVersionOf?: string) => {
    if (!workspaceId) {
      setWorkspaceError('No workspace available. Ask an admin to add you to one.')
      return
    }
    setUploading(true)
    setUploadError(null)
    try {
      const form = new FormData()
      form.set('workspace_id', workspaceId)
      if (confirmVersionOf) form.set('confirm_version_of', confirmVersionOf)
      for (const file of uploadFiles) form.append('files', file)

      const res = await fetch('/api/v1/documents', {
        method: 'POST',
        headers: authHeadersForUpload(),
        body: form,
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail || `HTTP ${res.status}`)
      }
      const data: UploadResponse = await res.json()
      setRejected(prev => [...prev, ...data.rejected])
      // When confirming a version, `duplicates` state was already cleared by
      // confirmVersion() before calling doUpload -- a fresh upload can still
      // surface new duplicates against other files in the same batch.
      if (data.duplicates.length > 0) setDuplicates(prev => [...prev, ...data.duplicates])
      setJobs(prev => [
        ...data.jobs.map(j => ({
          id: j.job_id, original_filename: j.original_filename,
          status: j.status as JobStatus['status'], attempt: 0, max_attempts: 3,
        })),
        ...prev,
      ])
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }

  const handleSubmit = async () => {
    if (files.length === 0) {
      setUploadError('Choose at least one file.')
      return
    }
    setRejected([])
    setDuplicates([])
    for (const file of files) pendingFiles.current.set(file.name, file)
    await doUpload(files)
    setFiles([])
  }

  const confirmVersion = async (dup: DuplicateNotice) => {
    const file = pendingFiles.current.get(dup.original_filename)
    if (!file) return
    setDuplicates(prev => prev.filter(d => d.original_filename !== dup.original_filename))
    await doUpload([file], dup.existing_document_id)
  }

  const dismissDuplicate = (dup: DuplicateNotice) => {
    setDuplicates(prev => prev.filter(d => d.original_filename !== dup.original_filename))
    pendingFiles.current.delete(dup.original_filename)
  }

  const ackDocument = async (job: JobStatus) => {
    if (!job.document_id) return
    try {
      const res = await fetch(`/api/v1/documents/${job.document_id}/ack`, {
        method: 'POST',
        headers: authHeaders(),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail || `HTTP ${res.status}`)
      }
      setAckMessages(prev => ({ ...prev, [job.id]: 'Confirmed -- now visible in search for your workspace.' }))
    } catch (e: unknown) {
      setAckMessages(prev => ({ ...prev, [job.id]: e instanceof Error ? e.message : 'Could not confirm.' }))
    }
  }

  const retryJob = async (job: JobStatus) => {
    const res = await fetch(`/api/v1/jobs/${job.id}/retry`, { method: 'POST', headers: authHeaders() })
    if (!res.ok) return
    const updated = await res.json()
    setJobs(prev => prev.map(j => (j.id === job.id ? updated : j)))
  }

  const statusBadge = (status: string) => {
    const cls = status === 'indexed' ? 'bg-green-500/20 text-green-400'
      : status === 'failed' ? 'bg-red-500/20 text-red-400'
      : 'bg-yellow-500/20 text-yellow-400'
    return <span className={`text-[10px] px-2 py-0.5 rounded ${cls}`}>{status}</span>
  }

  return (
    <div>
      {!currentUser?.is_admin && (currentUser?.workspace_ids?.length ?? 0) === 0 && (
        <div className="mb-4 text-amber-400 text-sm border border-amber-400/30 rounded px-3 py-2">
          You don't belong to any workspace yet. Ask an admin to add you before uploading.
        </div>
      )}

      <div className="kb-card p-5 mb-5 max-w-2xl">
        <div className="flex flex-col gap-3">
          <div>
            <label className="text-xs text-kb-muted block mb-1">Workspace</label>
            <select
              value={workspaceId}
              onChange={e => setWorkspaceId(e.target.value)}
              className="w-full bg-kb-dark border border-kb-primary/30 rounded px-3 py-2 text-sm"
            >
              {workspaces.length === 0 && <option value="">No workspace available</option>}
              {workspaces.map(w => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
            {workspaceError && <div className="text-red-400 text-xs mt-1">{workspaceError}</div>}
          </div>

          <div>
            <label className="text-xs text-kb-muted block mb-1">Files (PDF, DOCX, XLSX, PPTX, CSV, MD, TXT)</label>
            <input
              type="file"
              multiple
              onChange={e => setFiles(Array.from(e.target.files || []))}
              className="w-full text-sm"
            />
          </div>

          <button
            onClick={handleSubmit}
            disabled={uploading || files.length === 0}
            className="kb-btn kb-btn-primary w-fit disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
        </div>

        {uploadError && (
          <div className="mt-3 text-red-400 text-sm border border-red-400/30 rounded px-3 py-2">{uploadError}</div>
        )}

        {rejected.length > 0 && (
          <div className="mt-3 text-xs text-amber-400">
            {rejected.map((r, i) => <div key={i}>{r}</div>)}
          </div>
        )}

        {duplicates.map(dup => (
          <div key={dup.original_filename} className="mt-3 text-xs border border-amber-400/30 rounded px-3 py-2">
            <div className="mb-2">
              <strong>{dup.original_filename}</strong> matches an existing document
              (<em>{dup.existing_document_title}</em>). Create a new version?
            </div>
            <div className="flex gap-2">
              <button onClick={() => confirmVersion(dup)} className="kb-btn kb-btn-primary text-[11px] py-1">
                Create version
              </button>
              <button onClick={() => dismissDuplicate(dup)} className="kb-btn border border-kb-primary/30 text-[11px] py-1">
                Cancel
              </button>
            </div>
          </div>
        ))}
      </div>

      {jobs.length > 0 && (
        <div className="max-w-2xl">
          <h2 className="text-sm font-semibold text-kb-muted mb-2">Upload queue</h2>
          <div className="kb-card divide-y divide-kb-primary/10">
            {jobs.map(job => (
              <div key={job.id} className="p-3 text-xs flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <span className="font-mono truncate max-w-[16rem]">{job.original_filename}</span>
                  {statusBadge(job.status)}
                </div>
                {job.status === 'queued' && job.queue_position != null && (
                  <div className="text-kb-muted">Dang cho trong hang doi (vi tri {job.queue_position}).</div>
                )}
                {job.status === 'extracting' && <div className="text-kb-muted">Dang nap du lieu...</div>}
                {job.status === 'failed' && (
                  <div className="flex items-center justify-between">
                    <span className="text-red-400">{job.error_message || 'Trich xuat that bai.'}</span>
                    <button onClick={() => retryJob(job)} className="kb-btn border border-kb-primary/30 text-[10px] py-0.5">
                      Retry
                    </button>
                  </div>
                )}
                {job.status === 'indexed' && !ackMessages[job.id] && (
                  <div className="flex items-center justify-between">
                    <span className="text-kb-muted">Da xu ly xong, cho ban xac nhan da doc.</span>
                    <button onClick={() => ackDocument(job)} className="kb-btn kb-btn-primary text-[10px] py-0.5">
                      Confirm read
                    </button>
                  </div>
                )}
                {ackMessages[job.id] && <div className="text-green-400">{ackMessages[job.id]}</div>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
