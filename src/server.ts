import { loadConfig } from './config.js';
import { buildApp } from './app.js';

const config = loadConfig();
const app = buildApp(config);
try {
  await app.listen({ port: config.PORT, host: '0.0.0.0' });
} catch (error) {
  app.log.error(error);
  process.exit(1);
}
