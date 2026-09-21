import { readFile, mkdir, appendFile, writeFile } from 'node:fs/promises';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { randomUUID } from 'node:crypto';
import { performance } from 'node:perf_hooks';
import { setTimeout as sleep } from 'node:timers/promises';

export function validateProfile(p) {
  if (!p || typeof p.name !== 'string' || !Number.isInteger(p.seed) ||
      !Number.isFinite(p.jitter) || p.jitter < 0 || p.jitter > 0.5 ||
      !Array.isArray(p.phases) || !p.phases.length) throw new Error('Invalid profile name, seed, jitter or phases');
  let seconds = 0;
  for (const phase of p.phases) {
    if (![phase.seconds, phase.requests_per_second, phase.error_fraction].every(Number.isFinite) ||
        phase.seconds <= 0 || phase.requests_per_second < 0 || phase.requests_per_second > 10 ||
        phase.error_fraction < 0 || phase.error_fraction > 1) throw new Error('Invalid phase: duration > 0, rate 0..10, error fraction 0..1 required');
    seconds += phase.seconds;
  }
  if (seconds > 3600) throw new Error('Profile may run at most one hour');
  return p;
}

export function seededRandom(seed) {
  let state = seed >>> 0;
  return () => { state = (Math.imul(1664525, state) + 1013904223) >>> 0; return state / 4294967296; };
}

async function journal(path) {
  try {
    const text = await readFile(path, 'utf8');
    // A concurrent writer may not have finished the last JSONL record yet.
    return text.split('\n').slice(0, -1).filter(line => line.trim()).map(line => JSON.parse(line));
  } catch (error) { if (error.code === 'ENOENT') return []; throw error; }
}

export function stopReason(events) {
  if (events.some(e => e.event === 'bdi_recovery_decision')) return 'recovery_started';
  if (events.some(e => e.event === 'controller_finished')) return 'campaign_finished';
  return null;
}

async function getHealth(baseUrl) {
  const response = await fetch(`${baseUrl}/health`, { signal: AbortSignal.timeout(3000) });
  if (!response.ok) throw new Error(`Health HTTP ${response.status}`);
  return response.json();
}

