import { defineConfig } from '@playwright/test';

const remoto = process.env.AUDIT_BASE_URL;
const baseURL = remoto || 'http://127.0.0.1:4173';

export default defineConfig({
  testDir: './tests',
  testMatch: /auditoria-visual\.spec\.mjs$/,
  timeout: 90_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'auditoria-visual/relatorio-html', open: 'never' }],
    ['json', { outputFile: 'auditoria-visual/resultados.json' }],
  ],
  outputDir: 'auditoria-visual/evidencias',
  use: {
    baseURL,
    locale: 'pt-BR',
    colorScheme: 'light',
    reducedMotion: 'reduce',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    actionTimeout: 25_000,
    navigationTimeout: 45_000,
  },
  webServer: remoto ? undefined : {
    command: 'npm run preview -- --host 127.0.0.1 --port 4173 --strictPort',
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
  projects: [
    { name: 'celular-375', use: { viewport: { width: 375, height: 812 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true } },
    { name: 'tablet-768', use: { viewport: { width: 768, height: 1024 }, deviceScaleFactor: 1 } },
    { name: 'desktop-1440', use: { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 } },
  ],
});