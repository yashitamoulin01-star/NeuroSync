'use client'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts'
import { formatDuration } from '@/lib/utils'

interface TimelinePoint {
  t: number
  confidence: number
  stress: number
  engagement: number
  communication: number
}

interface Props {
  data: TimelinePoint[]
  height?: number
}

const LINES = [
  { key: 'confidence',    color: '#818cf8', label: 'Confidence' },
  { key: 'engagement',    color: '#34d399', label: 'Engagement' },
  { key: 'stress',        color: '#f87171', label: 'Stress' },
  { key: 'communication', color: '#60a5fa', label: 'Communication' },
]

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-border bg-bg-card p-3 shadow-card-lg text-xs min-w-[140px]">
      <p className="text-text-muted mb-2 font-medium">{formatDuration(label)}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4 py-0.5">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: p.color }} />
            <span className="text-text-secondary">{p.name}</span>
          </div>
          <span className="font-mono text-text-primary font-medium">{Math.round(p.value * 100)}%</span>
        </div>
      ))}
    </div>
  )
}

export function TimelineChart({ data, height = 200 }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
        <XAxis
          dataKey="t"
          tickFormatter={formatDuration}
          tick={{ fill: '#71717a', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          domain={[0, 1]}
          tickFormatter={v => `${v * 100}%`}
          tick={{ fill: '#71717a', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          width={38}
        />
        <Tooltip content={<CustomTooltip />} />
        {LINES.map(({ key, color, label }) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            name={label}
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            activeDot={{ r: 3, fill: color, stroke: 'none' }}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
