/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}'
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        surface: {
          base:     '#0b0e14',
          raised:   '#111520',
          card:     '#161b27',
          elevated: '#1c2333',
          overlay:  '#232b3e',
          hover:    '#2a3349',
          border:   '#2e3a50',
          'border-light': '#3d4d6a',
        },
        content: {
          DEFAULT:  '#e2e8f0',
          muted:    '#94a3b8',
          subtle:   '#64748b',
          inverse:  '#0f172a',
        },
        accent: {
          DEFAULT:  '#3b82f6',
          hover:    '#2563eb',
          muted:    '#1e3a5f',
        },
        bull: {
          DEFAULT:  '#22c55e',
          bright:   '#4ade80',
          muted:    '#15803d',
          bg:       '#052e16',
        },
        bear: {
          DEFAULT:  '#ef4444',
          bright:   '#f87171',
          muted:    '#991b1b',
          bg:       '#2d0a0a',
        },
        risk: {
          low:      '#22c55e',
          medium:   '#f59e0b',
          high:     '#f97316',
          critical: '#ef4444',
          extreme:  '#dc2626',
        },
        pattern: {
          spring:   '#22c55e',
          sos:      '#3b82f6',
          lps:      '#06b6d4',
          utad:     '#ef4444',
          sc:       '#f97316',
          ar:       '#a855f7',
          st:       '#8b5cf6',
        },
        status: {
          filled:   '#22c55e',
          pending:  '#f59e0b',
          rejected: '#ef4444',
          stopped:  '#dc2626',
          partial:  '#06b6d4',
          canceled: '#6b7280',
          active:   '#3b82f6',
          paused:   '#f59e0b',
          closed:   '#64748b',
        },
        confidence: {
          'a-plus': '#22c55e',
          a:        '#4ade80',
          b:        '#eab308',
          c:        '#f97316',
          d:        '#ef4444',
        },
        phase: {
          a: '#f87171',
          b: '#fbbf24',
          c: '#22c55e',
          d: '#3b82f6',
          e: '#a78bfa',
        },
        chart: {
          line1:    '#3b82f6',
          line2:    '#8b5cf6',
          line3:    '#06b6d4',
          line4:    '#f59e0b',
          volume:   '#6366f1',
          'volume-high': '#818cf8',
          grid:     '#1e293b',
          axis:     '#475569',
          crosshair:'#94a3b8',
        },
        // Keep existing for backward compat
        primary: '#3b82f6',
        success: '#10b981',
        warning: '#f59e0b',
        danger:  '#ef4444',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'card':       '0 1px 3px rgba(0, 0, 0, 0.4), 0 1px 2px rgba(0, 0, 0, 0.3)',
        'card-hover': '0 4px 12px rgba(0, 0, 0, 0.5), 0 2px 4px rgba(0, 0, 0, 0.4)',
        'elevated':   '0 8px 24px rgba(0, 0, 0, 0.6)',
        'glow-blue':  '0 0 20px rgba(59, 130, 246, 0.3)',
        'glow-green': '0 0 20px rgba(34, 197, 94, 0.3)',
        'glow-red':   '0 0 20px rgba(239, 68, 68, 0.3)',
        'glow-amber': '0 0 20px rgba(245, 158, 11, 0.3)',
        'inner-glow': 'inset 0 1px 0 rgba(255, 255, 255, 0.05)',
      },
      borderRadius: {
        'card':  '0.5rem',
        'badge': '0.25rem',
        'pill':  '9999px',
      },
      animation: {
        'fade-in':    'fadeIn 0.3s ease-in',
        'slide-up':   'slideUp 0.3s ease-out',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        'shimmer':    'shimmer 1.5s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%':   { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 8px rgba(239, 68, 68, 0.3)' },
          '50%':      { boxShadow: '0 0 20px rgba(239, 68, 68, 0.6)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '200% 0' },
          '100%': { backgroundPosition: '-200% 0' },
        },
      },
    },
  },
  plugins: [],
}
