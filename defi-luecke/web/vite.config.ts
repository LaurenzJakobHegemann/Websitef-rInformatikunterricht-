import { defineConfig } from 'vite';

// base './' = relative asset paths, so the build also works in a GitHub Pages subfolder.
export default defineConfig({
  base: './',
  build: { outDir: 'dist', sourcemap: false },
});
