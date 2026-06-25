'use client'
import { useEffect, useRef } from 'react'
import { polarToCartesian } from '@/lib/utils'

interface FingerprintData {
  confidence:   number
  communication: number
  engagement:   number
  stress:       number  // inverted for display
  consistency:  number
}

interface Props {
  data: FingerprintData
  size?: number
  animated?: boolean
  className?: string
}

const DIMS = [
  { key: 'confidence',    label: 'Confidence',    color: '#818cf8', angle: -90 },
  { key: 'engagement',    label: 'Engagement',    color: '#34d399', angle: -90 + 72 },
  { key: 'communication', label: 'Comm.',          color: '#60a5fa', angle: -90 + 144 },
  { key: 'consistency',   label: 'Consistency',   color: '#fbbf24', angle: -90 + 216 },
  { key: 'stress',        label: 'Composure',     color: '#f87171', angle: -90 + 288 },
] as const

export function BehavioralFingerprint({ data, size = 220, animated = true, className }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const cx = size / 2
  const cy = size / 2
  const maxR = size * 0.38
  const rings = [0.25, 0.5, 0.75, 1]

  const displayData = {
    ...data,
    stress: 1 - data.stress, // invert — high stress = low composure
  }

  // Build polygon path from data
  function buildPath(vals: typeof displayData, scale = 1): string {
    const points = DIMS.map(d => {
      const r = (vals[d.key] ?? 0) * maxR * scale
      return polarToCartesian(cx, cy, r, d.angle)
    })
    return points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(' ') + ' Z'
  }

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${size} ${size}`}
      width={size}
      height={size}
      className={className}
      aria-label="Behavioral fingerprint visualization"
    >
      {/* Ring guides */}
      {rings.map(r => (
        <circle
          key={r}
          cx={cx} cy={cy}
          r={maxR * r}
          fill="none"
          stroke="rgba(255,255,255,0.04)"
          strokeWidth="1"
        />
      ))}

      {/* Axis lines */}
      {DIMS.map(d => {
        const end = polarToCartesian(cx, cy, maxR, d.angle)
        return (
          <line
            key={d.key}
            x1={cx} y1={cy}
            x2={end.x} y2={end.y}
            stroke="rgba(255,255,255,0.06)"
            strokeWidth="1"
          />
        )
      })}

      {/* Fill polygon */}
      <path
        d={buildPath(displayData)}
        fill="rgba(99,102,241,0.08)"
        stroke="rgba(99,102,241,0.25)"
        strokeWidth="1.5"
        strokeLinejoin="round"
        style={animated ? {
          animation: 'breathe 4s ease-in-out infinite',
          transformOrigin: `${cx}px ${cy}px`,
        } : undefined}
      />

      {/* Per-dimension colored arcs at max */}
      {DIMS.map(d => {
        const val = displayData[d.key] ?? 0
        const r = val * maxR
        const dot = polarToCartesian(cx, cy, r, d.angle)
        return (
          <g key={d.key}>
            {/* Data dot */}
            <circle
              cx={dot.x} cy={dot.y}
              r={3.5}
              fill={d.color}
              stroke={d.color}
              strokeWidth="2"
              strokeOpacity="0.3"
            />
            {/* Outer ring */}
            <circle
              cx={dot.x} cy={dot.y}
              r={6}
              fill="none"
              stroke={d.color}
              strokeWidth="1"
              strokeOpacity="0.2"
            />
          </g>
        )
      })}

      {/* Axis labels */}
      {DIMS.map(d => {
        const labelR = maxR + 18
        const pos = polarToCartesian(cx, cy, labelR, d.angle)
        return (
          <text
            key={d.key}
            x={pos.x} y={pos.y}
            textAnchor="middle"
            dominantBaseline="middle"
            fill="rgba(161,161,170,0.7)"
            fontSize="8"
            fontFamily="Inter, sans-serif"
            fontWeight="500"
          >
            {d.label}
          </text>
        )
      })}

      {/* Center score */}
      <text
        x={cx} y={cy - 7}
        textAnchor="middle"
        fill="#f4f4f5"
        fontSize="18"
        fontFamily="'JetBrains Mono', monospace"
        fontWeight="600"
        letterSpacing="-1"
      >
        {Math.round(
          (displayData.confidence + displayData.engagement + displayData.communication + displayData.consistency + displayData.stress) / 5 * 100
        )}
      </text>
      <text
        x={cx} y={cy + 9}
        textAnchor="middle"
        fill="rgba(161,161,170,0.6)"
        fontSize="8"
        fontFamily="Inter, sans-serif"
        fontWeight="500"
        letterSpacing="0.05em"
      >
        OVERALL
      </text>
    </svg>
  )
}
