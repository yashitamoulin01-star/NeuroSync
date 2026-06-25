/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  darkMode: 'class',
  theme: {
    extend: {
      // ── shadcn/ui CSS-variable tokens ─────────────────────────────────────
      // These resolve via CSS custom properties defined in globals.css.
      // shadcn components expect exactly these names.
      colors: {
        background:  'hsl(var(--background))',
        foreground:  'hsl(var(--foreground))',
        card: {
          DEFAULT:    'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT:    'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        primary: {
          DEFAULT:    'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT:    'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT:    'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT:    'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: {
          DEFAULT:    'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        border: {
          DEFAULT: 'hsl(var(--border))',
          subtle:  '#171717',
          strong:  '#404040',
          focus:   '#6366f1',
          active:  '#525252',
        },
        input: 'hsl(var(--input))',
        ring:  'hsl(var(--ring))',

        // ── Project design system tokens ─────────────────────────────────────
        // Used throughout the app's own components.

        // Brand accent — these are the intentional usage aliases.
        // accent-bright:  solid indigo for logo backgrounds, primary buttons
        // accent-glow:    subtle indigo wash for active nav / selected states
        // accent:         legible indigo for text labels and icon tints
        'accent-bright': '#6366f1',
        'accent-glow':   'rgba(99,102,241,0.10)',
        'accent':        '#818cf8',

        // Input background
        'bg-input': '#0a0a0a',

        bg: {
          base:     '#000000',
          surface:  '#0a0a0a',
          card:     '#0a0a0a',
          hover:    '#171717',
          selected: '#262626',
        },
        text: {
          primary:   '#ffffff',
          secondary: '#a3a3a3',
          muted:     '#737373',
          disabled:  '#52525b',
        },
        // Behavioral dimension colors — use ONLY for behavioral score visualization
        // (charts, radar, score bars, timeline). NOT for UI states like online/error.
        metric: {
          confidence:  '#818cf8',
          stress:      '#f87171',
          engagement:  '#34d399',
          comm:        '#60a5fa',
          consistency: '#fbbf24',
        },
        // UI state colors — use for system health, validation, errors, success messages.
        // NOT for behavioral scores (use metric.* for those).
        status: {
          success: '#22c55e',
          warning: '#f59e0b',
          danger:  '#ef4444',
          info:    '#6366f1',
        },
      },

      borderRadius: {
        xs: '3px',
        sm: 'calc(var(--radius) - 4px)',
        md: 'calc(var(--radius) - 2px)',
        lg: 'var(--radius)',
      },

      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },

      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
      },

      letterSpacing: {
        tight2: '-0.04em',
        tight3: '-0.06em',
      },

      // Motion timing tokens — use these instead of hardcoding durations
      // fast: hover, micro-interactions (120–150ms)
      // normal: transitions, reveals (250–300ms)
      // slow: charts, complex reveals (500ms)
      transitionDuration: {
        'fast':   '150ms',
        'normal': '250ms',
        'slow':   '500ms',
      },

      animation: {
        'pulse-slow':  'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
        'spin-slow':   'spin 6s linear infinite',
        'breathe':     'breathe 4s ease-in-out infinite',
        'slide-up':    'slideUp 0.4s cubic-bezier(0.16,1,0.3,1)',
        'slide-in':    'slideIn 0.3s cubic-bezier(0.16,1,0.3,1)',
        'fade-in':     'fadeIn 0.3s ease',
        'ring-expand': 'ringExpand 1.5s ease-out infinite',
      },

      keyframes: {
        slideUp: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        slideIn: {
          from: { opacity: '0', transform: 'translateX(-8px)' },
          to:   { opacity: '1', transform: 'translateX(0)' },
        },
        fadeIn: {
          from: { opacity: '0' },
          to:   { opacity: '1' },
        },
        ringExpand: {
          '0%':   { transform: 'scale(1)',   opacity: '0.6' },
          '100%': { transform: 'scale(1.5)', opacity: '0' },
        },
      },

      backgroundImage: {
        'grid-subtle': `linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)`,
        'radial-glow': 'radial-gradient(ellipse at center, rgba(99,102,241,0.08) 0%, transparent 70%)',
      },

      backgroundSize: {
        'grid-sm': '32px 32px',
        'grid-md': '64px 64px',
      },

      boxShadow: {
        // Elevation scale — surface < raised < floating
        'surface':  '0 1px 2px rgba(0,0,0,0.3)',
        'raised':   '0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)',
        'floating': '0 4px 16px rgba(0,0,0,0.4)',
        // Legacy aliases (kept for compatibility)
        'card':     '0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)',
        'card-lg':  '0 4px 16px rgba(0,0,0,0.4)',
        // Accent glow
        'glow-sm': '0 0 12px rgba(99,102,241,0.15)',
        'glow-md': '0 0 24px rgba(99,102,241,0.20)',
        'glow-lg': '0 0 48px rgba(99,102,241,0.15)',
      },
    },
  },
  plugins: [],
}
