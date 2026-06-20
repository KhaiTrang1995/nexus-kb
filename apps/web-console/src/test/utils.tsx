import { ReactElement, ReactNode } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  })
}

function AllProviders({ children }: { children: ReactNode }) {
  const client = createTestQueryClient()
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

export function renderWithProviders(ui: ReactElement, options?: Omit<RenderOptions, 'wrapper'>) {
  return render(ui, { wrapper: AllProviders, ...options })
}

export const mockUser = {
  searcher: { id: 'u1', name: 'Alice', role: '' },
  reviewer: { id: 'u2', name: 'Bob', role: 'Reviewer' },
  auditor: { id: 'u3', name: 'Carol', role: 'Auditor' },
} as const