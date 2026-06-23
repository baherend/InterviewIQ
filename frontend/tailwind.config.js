/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        dark: '#0a0a0f',
        'dark-blue': '#0d1117',
        navy: '#0f172a',
      },
      boxShadow: {
        neon: '0 0 20px rgba(0,245,255,0.35)',
        'neon-lg': '0 0 40px rgba(0,245,255,0.5)',
        glass: '0 8px 32px 0 rgba(31,38,135,0.37)',
      },
      animation: {
        'spin-slow': 'spin 3s linear infinite',
        float: 'float 4s ease-in-out infinite',
        glow: 'glow 2s ease-in-out infinite alternate',
        'fade-in': 'fadeIn 0.5s ease-out',
      },
      keyframes: {
        float: {
          '0%,100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-12px)' },
        },
        glow: {
          from: { boxShadow: '0 0 10px #00f5ff, 0 0 20px #00f5ff' },
          to: { boxShadow: '0 0 20px #00f5ff, 0 0 50px #00f5ff, 0 0 80px #00f5ff' },
        },
        fadeIn: {
          from: { opacity: 0, transform: 'translateY(10px)' },
          to: { opacity: 1, transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
