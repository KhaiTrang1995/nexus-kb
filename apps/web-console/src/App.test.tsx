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
      vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
        if (url.includes('/api/v1/auth/dev-token')) {
          const body = opts?.body ? JSON.parse(opts.body as string) : {}
          return Promise.resolve({
            ok: true,
            json: async () => ({
              access_token: 'test-jwt-token',
              user: { id: body.user_id || 'u1', name: body.name || 'Alice', role: body.role || '' },
            }),
          })
        }
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

  it('renders sidebar nav after login', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />)

    const aliceButtons = screen.getAllByText('Alice')
    const loginCard = aliceButtons[0].closest('button')!
    await user.click(loginCard)

    await waitFor(() => {
      expect(screen.getByTestId('sidebar')).toBeInTheDocument()
    })
  })
})