export async function runScenario({ campaign, profile, baseUrl, entity = 'production', output,
  waitSeconds = 1800, signal, pollMs = 50, log = console.log }) {
  validateProfile(profile);
  if (!['staging', 'production'].includes(entity)) throw new Error('Entity must be staging or production');
  if (!Number.isFinite(waitSeconds) || waitSeconds <= 0 || waitSeconds > 3600) throw new Error('wait-seconds must be 1..3600');
  const url = new URL(baseUrl);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== '/') throw new Error('Use a plain HTTP(S) app origin');
  baseUrl = url.origin;
  campaign = resolve(campaign);
  output = resolve(output ?? `${campaign}-traffic-${Date.now()}-${randomUUID().slice(0, 8)}`);
  await mkdir(dirname(output), { recursive: true });
  await mkdir(output); // Never overwrite evidence or create the controller campaign directory.
  const eventsPath = join(output, 'traffic.jsonl');
  const emit = async (event, fields = {}) => appendFile(eventsPath, JSON.stringify({ timestamp: new Date().toISOString(), event, ...fields }) + '\n');
  const summary = { scenario: profile.name, campaign, entity, base_url: baseUrl, seed: profile.seed,
    requests: 0, successful: 0, injected_errors: 0, unexpected_responses: 0, network_errors: 0,
    outcome: 'waiting', stop_reason: null, execution_id: null, elapsed_seconds: 0 };
  await writeFile(join(output, 'profile.json'), JSON.stringify(profile, null, 2) + '\n');
  const random = seededRandom(profile.seed);
  const journalPath = join(campaign, 'controller-journal.jsonl');
  let started;
  let failure;
  try {
    log(`WAITING for fresh ${entity} controller_pause in ${journalPath}\nEvidence: ${output}`);
    const waitUntil = performance.now() + waitSeconds * 1000;
    let selected;
    while (!selected) {
      if (signal?.aborted) { summary.stop_reason = 'operator_stop'; return summary; }
      const events = await journal(journalPath);
      const stop = stopReason(events);
      if (stop) { summary.stop_reason = `${stop}_before_traffic`; return summary; }
      const pauseIndex = events.findLastIndex(e => e.event === 'controller_pause' && e.after_entity === entity);
      if (pauseIndex >= 0) {
        const pause = events[pauseIndex];
        const expires = Date.parse(pause.timestamp) + pause.milliseconds;
        if (!Number.isFinite(expires) || Date.now() >= expires) throw new Error('Pause already expired. Do not attach late; reset and launch a new campaign.');
        selected = events.slice(0, pauseIndex).findLast(e => e.event === 'execution_configuration' && e.entity === entity);
        if (!selected?.execution_id) throw new Error('Pause lacks a correlated execution_configuration');
        const health = await getHealth(baseUrl);
        if (health.deploymentRunId !== selected.execution_id) throw new Error('App identity differs from the selected campaign execution');
        if (profile.phases.some(p => p.error_fraction > 0) && health.experimentMode !== 'request_faults') throw new Error('Fault profiles require experimentMode=request_faults');
      } else {
        if (performance.now() >= waitUntil) throw new Error('No pause within wait limit; check controller, runner and campaign path');
        await sleep(pollMs);
      }
    }
    summary.execution_id = selected.execution_id;
    summary.release_sha = selected.release_sha;
    summary.started_at = new Date().toISOString();
    summary.outcome = 'running';
    started = performance.now();
    await emit('traffic_started', { execution_id: selected.execution_id, seed: profile.seed });
    log(`STARTED ${profile.name}, execution=${selected.execution_id}; keep this terminal open. Ctrl+C stops traffic.`);
    let consecutiveNetworkErrors = 0;
    for (const [index, phase] of profile.phases.entries()) {
      await emit('phase_started', { phase: index + 1, ...phase });
      log(`PHASE ${index + 1}: ${phase.seconds}s, target ${phase.requests_per_second} requests/s, ${phase.error_fraction * 100}% fault headers`);
      const until = performance.now() + phase.seconds * 1000;
      let nextRequest = performance.now();
      let lastReport = performance.now();
      while (performance.now() < until) {
        if (signal?.aborted) { summary.stop_reason = 'operator_stop'; return summary; }
        const stop = stopReason(await journal(journalPath));
        if (stop) { summary.stop_reason = stop; return summary; }
        if (phase.requests_per_second > 0 && performance.now() >= nextRequest) {
          if (summary.requests >= 10000) throw new Error('Request safety limit reached');
          // Check identity before each payment; do not intentionally send faults into recovery.
          const health = await getHealth(baseUrl);
          if (health.deploymentRunId !== selected.execution_id) { summary.stop_reason = 'deployment_identity_changed'; return summary; }
          const inject = random() < phase.error_fraction;
          if (inject && health.experimentMode !== 'request_faults') throw new Error('Fault capability disappeared');
          // Recheck after health fetch, since recovery can begin while it is in flight.
          const stopAfterHealth = stopReason(await journal(journalPath));
          if (stopAfterHealth) { summary.stop_reason = stopAfterHealth; return summary; }
          const requestStarted = performance.now();
          summary.requests++;
          try {
            const response = await fetch(`${baseUrl}/payments`, {
              method: 'POST', signal: AbortSignal.timeout(3000),
              headers: { 'Content-Type': 'application/json', 'Idempotency-Key': randomUUID(), ...(inject ? { 'X-Experiment-Fault': 'error' } : {}) },
              body: JSON.stringify({ amount: 5000, currency: 'AUD', description: `Traffic scenario ${profile.name}`, payerName: 'Demo Customer',
                payerEmail: 'demo@example.com', provider: 'fake', demoCardNumber: '4242424242424242' })
            });
            const body = await response.json();
            const good = !inject && response.status === 201 && body.status === 'succeeded';
            const expectedFault = inject && response.status === 503 && body.error === 'experiment_injected_failure';
            if (good) summary.successful++;
            else if (expectedFault) summary.injected_errors++;
            else summary.unexpected_responses++;
            await emit('request', { phase: index + 1, injected: inject, status: response.status, duration_ms: performance.now() - requestStarted, expected: good || expectedFault });
            consecutiveNetworkErrors = 0;
            if (inject && !expectedFault) throw new Error('Requested fault was not confirmed; inspect app configuration');
          } catch (error) {
            if (error.message.startsWith('Requested fault')) throw error;
            summary.network_errors++;
            await emit('request_error', { message: error.message });
            if (++consecutiveNetworkErrors >= 5) throw new Error('Five consecutive traffic transport errors');
          }
          const interval = 1000 / phase.requests_per_second;
          nextRequest = performance.now() + interval * (1 + (random() * 2 - 1) * profile.jitter);
        }
        if (performance.now() - lastReport >= 5000) {
          log(`ACTIVE ${Math.round((performance.now() - started) / 1000)}s: requests=${summary.requests}, HTTP201=${summary.successful}, injected503=${summary.injected_errors}, unexpected=${summary.unexpected_responses}, transport_errors=${summary.network_errors}`);
          lastReport = performance.now();
        }
        await sleep(pollMs);
      }
    }
    summary.stop_reason = 'profile_duration_limit';
  } catch (error) {
    summary.stop_reason = 'error';
    summary.error = error.message;
    failure = error;
  } finally {
    summary.elapsed_seconds = started ? (performance.now() - started) / 1000 : 0;
    summary.outcome = failure ? 'error' : 'stopped';
    await emit('traffic_stopped', summary);
    await writeFile(join(output, 'summary.json'), JSON.stringify(summary, null, 2) + '\n');
    log(`STOPPED: ${summary.stop_reason}. Traffic summary: ${join(output, 'summary.json')}`);
  }
  if (failure) throw failure;
  return summary;
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help')) {
    console.log('node scripts/run-traffic-scenario.mjs --campaign <new-campaign-dir> --scenario <healthy|fluctuating|burst|temporary-errors|persistent-errors|intermittent-errors|idle> [--entity production|staging] [--url http://localhost:3000] [--seed 42] [--wait-seconds 1800] [--output <new-dir>]\nOr use --profile <JSON file> instead of --scenario. Start before the controller pause. Fake-payment adapter only; never dispatches CI/CD.');
    return;
  }
  const options = {};
  const allowed = new Set(['campaign', 'scenario', 'profile', 'entity', 'url', 'seed', 'wait-seconds', 'output']);
  for (let i = 0; i < args.length; i += 2) {
    const key = args[i].replace(/^--/, '');
    if (!args[i].startsWith('--') || !allowed.has(key) || !args[i + 1] || args[i + 1].startsWith('--') || key in options) throw new Error(`Invalid argument ${args[i]}; use --help`);
    options[key] = args[i + 1];
  }
  if (!options.campaign || Boolean(options.scenario) === Boolean(options.profile)) throw new Error('Specify --campaign and exactly one of --scenario or --profile');
  if (options.scenario && !/^[a-z-]+$/.test(options.scenario)) throw new Error('Invalid scenario name');
  const profilePath = options.profile ?? join(dirname(fileURLToPath(import.meta.url)), 'traffic-scenarios', `${options.scenario}.json`);
  const profile = JSON.parse(await readFile(profilePath, 'utf8'));
  if (options.seed !== undefined) profile.seed = Number(options.seed);
  const abort = new AbortController();
  process.once('SIGINT', () => abort.abort());
  process.once('SIGTERM', () => abort.abort());
  await runScenario({ campaign: options.campaign, profile, entity: options.entity,
    baseUrl: options.url ?? (options.entity === 'staging' ? 'http://localhost:3001' : 'http://localhost:3000'),
    output: options.output, waitSeconds: options['wait-seconds'] === undefined ? 1800 : Number(options['wait-seconds']), signal: abort.signal });
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch(error => { console.error(`Traffic scenario failed: ${error.message}`); process.exitCode = 1; });
}
