/** @type {import('tailwindcss').Config} */

// Semantic tokens resolve to CSS variables (see src/index.css), so one class
// works in both themes and the opacity modifier (`bg-accent/10`) still applies.
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`

export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Geist', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['"Geist Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        // Surfaces and text
        bg: token('bg'),
        side: token('side'),
        panel: token('panel'),
        raised: token('raised'),
        hover: token('hover'),
        line: token('line'),
        line2: token('line-2'),
        tx: token('tx'),
        tx2: token('tx-2'),
        tx3: token('tx-3'),
        // One accent: primary action, active nav, focus, current version, the mark
        accent: {
          DEFAULT: token('accent'),
          fg: token('accent-fg'),
          ink: token('accent-ink'),
        },
        // Status only
        ok: token('ok'),
        warn: token('warn'),
        dep: token('dep'),
        mute: token('mute'),
        bad: token('bad'),
        // Legacy scales re-tuned so untouched screens share the new neutrals.
        // Light mode reads `gray`, dark mode reads `slate`.
        gray: {
          50: '#F6F6F4',
          100: '#EEEEEB',
          200: '#E2E2DE',
          300: '#D2D2CC',
          400: '#74777F',
          500: '#62656D',
          600: '#52555D',
          700: '#3A3D44',
          800: '#25272C',
          900: '#151619',
          950: '#0C0D0F',
        },
        slate: {
          50: '#F5F5F6',
          100: '#ECEDEF',
          200: '#D9DADD',
          300: '#B9BBC1',
          400: '#A4A7AF',
          500: '#80848D',
          600: '#30333A',
          700: '#23252B',
          800: '#141519',
          900: '#0C0D0F',
          950: '#08090A',
        },
      },
      keyframes: {
        enter: {
          from: { opacity: '0', transform: 'translateY(8px)' },
        },
        grow: {
          from: { transform: 'scaleX(0)' },
        },
        route: {
          '0%': { opacity: '1', transform: 'scaleX(0)' },
          '70%': { opacity: '1', transform: 'scaleX(0.92)' },
          '100%': { opacity: '0', transform: 'scaleX(1)' },
        },
      },
      animation: {
        enter: 'enter 0.5s cubic-bezier(0.2, 0.7, 0.2, 1) both',
        swap: 'enter 0.35s cubic-bezier(0.2, 0.7, 0.2, 1) both',
        grow: 'grow 0.8s cubic-bezier(0.3, 0.7, 0.2, 1) 0.3s both',
        route: 'route 0.9s cubic-bezier(0.3, 0.7, 0.2, 1) both',
      },
    },
  },
  plugins: [],
}
