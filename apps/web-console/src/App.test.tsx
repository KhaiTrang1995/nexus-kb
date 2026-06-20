import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { renderWithProviders } from './test/utils'

describe('App', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('/api/v1/graph/stats')) {
          return Promise.resolve({ ok: true, json: async () => ({ node_count: 0 }) })
        }
        if (url.includes('/api/v1/review/queue')) {
          return Promise.resolve({ ok: true, json: async () => [] })
        }
        if (url.includes('/api/v1/search')) {
          return Promise.resolve({ ok: true, json: async () => ({ query: '', results: [] }) })
        }
        return Promise.resolve({ ok: false, status: 404 })
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('renders operational console nav after mock login', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />)

    await user.click(screen.getByRole('button', { name: /use default \(alice/i }))

    await waitFor(() => {
      expect(screen.getByText(/Nexus-KB/i)).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /search/i })).toBeInTheDocument()
      expect(screen.queryByRole('link', { name: /review queue/i })).not.toBeInTheDocument()
    })
  })
})
