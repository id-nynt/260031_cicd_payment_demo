import { readFile, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import pg from 'pg';
import { loadConfig } from '../config.js';

const { Client } = pg;
const config = loadConfig();
const client = new Client({ connectionString: config.DATABASE_URL });
const migrationDirectory = fileURLToPath(new URL('./migrations/', import.meta.url));

await client.connect();
try {
  const files = (await readdir(migrationDirectory)).filter((file) => file.endsWith('.sql')).sort();
  for (const file of files) await client.query(await readFile(`${migrationDirectory}/${file}`, 'utf8'));
  console.log('Database migration complete');
} finally {
  await client.end();
}
