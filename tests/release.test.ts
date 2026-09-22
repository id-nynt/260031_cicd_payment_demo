import { afterEach, describe, expect, it } from 'vitest';
import { buildApp } from '../src/app.js';
import { loadConfig } from '../src/config.js';
import { APP_VERSION } from '../src/release.js';

const applications: ReturnType<typeof buildApp>[] = [];
afterEach(async () => { await Promise.all(applications.splice(0).map((app) => app.close())); });

function application() {
  // A deployment variable must not relabel an old source revision as another release.
  const app = buildApp(loadConfig({ DATABASE_URL: 'postgres://localhost/payment', CI_RUN_ID: 'release-test', APP_VERSION: 'misleading-runtime-label' }));
  applications.push(app);
  return app;
}

describe('source-controlled experiment version', () => {
  it.each(['/checkout', '/payment', '/receipt'])('identifies the version before any payment or browser script on %s', async (url) => {
    const response = await application().inject(url);
    expect(response.statusCode).toBe(200);
    expect(response.headers['cache-control']).toBe('no-store');
    expect(response.body).toContain('aria-label="Application version"');
    expect(response.body).toContain(`>${APP_VERSION}</span>`);
    expect(response.body).toMatch(new RegExp(`<title>[^<]*Payment Service ${APP_VERSION}</title>`));
    expect(response.body).not.toContain('Payment receipt V2');
    expect(response.body).not.toContain('misleading-runtime-label');
  });

  it('uses the same version in health and public configuration while retaining execution identity', async () => {
    const app = application();
    const health = await app.inject('/health');
    const config = await app.inject('/config');
    expect(['v1', 'v2']).toContain(APP_VERSION);
    expect(health.json()).toMatchObject({ status: 'ok', appVersion: APP_VERSION, deploymentRunId: 'release-test', experimentMode: 'normal' });
    expect(config.json()).toMatchObject({ appVersion: APP_VERSION, providers: ['fake'] });
    expect(health.headers['cache-control']).toBe('no-store');
    expect(config.headers['cache-control']).toBe('no-store');
    expect((await app.inject('/')).headers.location).toBe('/checkout');
  });
});
