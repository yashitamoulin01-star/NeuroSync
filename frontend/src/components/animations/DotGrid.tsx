'use client'
// NOTE: InertiaPlugin is subject to GSAP standard license (non-commercial free).
// Commercial deployment requires a Club GreenSock Business Green membership.
// See https://gsap.com/standard-license — replace with CSS spring or purchase a license before production.
import { useRef, useEffect, useCallback, useMemo } from 'react'
import { gsap } from 'gsap'
import { InertiaPlugin } from 'gsap/InertiaPlugin'

gsap.registerPlugin(InertiaPlugin)

interface Dot {
  cx: number
  cy: number
  xOffset: number
  yOffset: number
  _inertiaApplied: boolean
}

interface PointerState {
  x: number
  y: number
  vx: number
  vy: number
  speed: number
  lastTime: number
  lastX: number
  lastY: number
}

interface DotGridProps {
  dotSize?: number
  gap?: number
  baseColor?: string
  activeColor?: string
  proximity?: number
  speedTrigger?: number
  shockRadius?: number
  shockStrength?: number
  maxSpeed?: number
  resistance?: number
  returnDuration?: number
  className?: string
  style?: React.CSSProperties
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const m = hex.match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i)
  if (!m) return { r: 0, g: 0, b: 0 }
  return { r: parseInt(m[1], 16), g: parseInt(m[2], 16), b: parseInt(m[3], 16) }
}

function throttle<T extends (...args: Parameters<T>) => void>(fn: T, limit: number): T {
  let lastCall = 0
  return function (this: unknown, ...args: Parameters<T>) {
    const now = performance.now()
    if (now - lastCall >= limit) { lastCall = now; fn.apply(this, args) }
  } as T
}

