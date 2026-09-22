import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtemp, mkdir, writeFile, appendFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { runScenario, validateProfile, seededRandom, stopReason } from '../run-traffic-scenario.mjs';

const profile = phases => ({ name: 'test', seed: 42, jitter: 0, phases });
const phase = (seconds, error_fraction = 0) => ({ seconds, requests_per_second: 10, error_fraction });

async function fixture(t, { identity = 'candidate', onPayment, expired = false, entity = 'production' } = {}) {
  const root = await mkdtemp(join(tmpdir(), 'bdi-traffic-test-'));
  const campaign = join(root, 'campaign');
  await mkdir(campaign);
  const journal = join(campaign, 'controller-journal.jsonl');
  await writeFile(journal, [
    { event: 'execution_configuration', entity, execution_id: 'candidate' },
    { event: 'controller_pause', after_entity: entity, timestamp: new Date(Date.now() - (expired ? 120000 : 0)).toISOString(), milliseconds: 60000 }
  ].map(e => JSON.stringify(e)).join('\n') + '\n');
  const received = [];
  const server = createServer(async (req, res) => {
    res.setHeader('Content-Type', 'application/json');
    if (req.url === '/health') { res.end(JSON.stringify({ deploymentRunId: identity, experimentMode: 'request_faults' })); return; }
    const fault = req.headers['x-experiment-fault'] === 'error';
    received.push(fault);
    await onPayment?.({ journal, received });
    res.statusCode = fault ? 503 : 201;
    res.end(JSON.stringify(fault ? { error: 'experiment_injected_failure' } : { status: 'succeeded' }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(async () => { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); await rm(root, { recursive: true, force: true }); });
  return { campaign, output: join(root, 'evidence'), baseUrl: `http://127.0.0.1:${server.address().port}`, pollMs: 10, log: () => {}, received, journal };
}

test('profile bounds and seeded schedule are reproducible', () => {
  assert.throws(() => validateProfile(profile([{ ...phase(1), requests_per_second: 100 }])));
  const a = seededRandom(42), b = seededRandom(42);
  assert.deepEqual(Array.from({ length: 20 }, a), Array.from({ length: 20 }, b));
});

test('temporary errors become continuous normal requests and evidence preserves profile', async t => {
  const f = await fixture(t);
  const p = profile([phase(.35, 1), phase(.45)]);
  const result = await runScenario({ ...f, profile: p });
  assert.ok(result.injected_errors >= 2);
  assert.ok(result.successful >= 2);
  assert.equal(result.stop_reason, 'profile_duration_limit');
  const firstNormal = f.received.indexOf(false);
  assert.ok(firstNormal > 0);
  assert.ok(f.received.slice(firstNormal).every(v => !v));
  assert.deepEqual(JSON.parse(await readFile(join(f.output, 'profile.json'))), p);
});

test('recovery stops future payments without touching restored release', async t => {
  const f = await fixture(t, { onPayment: async ({ journal }) => appendFile(journal, JSON.stringify({ event: 'bdi_recovery_decision' }) + '\n') });
  const result = await runScenario({ ...f, profile: profile([phase(2, 1)]) });
  assert.equal(result.stop_reason, 'recovery_started');
  assert.equal(f.received.length, 1);
});

test('wrong deployment identity is rejected without payments', async t => {
  const f = await fixture(t, { identity: 'old-v1' });
  await assert.rejects(runScenario({ ...f, profile: profile([phase(.1, 1)]) }), /identity differs/);
  assert.equal(f.received.length, 0);
});

test('expired pause is rejected rather than injecting into an old campaign', async t => {
  const f = await fixture(t, { expired: true });
  await assert.rejects(runScenario({ ...f, profile: profile([phase(.1)]) }), /expired/);
  assert.equal(f.received.length, 0);
});

test('idle emits no payments and reports duration limit, not app failure', async t => {
  const f = await fixture(t);
  const result = await runScenario({ ...f, profile: profile([{ ...phase(.1), requests_per_second: 0 }]) });
  assert.equal(result.requests, 0);
  assert.equal(result.stop_reason, 'profile_duration_limit');
});

test('campaign finish prevents any injection', async t => {
  const f = await fixture(t);
  await appendFile(f.journal, JSON.stringify({ event: 'controller_finished' }) + '\n');
  const result = await runScenario({ ...f, profile: profile([phase(.1, 1)]) });
  assert.equal(result.stop_reason, 'campaign_finished_before_traffic');
  assert.equal(f.received.length, 0);
});

test('client can arm before campaign exists and waits for complete journal lines', async t => {
  const f = await fixture(t);
  const original = await readFile(f.journal, 'utf8');
  await rm(f.campaign, { recursive: true });
  const running = runScenario({ ...f, profile: profile([phase(.2)]), waitSeconds: 2 });
  await new Promise(resolve => setTimeout(resolve, 50));
  assert.equal(f.received.length, 0);
  await mkdir(f.campaign);
  await writeFile(f.journal, original.trimEnd());
  await new Promise(resolve => setTimeout(resolve, 50));
  assert.equal(f.received.length, 0);
  await appendFile(f.journal, '\n');
  const result = await running;
  assert.ok(result.successful > 0);
});

test('operator abort saves evidence without waiting for a pause', async t => {
  const f = await fixture(t);
  const abort = new AbortController();
  abort.abort();
  const result = await runScenario({ ...f, profile: profile([phase(.2)]), signal: abort.signal });
  assert.equal(result.stop_reason, 'operator_stop');
  assert.equal(f.received.length, 0);
  assert.equal(JSON.parse(await readFile(join(f.output, 'summary.json'))).stop_reason, 'operator_stop');
});


test('staging profile follows staging pause and switches to healthy traffic', async t => {
  const f = await fixture(t, { entity: 'staging' });
  const p = { ...profile([phase(.3, 1), phase(.3)]), entity: 'staging' };
  const result = await runScenario({ ...f, profile: p });
  assert.equal(result.entity, 'staging');
  assert.ok(result.injected_errors >= 1);
  assert.ok(result.successful >= 1);
});

test('staging-only profile rejects a production override before requests', async t => {
  const f = await fixture(t);
  const p = { ...profile([phase(.1, 1)]), entity: 'staging' };
  await assert.rejects(runScenario({ ...f, profile: p, entity: 'production' }), /disagrees/);
  assert.equal(f.received.length, 0);
});

test('persistent staging traffic stops when the campaign stops promotion', async t => {
  const f = await fixture(t, { entity: 'staging', onPayment: async ({ journal }) => appendFile(journal, JSON.stringify({ event: 'controller_finished', outcome: 'stopped' }) + '\n') });
  const result = await runScenario({ ...f, profile: { ...profile([phase(2, 1)]), entity: 'staging' } });
  assert.equal(result.stop_reason, 'campaign_finished');
  assert.equal(result.requests, 1);
});

test('common experiment events drive traffic for the conventional mechanism too', async t => {
  const f = await fixture(t);
  const source=(await readFile(f.journal,'utf8')).trim().split('\n').map(JSON.parse);
  source[1].event='deployment_ready';
  for (const e of source) { e.mechanism='conventional'; e.schema_version=1; }
  await writeFile(join(f.campaign,'experiment-events.jsonl'),source.map(e=>JSON.stringify(e)).join('\n')+'\n');
  await rm(f.journal);
  const result=await runScenario({...f,profile:profile([phase(.2)])});
  assert.ok(result.successful > 0);
  assert.equal(result.execution_id,'candidate');
});


test('completion of staging observation does not stop the production client', () => {
  const events = [{ event: 'health_accepted', entity: 'staging', decision: 'allow' }];
  assert.equal(stopReason(events, 'staging'), 'campaign_finished');
  assert.equal(stopReason(events, 'production'), null);
  assert.equal(stopReason([...events, { event: 'bdi_recovery_decision' }], 'production'), 'recovery_started');
});
