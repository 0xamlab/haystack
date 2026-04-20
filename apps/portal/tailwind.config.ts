import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      // ─── Algenta Design System tokens ──────────────────────────────────
      colors: {
        ag: {
          bg: {
            canvas:   '#0B0D12',
            0:        '#0F1117',
            1:        '#11131A',
            2:        '#151823',
            3:        '#1A1F2B',
            sidebar:  '#0D1016',
          },
          border: {
            subtle:  '#1B2130',
            DEFAULT: '#1F2430',
            strong:  '#2A3142',
            focus:   '#6B42FC',
          },
          text: {
            primary:   '#E6E8EC',
            secondary: '#B0B7C6',
            muted:     '#8A90A2',
            faint:     '#687089',
          },
          brand: {
            DEFAULT: '#6B42FC',
            hover:   '#7C5CFF',
            active:  '#5B34E8',
          },
          success: '#00D395',
          warning: '#F59E0B',
          danger:  '#EF4444',
          info:    '#38BDF8',
        },
        // Legacy brand-* kept for any inline Tailwind fallbacks
        'brand-bg':      '#0B0D12',
        'brand-card':    '#11131A',
        'brand-border':  '#1F2430',
        'brand-text':    '#E6E8EC',
        'brand-muted':   '#8A90A2',
        'brand-primary': '#6B42FC',
        'brand-success': '#00D395',
        'brand-warning': '#F59E0B',
        'brand-danger':  '#EF4444',
        'brand-editor':  '#0F1117',
        'dark-100': '#0B0D12',
        'dark-200': '#0F1117',
        'dark-300': '#151823',
        'dark-400': '#1A1F2E',
      },

      // ─── Typography ────────────────────────────────────────────────────
      fontFamily: {
        sans: ['Inter', 'Geist', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },

      // ─── Border radius ─────────────────────────────────────────────────
      borderRadius: {
        'ag-xs': '6px',
        'ag-sm': '8px',
        'ag-md': '10px',
        'ag-lg': '14px',
        'ag-xl': '18px',
      },

      // ─── Shadows ───────────────────────────────────────────────────────
      boxShadow: {
        'ag-card':  '0 0 0 1px rgba(255,255,255,0.03), 0 8px 24px rgba(0,0,0,0.24)',
        'ag-panel': '0 0 0 1px rgba(255,255,255,0.04), 0 12px 40px rgba(0,0,0,0.28)',
        'ag-focus': '0 0 0 1px rgba(107,66,252,0.55), 0 0 0 4px rgba(107,66,252,0.16)',
        'glow':     '0 0 20px rgba(107, 66, 252, 0.15)',
      },

      // ─── Heights ───────────────────────────────────────────────────────
      height: {
        'topbar':  '60px',
        'sidebar': '248px',
      },
      width: {
        'sidebar': '248px',
      },
    },
  },
  plugins: [],
  darkMode: 'class',
}
export default config