export default function DotGrid({
  dotSize = 16,
  gap = 32,
  baseColor = '#5227FF',
  activeColor = '#5227FF',
  proximity = 150,
  speedTrigger = 100,
  shockRadius = 250,
  shockStrength = 5,
  maxSpeed = 5000,
  resistance = 750,
  returnDuration = 1.5,
  className = '',
  style,
}: DotGridProps) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const canvasRef  = useRef<HTMLCanvasElement>(null)
  const dotsRef    = useRef<Dot[]>([])
  const pointerRef = useRef<PointerState>({
    x: 0, y: 0, vx: 0, vy: 0, speed: 0, lastTime: 0, lastX: 0, lastY: 0,
  })

  const baseRgb   = useMemo(() => hexToRgb(baseColor),   [baseColor])
  const activeRgb = useMemo(() => hexToRgb(activeColor), [activeColor])

  const circlePath = useMemo(() => {
    if (typeof window === 'undefined' || !window.Path2D) return null
    const p = new window.Path2D()
    p.arc(0, 0, dotSize / 2, 0, Math.PI * 2)
    return p
  }, [dotSize])

  const buildGrid = useCallback(() => {
    const wrap   = wrapperRef.current
    const canvas = canvasRef.current
    if (!wrap || !canvas) return

    const { width, height } = wrap.getBoundingClientRect()
    const dpr = window.devicePixelRatio || 1

    canvas.width  = width  * dpr
    canvas.height = height * dpr
    canvas.style.width  = `${width}px`
    canvas.style.height = `${height}px`
    const ctx = canvas.getContext('2d')
    if (ctx) ctx.scale(dpr, dpr)

    const cols  = Math.floor((width  + gap) / (dotSize + gap))
    const rows  = Math.floor((height + gap) / (dotSize + gap))
    const cell  = dotSize + gap
    const startX = (width  - (cell * cols - gap)) / 2 + dotSize / 2
    const startY = (height - (cell * rows - gap)) / 2 + dotSize / 2

    const dots: Dot[] = []
    for (let r = 0; r < rows; r++)
      for (let c = 0; c < cols; c++)
        dots.push({ cx: startX + c * cell, cy: startY + r * cell, xOffset: 0, yOffset: 0, _inertiaApplied: false })
    dotsRef.current = dots
  }, [dotSize, gap])

  useEffect(() => {
    if (!circlePath) return
    let rafId: number
    const proxSq = proximity * proximity

    const draw = () => {
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      const { x: px, y: py } = pointerRef.current
      for (const dot of dotsRef.current) {
        const dx = dot.cx - px, dy = dot.cy - py
        let fill = baseColor
        if (dx * dx + dy * dy <= proxSq) {
          const t = 1 - Math.sqrt(dx * dx + dy * dy) / proximity
          fill = `rgb(${Math.round(baseRgb.r + (activeRgb.r - baseRgb.r) * t)},${Math.round(baseRgb.g + (activeRgb.g - baseRgb.g) * t)},${Math.round(baseRgb.b + (activeRgb.b - baseRgb.b) * t)})`
        }
        ctx.save()
        ctx.translate(dot.cx + dot.xOffset, dot.cy + dot.yOffset)
        ctx.fillStyle = fill
        ctx.fill(circlePath)
        ctx.restore()
      }
      rafId = requestAnimationFrame(draw)
    }

    draw()
    return () => cancelAnimationFrame(rafId)
  }, [proximity, baseColor, activeRgb, baseRgb, circlePath])

  useEffect(() => {
    buildGrid()
    let ro: ResizeObserver | null = null
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(buildGrid)
      if (wrapperRef.current) ro.observe(wrapperRef.current)
    } else {
      window.addEventListener('resize', buildGrid)
    }
    return () => { ro ? ro.disconnect() : window.removeEventListener('resize', buildGrid) }
  }, [buildGrid])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const onMove = (e: MouseEvent) => {
      const now = performance.now()
      const pr  = pointerRef.current
      const dt  = pr.lastTime ? now - pr.lastTime : 16
      let vx = ((e.clientX - pr.lastX) / dt) * 1000
      let vy = ((e.clientY - pr.lastY) / dt) * 1000
      let speed = Math.hypot(vx, vy)
      if (speed > maxSpeed) { const s = maxSpeed / speed; vx *= s; vy *= s; speed = maxSpeed }
      Object.assign(pr, { lastTime: now, lastX: e.clientX, lastY: e.clientY, vx, vy, speed })
      const rect = canvas.getBoundingClientRect()
      pr.x = e.clientX - rect.left
      pr.y = e.clientY - rect.top

      for (const dot of dotsRef.current) {
        if (speed > speedTrigger && Math.hypot(dot.cx - pr.x, dot.cy - pr.y) < proximity && !dot._inertiaApplied) {
          dot._inertiaApplied = true
          gsap.killTweensOf(dot)
          const pushX = dot.cx - pr.x + vx * 0.005
          const pushY = dot.cy - pr.y + vy * 0.005
          gsap.to(dot, {
            inertia: { xOffset: pushX, yOffset: pushY, resistance },
            onComplete: () => { gsap.to(dot, { xOffset: 0, yOffset: 0, duration: returnDuration, ease: 'elastic.out(1,0.75)' }); dot._inertiaApplied = false },
          })
        }
      }
    }

    const onClick = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect()
      const cx = e.clientX - rect.left, cy = e.clientY - rect.top
      for (const dot of dotsRef.current) {
        const dist = Math.hypot(dot.cx - cx, dot.cy - cy)
        if (dist < shockRadius && !dot._inertiaApplied) {
          dot._inertiaApplied = true
          gsap.killTweensOf(dot)
          const falloff = Math.max(0, 1 - dist / shockRadius)
          gsap.to(dot, {
            inertia: { xOffset: (dot.cx - cx) * shockStrength * falloff, yOffset: (dot.cy - cy) * shockStrength * falloff, resistance },
            onComplete: () => { gsap.to(dot, { xOffset: 0, yOffset: 0, duration: returnDuration, ease: 'elastic.out(1,0.75)' }); dot._inertiaApplied = false },
          })
        }
      }
    }

    const throttledMove = throttle(onMove, 50)
    window.addEventListener('mousemove', throttledMove, { passive: true })
    window.addEventListener('click', onClick)
    return () => { window.removeEventListener('mousemove', throttledMove); window.removeEventListener('click', onClick) }
  }, [maxSpeed, speedTrigger, proximity, resistance, returnDuration, shockRadius, shockStrength])

  return (
    <section className={`flex items-center justify-center h-full w-full relative ${className}`} style={style}>
      <div ref={wrapperRef} className="w-full h-full relative">
        <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" />
      </div>
    </section>
  )
}
