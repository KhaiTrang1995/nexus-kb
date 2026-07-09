import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AuditView from './AuditView'
import { renderWithProviders } from '../../test/utils'

const auditRecords = [
  {
    id: '11111111-1111-1111-1111-111111111111',
    actor_id: 'u2',
    action: 'SEARCH_QUERY',
    status: 'SUCCESS',
    details: { query: 'governed retrieval' },
    created_at: new Date().toISOString(),
  },
  {
    id: '22222222-2222-2222-2222-222222222222',
    actor_id: 'pipeline',
    action: 'INGEST_START',
    status: 'SUCCESS',
    details: { source_path: '/docs' },
    created_at: new Date(Date.now() - 120_000).toISOString(),
  },
]

describe('AuditView', () => {
  beforeEach(() => {
    localStorage.setItem('nexus-jwt', 'test-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => auditRecords,
      }),
    )
  })

  afterEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('auto-loads audit log on mount and renders table rows with action pills', async () => {
    renderWithProviders(
      <AuditView canAdvanced={false} />,
    )

    expect(screen.getByText('Audit Log')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('SEARCH_QUERY')).toBeInTheDocument()
      expect(screen.getByText('INGEST_START')).toBeInTheDocument()
    })

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/audit?'),
      expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          'Authorization': 'Bearer test-token',
        }),
      }),
    )
  })

  it('shows action filter pills and refetches when filter changes', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <AuditView canAdvanced={false} />,
    )

    await waitFor(() => screen.getByText('SEARCH_QUERY'))
    await user.click(screen.getByRole('button', { name: /graph write/i }))

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('action_filter=GRAPH_WRITE'),
        expect.any(Object),
      )
    })
  })

  it('shows actor filter only for Auditor (canAdvanced)', async () => {
    renderWithProviders(
      <AuditView canAdvanced={true} />,
    )

    expect(screen.getByPlaceholderText(/filter by actor/i)).toBeInTheDocument()
  })

  it('displays error state with retry when fetch fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 503 }),
    )

    renderWithProviders(
      <AuditView canAdvanced={false} />,
    )

    await waitFor(() => {
      expect(screen.getByText(/HTTP 503/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
    })
  })

  it('expands row to show details on click', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <AuditView canAdvanced={false} />,
    )

    await waitFor(() => screen.getByText('SEARCH_QUERY'))
    await user.click(screen.getByText('SEARCH_QUERY').closest('tr')!)

    expect(screen.getByText(/governed retrieval/)).toBeInTheDocument()
  })
})