import { describe, it, expect, vi } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import GraphCanvas, { type GraphNode } from './GraphCanvas'

const nodes: GraphNode[] = [
  { id: 'node-1', name: 'Nexus-KB', entity_type: 'TERM', confidence: 0.9 },
  { id: 'node-2', name: 'Qdrant', entity_type: 'TECHNOLOGY', confidence: 0.85 },
]

describe('GraphCanvas', () => {
  it('calls onNodeClick when a node is clicked without dragging', () => {
    const onNodeClick = vi.fn()
    const { container } = render(<GraphCanvas nodes={nodes} edges={[]} onNodeClick={onNodeClick} />)

    const circle = container.querySelector('circle')
    expect(circle).toBeTruthy()

    // mousedown then mouseup with no mousemove in between = a click, not a drag.
    // fireEvent (not raw dispatchEvent) so React flushes state between calls --
    // the mouseup handler's closure needs the fresh `dragging` value set by mousedown.
    fireEvent.mouseDown(circle!.parentElement!)
    fireEvent.mouseUp(container.querySelector('svg')!)

    expect(onNodeClick).toHaveBeenCalledTimes(1)
    expect(onNodeClick.mock.calls[0][0].id).toBe('node-1')
  })

  it('does not call onNodeClick when the node is dragged', () => {
    const onNodeClick = vi.fn()
    const { container } = render(<GraphCanvas nodes={nodes} edges={[]} onNodeClick={onNodeClick} />)

    const circle = container.querySelector('circle')!
    const svg = container.querySelector('svg')!
    fireEvent.mouseDown(circle.parentElement!, { clientX: 0, clientY: 0 })
    fireEvent.mouseMove(svg, { clientX: 50, clientY: 50 })
    fireEvent.mouseUp(svg)

    expect(onNodeClick).not.toHaveBeenCalled()
  })

  it('renders a "no entities" placeholder when there are no nodes', () => {
    const { getByText } = render(<GraphCanvas nodes={[]} edges={[]} />)
    expect(getByText(/No entities to display/i)).toBeInTheDocument()
  })

  it('does not throw when onNodeClick is omitted', () => {
    const { container } = render(<GraphCanvas nodes={nodes} edges={[]} />)
    const circle = container.querySelector('circle')!
    const svg = container.querySelector('svg')!
    expect(() => {
      fireEvent.mouseDown(circle.parentElement!)
      fireEvent.mouseUp(svg)
    }).not.toThrow()
  })
})
