import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import IngestionView from './IngestionView'
import { renderWithProviders, mockUser } from '../../test/utils'

const ingestResult = {
  run_id: '11111111-1111-1111-1111-111111111111',
  status: 'completed',
  documents_seen: 3,
  documents_indexed: 3,
  chunks_indexed: 12,
  error_message: null,
}

describe('IngestionView', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ingestResult,
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('POSTs form payload to /api/v1/ingest on submit', async () => {
    const user = userEvent.setup()
    renderWithProviders(<IngestionView currentUser={mockUser.reviewer} />)

    const pathInput = screen.getByPlaceholderText(/path\/to\/documents/i)
    await user.type(pathInput, 'D:\\docs\\vault')
    await user.click(screen.getByRole('button', { name: /run ingestion/i }))

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/v1/ingest',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            'X-User-Role': 'Reviewer',
            'X-User-Id': 'u2',
          }),
          body: JSON.stringify({
            source_path: 'D:\\docs\\vault',
            source_type: 'local_file',
          }),
        }),
      )
    })
  })

  it('renders ingestion result metrics after successful submit', async () => {
    const user = userEvent.setup()
    renderWithProviders(<IngestionView currentUser={mockUser.reviewer} />)

    await user.type(screen.getByPlaceholderText(/path\/to\/documents/i), '/tmp/docs')
    await user.click(screen.getByRole('button', { name: /run ingestion/i }))

    await waitFor(() => {
      expect(screen.getByText('COMPLETED')).toBeInTheDocument()
      expect(screen.getByText(/Documents seen/i)).toBeInTheDocument()
      expect(screen.getByText('Indexed')).toBeInTheDocument()
      expect(screen.getByText('Chunks')).toBeInTheDocument()
      const metrics = screen.getAllByText('12')
      expect(metrics.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('blocks Searcher role with warning and disabled controls', () => {
    renderWithProviders(<IngestionView currentUser={mockUser.searcher} />)

    expect(screen.getByText(/Switch to Reviewer or Auditor/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /run ingestion/i })).toBeDisabled()
  })

  it('validates empty source path client-side', async () => {
    const user = userEvent.setup()
    renderWithProviders(<IngestionView currentUser={mockUser.reviewer} />)

    await user.click(screen.getByRole('button', { name: /run ingestion/i }))

    expect(screen.getByText('Source path is required.')).toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('shows API error detail on failed ingest', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'source path not found' }),
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<IngestionView currentUser={mockUser.auditor} />)

    await user.type(screen.getByPlaceholderText(/path\/to\/documents/i), '/missing')
    await user.click(screen.getByRole('button', { name: /run ingestion/i }))

    await waitFor(() => {
      expect(screen.getByText('source path not found')).toBeInTheDocument()
    })
  })

  it('supports obsidian source_type selection', async () => {
    const user = userEvent.setup()
    renderWithProviders(<IngestionView currentUser={mockUser.reviewer} />)

    await user.selectOptions(screen.getByRole('combobox'), 'obsidian')
    await user.type(screen.getByPlaceholderText(/path\/to\/documents/i), '/vault')
    await user.click(screen.getByRole('button', { name: /run ingestion/i }))

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/v1/ingest',
        expect.objectContaining({
          body: JSON.stringify({ source_path: '/vault', source_type: 'obsidian' }),
        }),
      )
    })
  })
})