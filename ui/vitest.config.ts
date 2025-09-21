import { defineConfig } from 'vitest/config'
import path from 'path'

export default defineConfig({
  test: {
    // Test files location
    include: ['tests/**/*.test.ts'],
  },
  resolve: {
    alias: {
      // Map ~ to the app directory for imports in tests
      '~': path.resolve(__dirname, './app'),
      '#imports': path.resolve(__dirname, './app'),
    },
  },
})
