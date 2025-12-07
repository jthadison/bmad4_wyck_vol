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
        primary: '#3b82f6', // blue-500
        success: '#10b981', // green-500
        warning: '#f59e0b', // amber-500
        danger: '#ef4444'  // red-500
      }
    },
  },
  plugins: [],
}
