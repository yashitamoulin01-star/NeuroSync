'use client'
import { ResponsiveContainer, AreaChart, Area } from 'recharts'

interface SparklineProps {
  data: number[]
  color?: string
  height?: number
  inverted?: boolean
}

export function Sparkline({ data, color = '#818cf8', height = 36, inverted }: SparklineProps) {
  if (!data.length) return <div style={{ height }} className="w-full" />
  const pts = data.map((v, i) => ({ i, v: inverted ? 1 - v : v }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={pts} margin={{ top: 2, bottom: 2, left: 0, right: 0 }}>
        <defs>
          <linearGradient id={`sg-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={color} stopOpacity={0.25} />
            <stop offset="95%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#sg-${color.replace('#', '')})`}
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
