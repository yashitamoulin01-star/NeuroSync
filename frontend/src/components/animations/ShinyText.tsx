'use client'
import { useState, useCallback, useEffect, useRef } from 'react'
import { motion, useMotionValue, useAnimationFrame, useTransform } from 'framer-motion'

interface ShinyTextProps {
  text: string
  disabled?: boolean
  speed?: number
  className?: string
  color?: string
  shineColor?: string
  spread?: number
  yoyo?: boolean
  pauseOnHover?: boolean
  direction?: 'left' | 'right'
  delay?: number
}

export default function ShinyText({
  text,
  disabled = false,
  speed = 2,
  className = '',
  color = '#b5b5b5',
  shineColor = '#ffffff',
  spread = 120,
  yoyo = false,
  pauseOnHover = false,
  direction = 'left',
  delay = 0,
}: ShinyTextProps) {
  const [isPaused, setIsPaused] = useState(false)
  const progress    = useMotionValue(0)
  const elapsedRef  = useRef(0)
  const lastTimeRef = useRef<number | null>(null)
  const dirRef      = useRef(direction === 'left' ? 1 : -1)

  const dur   = speed * 1000
  const delMs = delay * 1000

  useAnimationFrame((time: number) => {
    if (disabled || isPaused) { lastTimeRef.current = null; return }
    if (lastTimeRef.current === null) { lastTimeRef.current = time; return }
    elapsedRef.current += time - lastTimeRef.current
    lastTimeRef.current = time

    const cycle = dur + delMs
    if (yoyo) {
      const t = elapsedRef.current % (cycle * 2)
      if (t < dur)              progress.set(dirRef.current === 1 ? (t / dur) * 100 : 100 - (t / dur) * 100)
      else if (t < cycle)       progress.set(dirRef.current === 1 ? 100 : 0)
      else if (t < cycle + dur) progress.set(dirRef.current === 1 ? 100 - ((t - cycle) / dur) * 100 : ((t - cycle) / dur) * 100)
      else                      progress.set(dirRef.current === 1 ? 0 : 100)
    } else {
      const t = elapsedRef.current % cycle
      progress.set(t < dur
        ? (dirRef.current === 1 ? (t / dur) * 100 : 100 - (t / dur) * 100)
        : (dirRef.current === 1 ? 100 : 0))
    }
  })

  useEffect(() => {
    dirRef.current = direction === 'left' ? 1 : -1
    elapsedRef.current = 0
    progress.set(0)
  }, [direction, progress])

  const backgroundPosition = useTransform(progress, (p: number) => `${150 - p * 2}% center`)

  const handleMouseEnter = useCallback(() => { if (pauseOnHover) setIsPaused(true)  }, [pauseOnHover])
  const handleMouseLeave = useCallback(() => { if (pauseOnHover) setIsPaused(false) }, [pauseOnHover])

  return (
    <motion.span
      className={`inline-block ${className}`}
      style={{
        backgroundImage: `linear-gradient(${spread}deg, ${color} 0%, ${color} 35%, ${shineColor} 50%, ${color} 65%, ${color} 100%)`,
        backgroundSize: '200% auto',
        WebkitBackgroundClip: 'text',
        backgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        backgroundPosition,
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {text}
    </motion.span>
  )
}
