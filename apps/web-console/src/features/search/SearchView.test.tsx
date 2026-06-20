import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SearchView from './SearchView'
import { renderWithProviders, mockUser } from '../../test/utils'

const entityA = {
  id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  name: 'Nexus-KB',
  entity_type: 'TERM',
  confidence: 0.92,
  provenance: {},
}
const entityB = {
  id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  name: 'Qdrant',
  entity_type: 'TECHNOLOGY',
  confidence: 0.88,
  provenance: {},
}

const searchResponse = {
  query: 'governed retrieval',
  results: [
    {
      chunk_id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
      document_id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
      title: 'Governed Retrieval Guide',
      source_path: '/vault/retrieval.md',
      score: 0.91,
      vector_score: 0.85,
      snippet: 'Governed <em>retrieval</em> in enterprise',
      content: 'Full content about governed retrieval and Qdrant.',
      tags: ['rag'],
      wikilinks: [],
      metadata: { confidence: 0.9 },
      graph_entities: [entityA, entityB],
      graph_relationships: [
        {
          id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
          source_entity_id: entityA.id,
          target_entity_id: entityB.id,
          relationship_type: 'USES',
          confidence: 0.87,
          provenance: {},
        },
      ],
    },
  ],
}

describe('SearchView graph panel', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('/api/v1/graph/stats')) {
          return Promise.resolve({ ok: true, json: async () => ({ node_count: 42 }) })
        }
        if (url.includes('/api/v1/review/queue')) {
          return Promise.resolve({ ok: true, json: async () => [] })
        }
        if (url.includes('/api/v1/search')) {
          return Promise.resolve({ ok: true, json: async () => searchResponse })
        }
        return Promise.resolve({ ok: false, status: 404 })
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders search results and opens graph panel with entity badges grouped by type', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SearchView currentUser={mockUser.searcher} />)

    await waitFor(() => {
      expect(screen.getByText('Governed Retrieval Guide')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Governed Retrieval Guide'))

    await waitFor(() => {
      expect(screen.getByText('Graph context')).toBeInTheDocument()
      expect(screen.getByText('TERM')).toBeInTheDocument()
      expect(screen.getByText('TECHNOLOGY')).toBeInTheDocument()
      expect(screen.getAllByText('Nexus-KB').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('Qdrant').length).toBeGreaterThanOrEqual(1)
    })
  })

  it('renders readable relationship arrows with entity names and confidence', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SearchView currentUser={mockUser.searcher} />)

    await waitFor(() => screen.getByText('Governed Retrieval Guide'))
    await user.click(screen.getByText('Governed Retrieval Guide'))

    await waitFor(() => {
      expect(screen.getByText('—USES→')).toBeInTheDocument()
      expect(screen.getByText(/conf 0\.87/)).toBeInTheDocument()
    })
  })

  it('shows graph node count from /api/v1/graph/stats in stats bar', async () => {
    renderWithProviders(<SearchView currentUser={mockUser.searcher} />)

    await waitFor(() => {
      expect(screen.getByText('Graph nodes')).toBeInTheDocument()
      expect(screen.getByText('42')).toBeInTheDocument()
    })
  })

  it('shows search error when API returns non-OK', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('/api/v1/graph/stats') || url.includes('/api/v1/review/queue')) {
          return Promise.resolve({ ok: true, json: async () => ({ node_count: 0 }) })
        }
        return Promise.resolve({ ok: false, status: 500 })
      }),
    )

    renderWithProviders(<SearchView currentUser={mockUser.searcher} />)

    await waitFor(() => {
      expect(screen.getByText(/Search failed: 500/i)).toBeInTheDocument()
    })
  })
})