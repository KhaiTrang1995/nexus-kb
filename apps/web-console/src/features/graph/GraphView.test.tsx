import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import GraphView from './GraphView'
import { renderWithProviders } from '../../test/utils'

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
    localStorage.setItem('nexus-jwt', 'test-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => buildResult,
      }),
    )
  })

  afterEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('POSTs to /api/v1/graph/build with limit query param when Build Graph clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <GraphView canBuild={true} />,
    )

    await user.click(screen.getByRole('button', { name: /build graph/i }))

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/v1/graph/build?limit=50',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            'Authorization': 'Bearer test-token',
          }),
        }),
      )
    })
  })

  it('renders entity and relationship counts after successful build', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <GraphView canBuild={true} />,
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
      <GraphView canBuild={false} />,
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
      <GraphView canBuild={true} />,
    )

    await user.click(screen.getByRole('button', { name: /build graph/i }))

    await waitFor(() => {
      expect(screen.getByText('graph build failed')).toBeInTheDocument()
    })
  })

  it('allows Auditor role to trigger build (frontend RBAC)', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <GraphView canBuild={true} />,
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

  it('loads the existing graph via GET /api/v1/graph/view on mount without rebuilding', async () => {
    renderWithProviders(
      <GraphView canBuild={true} />,
    )

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/graph/view'),
        expect.objectContaining({ headers: expect.anything() }),
      )
    })
  })

  it('searches nodes by name and focuses on the selected result', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.includes('/graph/entities/search')) {
          return Promise.resolve({
            ok: true,
            json: async () => [
              { id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', name: 'Nexus-KB', entity_type: 'TERM', confidence: 0.9 },
            ],
          })
        }
        if (url.includes('/neighbors')) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ entities: buildResult.entities, relationships: buildResult.relationships }),
          })
        }
        return Promise.resolve({ ok: true, json: async () => buildResult })
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(
      <GraphView canBuild={true} />,
    )

    const searchInput = screen.getByPlaceholderText(/search entity by name/i)
    await user.type(searchInput, 'Nexus')

    const resultButton = await screen.findByRole('button', { name: /Nexus-KB/i })

    await user.click(resultButton)

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/graph/entities/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/neighbors'),
        expect.anything(),
      )
    })
  })

  it('shows node content in the side panel after clicking a node in the canvas', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.includes('/context')) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              entity: { id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', name: 'Nexus-KB', entity_type: 'TERM', confidence: 0.9 },
              chunks: [
                {
                  chunk_id: 'c1', document_id: 'd1', document_title: 'Nexus Overview',
                  source_path: '/vault/Nexus.md', content: 'Nexus-KB is a governed retrieval platform.',
                },
              ],
            }),
          })
        }
        return Promise.resolve({ ok: true, json: async () => buildResult })
      }),
    )

    renderWithProviders(
      <GraphView canBuild={true} />,
    )

    await waitFor(() => {
      expect(document.querySelector('circle')).toBeTruthy()
    })

    const circle = document.querySelector('circle')!
    fireEvent.mouseDown(circle.parentElement!)
    fireEvent.mouseUp(document.querySelector('svg')!)

    await waitFor(() => {
      expect(screen.getByText('Nexus Overview')).toBeInTheDocument()
      expect(screen.getByText(/governed retrieval platform/i)).toBeInTheDocument()
    })
  })
})