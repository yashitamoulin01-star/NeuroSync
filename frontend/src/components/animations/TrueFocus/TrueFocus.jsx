'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import './TrueFocus.css';

export default function TrueFocus({
  sentence = 'Confidence Communication Engagement Consistency Composure',
  separator = ' ',
  manualMode = false,
  blurAmount = 2,
  borderColor = 'rgba(92,124,255,0.65)',
  glowColor = 'rgba(92,124,255,0.12)',
  animationDuration = 1.8,
  pauseBetweenAnimations = 3,
}) {
  const words = sentence.split(separator).filter(Boolean);
  const [activeIndex, setActiveIndex] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const containerRef = useRef(null);
  const timerRef = useRef(null);

  // Respect prefers-reduced-motion
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(mq.matches);
    const handler = (e) => setPrefersReducedMotion(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // Intersection Observer — pause when off-screen
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => setIsVisible(entry.isIntersecting),
      { threshold: 0.1 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Auto-advance animation
  useEffect(() => {
    if (manualMode || !isVisible || prefersReducedMotion) return;

    const totalCycle = (animationDuration + pauseBetweenAnimations) * 1000;

    timerRef.current = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % words.length);
    }, totalCycle);

    return () => clearInterval(timerRef.current);
  }, [manualMode, isVisible, prefersReducedMotion, animationDuration, pauseBetweenAnimations, words.length]);

  const handleWordClick = useCallback((index) => {
    if (manualMode) setActiveIndex(index);
  }, [manualMode]);

  return (
    <div
      ref={containerRef}
      className="true-focus-container"
      role="region"
      aria-label="Behavioral dimensions"
    >
      {words.map((word, index) => {
        const isActive = index === activeIndex;
        const isInactive = !isActive && !prefersReducedMotion;

        return (
          <span
            key={index}
            className={`true-focus-word ${isActive ? 'active' : ''} ${isInactive ? 'inactive' : ''}`}
            onClick={() => handleWordClick(index)}
            aria-current={isActive ? 'true' : undefined}
          >
            {word}

            <AnimatePresence>
              {isActive && (
                <motion.span
                  className="focus-frame"
                  key="frame"
                  initial={{ opacity: 0, scale: 0.92 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.96 }}
                  transition={{
                    duration: animationDuration * 0.4,
                    ease: [0.16, 1, 0.3, 1],
                  }}
                  style={{
                    borderColor,
                    boxShadow: `0 0 8px ${glowColor}, inset 0 0 8px ${glowColor}`,
                  }}
                />
              )}
            </AnimatePresence>
          </span>
        );
      })}
    </div>
  );
}
