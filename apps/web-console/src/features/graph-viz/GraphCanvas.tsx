import { useEffect, useRef, useState, useCallback } from 'react'

export interface GraphNode {
  id: string
  name: string
  entity_type: string
  confidence: number
}

export interface GraphEdge {
  id: string
  source_entity_id: string
  target_entity_id: string
  relationship_type: string
  confidence: number
}

interface NodePos { x: number; y: number; vx: number; vy: number }

const TYPE_COLORS: Record<string, string> = {
  TECHNOLOGY: '#6366f1',
  FRAMEWORK:  '#8b5cf6',
  LIBRARY:    '#a78bfa',
  CONCEPT:    '#06b6d4',
  PROCESS:    '#0ea5e9',
  PERSON:     '#f59e0b',
  ORGANIZATION: '#f97316',
  DOCUMENT:   '#84cc16',
  PRODUCT:    '#10b981',
  TERM:       '#94a3b8',
  DATASET:    '#ec4899',
}

function typeColor(type: string) {
  return TYPE_COLORS[type] ?? '#94a3b8'
}

const W = 900
const H = 560
const NODE_R = 20
const LINK_DIST = 140
const REPEL = 4000
const DAMPING = 0.82
const ALPHA = 0.08
const PULL = 0.012

export default function GraphCanvas({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const [positions, setPositions] = useState<Record<string, NodePos>>(() => initPositions(nodes))
  const [tooltip, setTooltip] = useState<{ node: GraphNode; x: number; y: number } | null>(null)
  const [dragging, setDragging] = useState<string | null>(null)
  const dragOffset = useRef<{ dx: number; dy: number }>({ dx: 0, dy: 0 })
  const rafRef = useRef<number>(0)
  const posRef = useRef(positions)
  posRef.current = positions

  // Reset positions when nodes change
  useEffect(() => {
    setPositions(initPositions(nodes))
  }, [nodes.map(n => n.id).join(',')])  // eslint-disable-line react-hooks/exhaustive-deps

  // Force simulation loop
  useEffect(() => {
    if (nodes.length < 2) return
    let running = true

    const tick = () => {
      if (!running) return
      setPositions(prev => {
        const next = { ...prev }
        const ids = nodes.map(n => n.id)

        // Add missing nodes
        for (const id of ids) {
          if (!next[id]) next[id] = { x: W / 2 + (Math.random() - 0.5) * 200, y: H / 2 + (Math.random() - 0.5) * 200, vx: 0, vy: 0 }
        }

        // Repulsion
        for (let i = 0; i < ids.length; i++) {
          for (let j = i + 1; j < ids.length; j++) {
            const a = next[ids[i]]
            const b = next[ids[j]]
            if (!a || !b) continue
            const dx = a.x - b.x
            const dy = a.y - b.y
            const dist = Math.sqrt(dx * dx + dy * dy) || 1
            const force = REPEL / (dist * dist)
            const fx = (dx / dist) * force
            const fy = (dy / dist) * force
            a.vx += fx; a.vy += fy
            b.vx -= fx; b.vy -= fy
          }
        }

        // Attraction along edges
        for (const e of edges) {
          const a = next[e.source_entity_id]
          const b = next[e.target_entity_id]
          if (!a || !b) continue
          const dx = b.x - a.x
          const dy = b.y - a.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const force = (dist - LINK_DIST) * ALPHA
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          a.vx += fx; a.vy += fy
          b.vx -= fx; b.vy -= fy
        }

        // Pull toward center
        for (const id of ids) {
          const p = next[id]
          if (!p) continue
          p.vx += (W / 2 - p.x) * PULL
          p.vy += (H / 2 - p.y) * PULL
        }

        // Integrate + damp + clamp
        for (const id of ids) {
          if (id === dragging) continue  // frozen while dragging
          const p = next[id]
          if (!p) continue
          p.vx *= DAMPING; p.vy *= DAMPING
          p.x += p.vx; p.y += p.vy
          p.x = Math.max(NODE_R + 2, Math.min(W - NODE_R - 2, p.x))
          p.y = Math.max(NODE_R + 2, Math.min(H - NODE_R - 2, p.y))
        }

        return next
      })
      rafRef.current = requestAnimationFrame(tick)
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => { running = false; cancelAnimationFrame(rafRef.current) }
  }, [nodes.length, edges.length, dragging])  // eslint-disable-line react-hooks/exhaustive-deps

  // Drag handlers
  const onMouseDown = useCallback((e: React.MouseEvent<SVGCircleElement>, id: string) => {
    e.preventDefault()
    const p = posRef.current[id]
    if (!p) return
    const svgRect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
    const mx = (e.clientX - svgRect.left) * (W / svgRect.width)
    const my = (e.clientY - svgRect.top) * (H / svgRect.height)
    dragOffset.current = { dx: p.x - mx, dy: p.y - my }
    setDragging(id)
  }, [])

  const onMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!dragging) return
    const svgRect = e.currentTarget.getBoundingClientRect()
    const mx = (e.clientX - svgRect.left) * (W / svgRect.width)
    const my = (e.clientY - svgRect.top) * (H / svgRect.height)
    setPositions(prev => {
      const next = { ...prev }
      const p = next[dragging]
      if (!p) return prev
      return { ...next, [dragging]: { ...p, x: mx + dragOffset.current.dx, y: my + dragOffset.current.dy, vx: 0, vy: 0 } }
    })
  }, [dragging])

  const onMouseUp = useCallback(() => setDragging(null), [])

  if (nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-kb-muted text-sm border border-kb-primary/20 rounded">
        No entities to display. Build the graph first.
      </div>
    )
  }

  return (
    <div className="relative select-none">
      <svg
        width="100%" viewBox={`0 0 ${W} ${H}`}
        className="rounded border border-kb-primary/20 bg-kb-dark/50 cursor-grab"
        style={{ cursor: dragging ? 'grabbing' : 'default' }}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
      >
        {/* Edges */}
        <g>
          {edges.map(e => {
            const a = positions[e.source_entity_id]
            const b = positions[e.target_entity_id]
            if (!a || !b) return null
            const mx = (a.x + b.x) / 2
            const my = (a.y + b.y) / 2
            return (
              <g key={e.id}>
                <line
                  x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke="#4f46e5" strokeOpacity={0.4} strokeWidth={1.2}
                />
                <text x={mx} y={my} textAnchor="middle" dominantBaseline="middle"
                  fill="#818cf8" fontSize={9} className="pointer-events-none">
                  {e.relationship_type}
                </text>
              </g>
            )
          })}
        </g>

        {/* Nodes */}
        <g>
          {nodes.map(n => {
            const p = positions[n.id]
            if (!p) return null
            const color = typeColor(n.entity_type)
            const label = n.name.length > 14 ? n.name.slice(0, 13) + '…' : n.name
            return (
              <g key={n.id}
                onMouseEnter={() => p && setTooltip({ node: n, x: p.x, y: p.y })}
                onMouseLeave={() => setTooltip(null)}
                onMouseDown={(e) => onMouseDown(e as any, n.id)}
                style={{ cursor: dragging === n.id ? 'grabbing' : 'grab' }}
              >
                <circle
                  cx={p.x} cy={p.y} r={NODE_R}
                  fill={color} fillOpacity={0.85}
                  stroke={dragging === n.id ? '#fff' : color}
                  strokeWidth={dragging === n.id ? 2 : 0.5}
                />
                <text
                  x={p.x} y={p.y + NODE_R + 11}
                  textAnchor="middle" fill="#e2e8f0" fontSize={10}
                  className="pointer-events-none"
                >
                  {label}
                </text>
              </g>
            )
          })}
        </g>

        {/* Tooltip */}
        {tooltip && positions[tooltip.node.id] && (() => {
          const p = positions[tooltip.node.id]
          const tx = Math.min(p.x + 14, W - 160)
          const ty = Math.max(p.y - 54, 4)
          return (
            <g>
              <rect x={tx} y={ty} width={155} height={52} rx={6}
                fill="#1e293b" stroke="#4f46e5" strokeWidth={0.8} />
              <text x={tx + 8} y={ty + 16} fill="#e2e8f0" fontSize={11} fontWeight="600">
                {tooltip.node.name.slice(0, 22)}
              </text>
              <text x={tx + 8} y={ty + 30} fill="#94a3b8" fontSize={9}>
                {tooltip.node.entity_type}
              </text>
              <text x={tx + 8} y={ty + 43} fill="#94a3b8" fontSize={9}>
                conf {tooltip.node.confidence.toFixed(2)}
              </text>
            </g>
          )
        })()}
      </svg>

      {/* Legend */}
      <div className="mt-2 flex flex-wrap gap-2">
        {Array.from(new Set(nodes.map(n => n.entity_type))).map(type => (
          <span key={type} className="flex items-center gap-1 text-[10px] text-kb-muted">
            <span style={{ background: typeColor(type) }} className="inline-block w-2.5 h-2.5 rounded-full" />
            {type}
          </span>
        ))}
      </div>
    </div>
  )
}

function initPositions(nodes: GraphNode[]): Record<string, NodePos> {
  const pos: Record<string, NodePos> = {}
  const count = nodes.length
  nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / count
    const r = Math.min(W, H) * 0.32
    pos[n.id] = {
      x: W / 2 + r * Math.cos(angle),
      y: H / 2 + r * Math.sin(angle),
      vx: 0, vy: 0,
    }
  })
  return pos
}
