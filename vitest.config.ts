import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Traffic scenarios use node:test and are run separately via test:traffic.
    include: ['tests/**/*.test.ts']
  }
});
