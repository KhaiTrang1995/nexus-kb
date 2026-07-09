import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import UploadPanel from './UploadPanel'
import { renderWithProviders } from '../../test/utils'

const workspace = { id: 'ws-1', name: 'Engineering', slug: 'engineering' }
const adminUser = { id: 'root', name: 'Root', role: 'Auditor', is_admin: true, workspace_ids: [] }
const memberUser = { id: 'u1', name: 'Alice', role: '', is_admin: false, workspace_ids: ['ws-1'] }

function mockFetchSequence(handlers: Record<string, () => unknown>) {
  return vi.fn((url: string) => {
    for (const [pattern, handler] of Object.entries(handlers)) {
      if (url.includes(pattern)) {
        return Promise.resolve({ ok: true, json: async () => handler() })
      }
    }
    return Promise.resolve({ ok: true, json: async () => ({}) })
  })
}

function makeFile(name: string, content = 'hello world'): File {
  return new File([content], name, { type: 'text/plain' })
}

describe('UploadPanel', () => {
  beforeEach(() => {
    localStorage.setItem('nexus-jwt', 'test-token')
  })

  afterEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('warns when the user has no workspace membership', async () => {
    vi.stubGlobal('fetch', mockFetchSequence({ '/api/v1/workspaces': () => ({ workspaces: [] }) }))
    renderWithProviders(<UploadPanel currentUser={{ ...memberUser, workspace_ids: [] }} />)

    await waitFor(() => {
      expect(screen.getByText(/don't belong to any workspace/i)).toBeInTheDocument()
    })
  })

  it('loads workspaces and uploads selected files with the chosen workspace_id', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence({
        '/api/v1/workspaces': () => ({ workspaces: [workspace] }),
        '/api/v1/documents': () => ({
          jobs: [{ job_id: 'job-1', original_filename: 'a.txt', status: 'queued' }],
          rejected: [],
          duplicates: [],
        }),
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<UploadPanel currentUser={memberUser} />)

    await waitFor(() => {
      expect(screen.getByText('Engineering')).toBeInTheDocument()
    })

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(fileInput, makeFile('a.txt'))
    await user.click(screen.getByRole('button', { name: /^upload$/i }))

    await waitFor(() => {
      expect(screen.getByText('a.txt')).toBeInTheDocument()
      expect(screen.getByText('queued')).toBeInTheDocument()
    })

    const uploadCall = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.find(
      call => call[0] === '/api/v1/documents',
    )
    expect(uploadCall).toBeTruthy()
    expect(uploadCall![1].method).toBe('POST')
    const formData = uploadCall![1].body as FormData
    expect(formData.get('workspace_id')).toBe('ws-1')
  })

  it('shows rejected files without creating a job for them', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence({
        '/api/v1/workspaces': () => ({ workspaces: [workspace] }),
        '/api/v1/documents': () => ({
          jobs: [],
          rejected: ['virus.exe: dinh dang khong duoc ho tro'],
          duplicates: [],
        }),
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<UploadPanel currentUser={memberUser} />)
    await waitFor(() => expect(screen.getByText('Engineering')).toBeInTheDocument())

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(fileInput, makeFile('virus.exe'))
    await user.click(screen.getByRole('button', { name: /^upload$/i }))

    await waitFor(() => {
      expect(screen.getByText(/dinh dang khong duoc ho tro/i)).toBeInTheDocument()
    })
  })

  it('prompts for a new version on duplicate and re-submits with confirm_version_of', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence({
        '/api/v1/workspaces': () => ({ workspaces: [workspace] }),
        '/api/v1/documents': () => ({
          jobs: [],
          rejected: [],
          duplicates: [{
            original_filename: 'a.txt', raw_content_hash: 'hash1',
            existing_document_id: 'doc-1', existing_document_title: 'Existing A',
          }],
        }),
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<UploadPanel currentUser={memberUser} />)
    await waitFor(() => expect(screen.getByText('Engineering')).toBeInTheDocument())

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(fileInput, makeFile('a.txt'))
    await user.click(screen.getByRole('button', { name: /^upload$/i }))

    await waitFor(() => {
      expect(screen.getByText(/Existing A/i)).toBeInTheDocument()
    })

    vi.stubGlobal(
      'fetch',
      mockFetchSequence({
        '/api/v1/documents': () => ({
          jobs: [{ job_id: 'job-2', original_filename: 'a.txt', status: 'queued' }],
          rejected: [], duplicates: [],
        }),
      }),
    )

    await user.click(screen.getByRole('button', { name: /create version/i }))

    await waitFor(() => {
      const call = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.find(c => c[0] === '/api/v1/documents')
      expect(call).toBeTruthy()
      const formData = call![1].body as FormData
      expect(formData.get('confirm_version_of')).toBe('doc-1')
    })
  })

  it('polls job status, then lets the uploader confirm they read an indexed document', async () => {
    let jobPollCount = 0
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string, options?: RequestInit) => {
        if (url.includes('/api/v1/workspaces')) {
          return Promise.resolve({ ok: true, json: async () => ({ workspaces: [workspace] }) })
        }
        if (url === '/api/v1/documents' && options?.method === 'POST') {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              jobs: [{ job_id: 'job-1', original_filename: 'a.txt', status: 'queued' }],
              rejected: [], duplicates: [],
            }),
          })
        }
        if (url === '/api/v1/jobs/job-1') {
          jobPollCount += 1
          return Promise.resolve({
            ok: true,
            json: async () => ({
              id: 'job-1', original_filename: 'a.txt', status: 'indexed',
              attempt: 1, max_attempts: 3, document_id: 'doc-9',
            }),
          })
        }
        if (url === '/api/v1/documents/doc-9/ack' && options?.method === 'POST') {
          return Promise.resolve({ ok: true, json: async () => ({ document_id: 'doc-9', acked_by: 'root' }) })
        }
        return Promise.resolve({ ok: true, json: async () => ({}) })
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<UploadPanel currentUser={adminUser} />)
    await waitFor(() => expect(screen.getByText('Engineering')).toBeInTheDocument())

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(fileInput, makeFile('a.txt'))
    await user.click(screen.getByRole('button', { name: /^upload$/i }))

    await waitFor(() => expect(screen.getByText('queued')).toBeInTheDocument())

    const ackButton = await screen.findByRole('button', { name: /confirm read/i }, { timeout: 5000 })
    expect(jobPollCount).toBeGreaterThan(0)

    await user.click(ackButton)

    await waitFor(() => {
      expect(screen.getByText(/now visible in search/i)).toBeInTheDocument()
    })
  })
})
