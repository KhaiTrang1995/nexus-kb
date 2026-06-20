import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import GraphView from './GraphView'
import { renderWithProviders, mockUser } from '../../test/utils'

const buildResult = {
  entities: [
    {
      id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      name: 'Nexus-KB',
      entity_type: 'TERM',
      confidence: 0.9,
    },
    {
      id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      name: 'Qdrant',
      entity_type: 'TECHNOLOGY',
      confidence: 0.85,
    },
  ],
  relationships: [
    {
      id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
      source_entity_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      target_entity_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      relationship_type: 'USES',
      confidence: 0.88,
    },
  ],
  hyperedges: [],
}

describe('GraphView', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => buildResult,
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('POSTs to /api/v1/graph/build with limit query param when Build Graph clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <GraphView canBuild={true} currentUser={mockUser.reviewer} />,
    )

    await user.click(screen.getByRole('button', { name: /build graph/i }))

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/v1/graph/build?limit=50',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'X-User-Role': 'Reviewer',
            'X-User-Id': 'u2',
          }),
        }),
      )
    })
  })

  it('renders entity and relationship counts after successful build', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <GraphView canBuild={true} currentUser={mockUser.reviewer} />,
    )

    await user.click(screen.getByRole('button', { name: /build graph/i }))

    await waitFor(() => {
      expect(screen.getByText(/Entities:/)).toBeInTheDocument()
      expect(screen.getByText('2')).toBeInTheDocument()
      expect(screen.getByText(/Relationships:/)).toBeInTheDocument()
    })
  })

  it('disables build button when canBuild is false (Searcher role)', () => {
    renderWithProviders(
      <GraphView canBuild={false} currentUser={mockUser.searcher} />,
    )

    const btn = screen.getByRole('button', { name: /build graph/i })
    expect(btn).toBeDisabled()
    expect(screen.getByText(/permission required/i)).toBeInTheDocument()
  })

  it('shows API error detail when build fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'graph build failed' }),
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(
      <GraphView canBuild={true} currentUser={mockUser.auditor} />,
    )

    await user.click(screen.getByRole('button', { name: /build graph/i }))

    await waitFor(() => {
      expect(screen.getByText('graph build failed')).toBeInTheDocument()
    })
  })

  it('allows Auditor role to trigger build (frontend RBAC)', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <GraphView canBuild={true} currentUser={mockUser.auditor} />,
    )

    const btn = screen.getByRole('button', { name: /build graph/i })
    expect(btn).not.toBeDisabled()
    await user.click(btn)

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/graph/build'),
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })
})