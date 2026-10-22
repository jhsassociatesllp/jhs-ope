import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Builds one self-contained script + stylesheet into ../static/react so the
// existing FastAPI static mount serves it. No server-side secrets are used here.
export default defineConfig({
  plugins: [react()],
  define: { 'process.env.NODE_ENV': '"production"' },
  build: {
    outDir: '../static/react',
    emptyOutDir: true,
    cssCodeSplit: false,
    sourcemap: false,
    lib: { entry: 'src/main.jsx', name: 'OPEReact', formats: ['iife'], fileName: () => 'ope-react.js' },
    rollupOptions: { output: { assetFileNames: 'ope-react.[ext]' } },
  },
});
