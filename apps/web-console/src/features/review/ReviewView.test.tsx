import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ReviewView from './ReviewView'
import { renderWithProviders, mockUser } from '../../test/utils'

const reviewItems = [
  {
    id: '11111111-1111-1111-1111-111111111111',
    run_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    source_path: '/docs/architecture.md',
    content: 'This chunk has low confidence and needs review.',
    confidence: 0.42,
    status: 'PENDING',
    reviewer_id: null,
    reviewed_at: null,
    created_at: new Date().toISOString(),
  },
  {
    id: '22222222-2222-2222-2222-222222222222',
    run_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    source_path: '/docs/security.md',
    content: 'Another pending chunk for review.',
    confidence: 0.35,
    status: 'PENDING',
    reviewer_id: null,
    reviewed_at: null,
    created_at: new Date(Date.now() - 60_000).toISOString(),
  },
]

describe('ReviewView', () => {
  beforeEach(() => {
    localStorage.setItem('nexus-jwt', 'test-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => reviewItems,
      }),
    )
  })

  afterEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('loads and renders review queue items on mount', async () => {
    renderWithProviders(<ReviewView currentUser={mockUser.reviewer} />)

    expect(screen.getByText('Review Queue')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('/docs/architecture.md')).toBeInTheDocument()
      expect(screen.getByText('/docs/security.md')).toBeInTheDocument()
    })
  })

  it('sends Bearer token in fetch headers', async () => {
    renderWithProviders(<ReviewView currentUser={mockUser.reviewer} />)

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/review/queue'),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Authorization': 'Bearer test-token',
          }),
        }),
      )
    })
  })

  it('shows role warning when user is not a Reviewer', () => {
    renderWithProviders(<ReviewView currentUser={mockUser.searcher} />)

    expect(screen.getByText(/Switch to "Reviewer" role/i)).toBeInTheDocument()
  })

  it('opens detail panel when item is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReviewView currentUser={mockUser.reviewer} />)

    await waitFor(() => screen.getByText('/docs/architecture.md'))
    await user.click(screen.getByText('/docs/architecture.md'))

    expect(screen.getByText('Review Item')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveValue(
      'This chunk has low confidence and needs review.',
    )
  })

  it('calls approve action and removes item from queue', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => reviewItems })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          item_id: '11111111-1111-1111-1111-111111111111',
          status: 'APPROVED',
        }),
      })
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    renderWithProviders(<ReviewView currentUser={mockUser.reviewer} />)

    await waitFor(() => screen.getByText('/docs/architecture.md'))
    await user.click(screen.getByText('/docs/architecture.md'))
    await user.click(screen.getByRole('button', { name: /approve/i }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/v1/review/action',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"action":"APPROVE"'),
        }),
      )
    })
  })

  it('displays error on fetch failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Internal error' }),
      }),
    )

    renderWithProviders(<ReviewView currentUser={mockUser.reviewer} />)

    await waitFor(() => {
      expect(screen.getByText('Internal error')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
    })
  })

  it('shows empty state when queue has no items', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [],
      }),
    )

    renderWithProviders(<ReviewView currentUser={mockUser.reviewer} />)

    await waitFor(() => {
      expect(screen.getByText(/Queue is empty/i)).toBeInTheDocument()
    })
  })
})
