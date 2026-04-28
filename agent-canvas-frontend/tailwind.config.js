export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      boxShadow: {
        node: '0 12px 28px rgba(15, 23, 42, 0.14)',
      },
      animation: {
        pulseBorder: 'pulseBorder 1.6s ease-in-out infinite',
      },
      keyframes: {
        pulseBorder: {
          '0%, 100%': { borderColor: '#ef4444' },
          '50%': { borderColor: '#fecaca' },
        },
      },
    },
  },
  plugins: [],
};
