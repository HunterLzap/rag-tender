/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#7C4DFF',
          light: '#EDE7F6',
          dark: '#651FFF',
        },
        surface: '#F9F7FF',
        success: '#4CAF50',
        warning: '#FF9800',
        error: '#EF5350',
      },
    },
  },
  plugins: [],
};
