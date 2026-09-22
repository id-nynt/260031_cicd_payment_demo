import { loadConfig } from './config.js';
import { buildApp } from './app.js';
import { APP_VERSION } from './release.js';

const config = loadConfig();
const app = buildApp(config);
try {
  await app.listen({ port: config.PORT, host: '0.0.0.0' });
  app.log.info({ appVersion: APP_VERSION, deploymentRunId: config.CI_RUN_ID }, `Payment Service ${APP_VERSION} started`);
} catch (error) {
  app.log.error(error);
  process.exit(1);
}
