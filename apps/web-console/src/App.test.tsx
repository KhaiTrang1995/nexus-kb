import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from './App'

describe('App', () => {
  it('renders operational console nav', () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    )
    expect(screen.getByText(/Nexus-KB/i)).toBeInTheDocument()
    expect(screen.getByText(/Search/i)).toBeInTheDocument()
    expect(screen.getByText(/Review Queue/i)).toBeInTheDocument()
  })
})
