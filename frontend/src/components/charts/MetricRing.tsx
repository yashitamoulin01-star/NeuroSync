'use client'
import { describeArc } from '@/lib/utils'

interface MetricRingProps {
  value: number
  label: string
  color: string
  size?: number
  strokeWidth?: number
  subLabel?: string
}

export function MetricRing({
  value, label, color, size = 80, strokeWidth = 7, subLabel,
}: MetricRingProps) {
  const cx = size / 2
  const cy = size / 2
  const r  = (size - strokeWidth * 2) / 2 - 2
  const pct = Math.min(1, Math.max(0, value))
  const end  = pct * 270 // 270° sweep (leaves a gap at bottom-left)
  const startAngle = 135
  const endAngle   = startAngle + end

  return (
    <div className="flex flex-col items-center gap-1.5">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Track */}
        <path
          d={describeArc(cx, cy, r, startAngle, startAngle + 270)}
          fill="none"
          stroke="rgba(255,255,255,0.05)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Value arc */}
        {pct > 0.02 && (
          <path
            d={describeArc(cx, cy, r, startAngle, endAngle)}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 0.8s ease' }}
          />
        )}
        {/* Center text */}
        <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="middle"
          fill="#f4f4f5" fontSize={size < 70 ? 13 : 16} fontWeight="600"
          fontFamily="'JetBrains Mono', monospace">
          {Math.round(pct * 100)}
        </text>
      </svg>
      <span className="text-xs text-text-muted font-medium">{label}</span>
      {subLabel && <span className="text-2xs text-text-disabled">{subLabel}</span>}
    </div>
  )
}
