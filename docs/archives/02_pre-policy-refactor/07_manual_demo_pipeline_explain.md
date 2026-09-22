# Overall Manual Demo Pipeline

This document explains the common manual workflow for demonstrating the BDI CI/CD prototype.

The short version is:

```text
clean old state
-> start observation terminals
-> start Jason deployment agent
-> wait for a meaningful point in the release
-> optionally trigger an environment change
-> watch Jason beliefs and decisions
-> check the final production version/state
```

## What Is The Correct Overall Pattern?

Yes, the common manual pattern is:

```text
1. Clear old logs and old containers.
2. Start the deployment by starting Jason.
3. Watch the MAS console and CicdEnvironment log.
4. Wait until the release reaches a meaningful point.
5. Trigger the scenario condition, if the scenario needs one.
6. Observe telemetry/percepts/beliefs.
7. Observe the selected Jason plan and action.
8. Check the final version and final production behavior.
```

The important research point is:

```text
The scenario setup may create the condition,
but Jason must choose the decision.
```

For example:

```text
PAYMENT_PRODUCTION_FORCE_ERROR_RATE=0.20
```

does not choose rollback. It only gives each real business request a probability of failing when `/pay` is called.

The rollback decision should appear only after:

```text
/pay traffic
-> Prometheus metrics change
-> CicdEnvironment telemetry poll
-> metric(production,error_rate,high)
-> environment(production,unstable)
-> AgentSpeak recovery plan
-> rollback(production)
```

## Common Terminals

Use four PowerShell terminals for manual demos.

## Terminal A: Clean State

Run before each demo:

```powershell
cd C:\NHI\2026_IT-Project\260023_BDI_CICD
docker compose down --remove-orphans
if (Test-Path .\bdi\logs\cicd_environment.log) { Clear-Content .\bdi\logs\cicd_environment.log }
```

Also remove old scenario environment variables:

```powershell
Remove-Item Env:\BDI_TELEMETRY_ENABLED -ErrorAction SilentlyContinue
Remove-Item Env:\BDI_TELEMETRY_INTERVAL_SECONDS -ErrorAction SilentlyContinue
Remove-Item Env:\BDI_TELEMETRY_GRACE_SECONDS -ErrorAction SilentlyContinue
Remove-Item Env:\BDI_OBSERVE_PRODUCTION_CANARY_MS -ErrorAction SilentlyContinue
Remove-Item Env:\PAYMENT_STAGING_FAILURE_MODE -ErrorAction SilentlyContinue
Remove-Item Env:\PAYMENT_PRODUCTION_FAILURE_MODE -ErrorAction SilentlyContinue
Remove-Item Env:\PAYMENT_PRODUCTION_FORCE_ERROR_RATE -ErrorAction SilentlyContinue
Remove-Item Env:\PAYMENT_PRODUCTION_EXTRA_LATENCY_MS -ErrorAction SilentlyContinue
Remove-Item Env:\BDI_FORCE_BUILD_FAIL -ErrorAction SilentlyContinue
Remove-Item Env:\BDI_FORCE_TEST_FAIL -ErrorAction SilentlyContinue
Remove-Item Env:\BDI_FORCE_SECURITY_SCAN_FAIL -ErrorAction SilentlyContinue
Remove-Item Env:\BDI_FORCE_HEALTH_CHECK_PRODUCTION_FAIL -ErrorAction SilentlyContinue
Remove-Item Env:\BDI_FORCE_HEALTH_CHECK_PRODUCTION_FAIL_ONCE -ErrorAction SilentlyContinue
Remove-Item Env:\BDI_FORCE_ROLLBACK_PRODUCTION_FAIL -ErrorAction SilentlyContinue
```

## Terminal B: Watch The Environment Log

```powershell
cd C:\NHI\2026_IT-Project\260023_BDI_CICD
Get-Content .\bdi\logs\cicd_environment.log -Tail 180 -Wait
```

This is usually the best evidence window.

It shows:

```text
external actions requested by Jason
shell scripts executed by Java
script exit codes
percepts added to Jason
telemetry polling results
decisions recorded from AgentSpeak
```

## Terminal C: Start Jason

Most demos start like this:

```powershell
cd C:\NHI\2026_IT-Project\260023_BDI_CICD\bdi

$env:BDI_TELEMETRY_ENABLED="true"
$env:BDI_TELEMETRY_INTERVAL_SECONDS="3"
$env:BDI_TELEMETRY_GRACE_SECONDS="5"
$env:BDI_OBSERVE_PRODUCTION_CANARY_MS="25000"

jason project.mas2j
```

Jason starts the MAS from:

```text
bdi/project.mas2j
```

The MAS starts:

```text
deployment_agent
```

The agent immediately adopts:

```text
!deliver_release(candidate)
```

## Terminal D: Inspect Agent Mind

While Jason is running:

```powershell
cd C:\NHI\2026_IT-Project\260023_BDI_CICD\bdi
jason agent mind deployment_agent
```

Expected belief examples:

```text
status(build,passed)[source(percept)]
status(deploy(production),passed)[source(percept)]
metric(production,error_rate,normal)[source(percept)]
environment(production,stable)[source(percept)]
delivery_succeeded(candidate)[source(self)]
decision(delivery_succeeded)[source(self)]
```

If this command is slow or does not flush, use the environment log as the main evidence.

## Final State Checks

Check the recorded production version:

```powershell
cd C:\NHI\2026_IT-Project\260023_BDI_CICD
Get-Content .\runtime\state\production_version.txt
```

Expected values:

```text
candidate   successful release
stable      rollback happened
```

Check production health:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8002/health
```

Check production business endpoint with POST:

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8002/pay -ContentType "application/json" -Body '{"amount": 10}'
```

Check Prometheus-derived telemetry:

```powershell
py .\telemetry\prometheus_adapter.py production --pretty
```

## Numbered Scenario Catalog

Use these numbered guides for the current experiment set. Each guide has:

```text
manual BDI workflow
expected MAS/log/belief evidence
quick BDI automation command
traditional fixed-pipeline command
```

| Code | Scenario | Main BDI capability | Guide |
| --- | --- | --- | --- |
| `01` | Successful delivery | Complete root goal when all beliefs stay healthy. | `experiments/01_successful_delivery.md` |
| `02` | Telemetry-driven production failure | React to real Prometheus error-rate degradation and rollback. | `experiments/02_telemetry_production_failure.md` |
| `03` | High latency | Pause/reobserve instead of blindly treating every telemetry issue the same. | `experiments/03_high_latency.md` |
| `04` | Observability failure | Distinguish app failure from missing telemetry and escalate uncertainty. | `experiments/04_observability_failure.md` |
| `05` | Transient health failure and retry | Restore reliability, then continue pursuing candidate delivery. | `experiments/05_transient_health_retry.md` |
| `06` | Build/test/security gate failures | Stop delivery when early gate percepts fail. | `experiments/06_gate_failures.md` |
| `07` | Rollback unavailable | Escalate to manual intervention when recovery action fails. | `experiments/07_rollback_unavailable.md` |

Quick automation commands:

```powershell
powershell -ExecutionPolicy Bypass -File .\experiments\01_successful_delivery_bdi.ps1
powershell -ExecutionPolicy Bypass -File .\experiments\02_telemetry_production_failure_bdi.ps1
powershell -ExecutionPolicy Bypass -File .\experiments\03_high_latency_bdi.ps1
powershell -ExecutionPolicy Bypass -File .\experiments\04_observability_failure_bdi.ps1
powershell -ExecutionPolicy Bypass -File .\experiments\05_transient_health_retry_bdi.ps1
powershell -ExecutionPolicy Bypass -File .\experiments\06_gate_failures_bdi.ps1 -Gate build
powershell -ExecutionPolicy Bypass -File .\experiments\07_rollback_unavailable_bdi.ps1
```

Traditional comparison commands:

```powershell
powershell -ExecutionPolicy Bypass -File .\experiments\01_successful_delivery_traditional.ps1
powershell -ExecutionPolicy Bypass -File .\experiments\02_telemetry_production_failure_traditional.ps1
powershell -ExecutionPolicy Bypass -File .\experiments\03_high_latency_traditional.ps1
powershell -ExecutionPolicy Bypass -File .\experiments\04_observability_failure_traditional.ps1
powershell -ExecutionPolicy Bypass -File .\experiments\05_transient_health_retry_traditional.ps1
powershell -ExecutionPolicy Bypass -File .\experiments\06_gate_failures_traditional.ps1 -Gate build
powershell -ExecutionPolicy Bypass -File .\experiments\07_rollback_unavailable_traditional.ps1
```

## Scenario Injection Cheat Sheet

Set these before starting Jason only for the matching scenario:

| Scenario | Injection |
| --- | --- |
| `01` successful delivery | No error injection. Use `PAYMENT_PRODUCTION_FORCE_ERROR_RATE=0` and `PAYMENT_PRODUCTION_EXTRA_LATENCY_MS=0`. |
| `02` telemetry-driven failure | Use `PAYMENT_PRODUCTION_FAILURE_MODE=none`, `PAYMENT_PRODUCTION_FORCE_ERROR_RATE=0.20`, then send real `/pay` traffic during canary. |
| `03` high latency | Use `PAYMENT_PRODUCTION_EXTRA_LATENCY_MS=800`, then send real `/pay` traffic during canary. |
| `04` observability failure | Use `BDI_PROMETHEUS_URL=http://localhost:19090` so Java cannot query Prometheus. |
| `05` transient health retry | Use `BDI_FORCE_HEALTH_CHECK_PRODUCTION_FAIL_ONCE=true`. |
| `06` gate failures | Use one of `BDI_FORCE_BUILD_FAIL=true`, `BDI_FORCE_TEST_FAIL=true`, or `BDI_FORCE_SECURITY_SCAN_FAIL=true`. |
| `07` rollback unavailable | Use telemetry failure setup plus `BDI_FORCE_ROLLBACK_PRODUCTION_FAIL=true`. |

Important distinction:

```text
PAYMENT_* variables affect the app container after deploy/recreate.
BDI_FORCE_* variables are Java-environment test hooks that create action-result percepts.
Only real traffic plus Prometheus metrics proves telemetry-driven behavior.
```

## Case 1: Successful Path

Goal:

```text
prove Jason can complete the release when action results and telemetry stay healthy
```

Start Jason with healthy application behavior:

```powershell
cd C:\NHI\2026_IT-Project\260023_BDI_CICD\bdi

$env:BDI_TELEMETRY_ENABLED="true"
$env:BDI_TELEMETRY_INTERVAL_SECONDS="3"
$env:BDI_TELEMETRY_GRACE_SECONDS="5"
$env:BDI_OBSERVE_PRODUCTION_CANARY_MS="15000"

$env:PAYMENT_STAGING_FAILURE_MODE="none"
$env:PAYMENT_PRODUCTION_FAILURE_MODE="none"
$env:PAYMENT_PRODUCTION_FORCE_ERROR_RATE="0"
$env:PAYMENT_PRODUCTION_EXTRA_LATENCY_MS="0"

jason project.mas2j
```

Do not inject errors.

Watch for:

```text
percept status(build, passed)
percept status(test, passed)
percept status(security_scan, passed)
percept status(deploy(staging), passed)
percept status(health_check(staging), passed)
percept status(deploy(production), passed)
percept status(health_check(production), passed)
[CicdEnvironment][decision] observe_production_canary
[CicdEnvironment][observe] complete environment=production phase=canary state=stable
percept observation(production, canary, stable)
[CicdEnvironment][decision] delivery_succeeded reason=candidate
[CicdEnvironment][decision] release_complete
```

Final version should be:

```powershell
Get-Content .\runtime\state\production_version.txt
```

Expected:

```text
candidate
```

Automated equivalent:

```powershell
powershell -ExecutionPolicy Bypass -File .\experiments\demo_successful_path.ps1
```

## Case 2: Telemetry Failure During Production Canary

Goal:

```text
prove Jason reacts to a real environment/telemetry change before accepting release_complete
```

Start Jason with production candidate configured for probabilistic `/pay` failures:

```powershell
cd C:\NHI\2026_IT-Project\260023_BDI_CICD\bdi

$env:BDI_TELEMETRY_ENABLED="true"
$env:BDI_TELEMETRY_INTERVAL_SECONDS="3"
$env:BDI_TELEMETRY_GRACE_SECONDS="5"
$env:BDI_OBSERVE_PRODUCTION_CANARY_MS="35000"

$env:PAYMENT_STAGING_FAILURE_MODE="none"
$env:PAYMENT_PRODUCTION_FAILURE_MODE="none"
$env:PAYMENT_PRODUCTION_FORCE_ERROR_RATE="0.20"
$env:PAYMENT_PRODUCTION_EXTRA_LATENCY_MS="0"

jason project.mas2j
```

Wait until this appears:

```text
[CicdEnvironment] percept status(health_check(production), passed)
[CicdEnvironment][decision] observe_production_canary
[CicdEnvironment][observe] start environment=production phase=canary
```

Then, in another terminal, trigger real business traffic:

```powershell
cd C:\NHI\2026_IT-Project\260023_BDI_CICD

1..80 | ForEach-Object {
  try {
    Invoke-RestMethod -Method POST -Uri http://localhost:8002/pay -ContentType "application/json" -Body "{`"amount`": $_}"
  } catch {
    "pay request failed as part of configured error rate"
  }
}
```

What this proves:

```text
The trigger is not a BDI_FORCE flag.
The trigger is application behavior plus real HTTP traffic.
Jason must perceive the result through Prometheus telemetry.
FORCE_ERROR_RATE does not create requests by itself; it only changes the probability that real requests fail.
```

Watch for:

```text
[CicdEnvironment][telemetry] production error_rate=0.xxxx(high) ... environment=unstable
[CicdEnvironment] percept observation(production, canary, unstable)
[CicdEnvironment][decision] recovery_reason reason=telemetry_unstable
[CicdEnvironment] action ... rollback.sh production
[CicdEnvironment] percept status(rollback(production), passed)
[CicdEnvironment][decision] production_reliability_restored reason=telemetry_unstable
[CicdEnvironment][decision] delivery_failed reason=telemetry_unstable
```

Expected agent beliefs:

```text
metric(production,error_rate,high)[source(percept)]
environment(production,unstable)[source(percept)]
observation(production,canary,unstable)[source(percept)]
recovery_reason(telemetry_unstable)[source(self)]
production_reliability_restored[source(self)]
delivery_failed(candidate,telemetry_unstable)[source(self)]
decision(delivery_failed)[source(self)]
```

Final version should be:

```text
stable
```

Automated equivalent:

```powershell
powershell -ExecutionPolicy Bypass -File .\experiments\demo_failed_telemetry_path.ps1
```

## Case 2B: Goal Persistence After Transient Production Health Failure

Goal:

```text
prove Jason does not treat the first production problem as the end of the delivery goal
```

This is a controlled action-result scenario, not a telemetry scenario. It is useful because it proves goal persistence:

```text
production health fails once
-> Jason restores production reliability with rollback
-> Jason verifies recovered production
-> Jason retries candidate deployment
-> Jason reaches delivery_succeeded(candidate)
```

Start Jason:

```powershell
cd C:\NHI\2026_IT-Project\260023_BDI_CICD\bdi

$env:BDI_TELEMETRY_ENABLED="false"
$env:BDI_OBSERVE_PRODUCTION_CANARY_MS="1000"
$env:BDI_FORCE_HEALTH_CHECK_PRODUCTION_FAIL_ONCE="true"

jason project.mas2j
```

Watch for:

```text
forced_failure stage=health_check_production
percept status(health_check(production), failed)
[CicdEnvironment][decision] recovery_reason reason=health_failed
[CicdEnvironment][decision] production_reliability_restored reason=health_failed
[CicdEnvironment][decision] rollback_then_retry_production reason=health_failed
[CicdEnvironment][decision] continue_deploy_candidate reason=health_failed
[CicdEnvironment][decision] delivery_succeeded reason=candidate
```

Expected agent beliefs:

```text
production_reliability_restored[source(self)]
production_reliability_restored(health_failed)[source(self)]
decision(rollback_then_retry_production)[source(self)]
decision(continue_deploy_candidate)[source(self)]
delivery_succeeded(candidate)[source(self)]
```

What it proves:

```text
Rollback restored safety, but the agent did not stop there.
It continued pursuing the original candidate delivery goal and succeeded after retry.
```

## Case 3: High Latency During Production Canary

Goal:

```text
prove Jason does not blindly rollback every telemetry problem
```

Start Jason with latency added to production:

```powershell
cd C:\NHI\2026_IT-Project\260023_BDI_CICD\bdi

$env:BDI_TELEMETRY_ENABLED="true"
$env:BDI_TELEMETRY_INTERVAL_SECONDS="3"
$env:BDI_TELEMETRY_GRACE_SECONDS="5"
$env:BDI_OBSERVE_PRODUCTION_CANARY_MS="25000"

$env:PAYMENT_STAGING_FAILURE_MODE="none"
$env:PAYMENT_PRODUCTION_FAILURE_MODE="none"
$env:PAYMENT_PRODUCTION_FORCE_ERROR_RATE="0"
$env:PAYMENT_PRODUCTION_EXTRA_LATENCY_MS="800"

jason project.mas2j
```

Wait for canary observation to start:

```text
[CicdEnvironment][observe] start environment=production phase=canary
```

Then send successful traffic:

```powershell
1..8 | ForEach-Object {
  Invoke-RestMethod -Method POST -Uri http://localhost:8002/pay -ContentType "application/json" -Body "{`"amount`": $_}"
}
```

Watch for:

```text
metric(production,latency,high)
[CicdEnvironment][decision] pause_reobserve reason=high_latency
```

What it proves:

```text
Jason distinguishes ambiguous latency from definite application error.
The plan is pause/reobserve, not immediate rollback.
```

## Case 4: Telemetry/Prometheus Unavailable During Canary

Goal:

```text
prove Jason can distinguish observability failure from application failure
```

Start a normal deployment:

```powershell
cd C:\NHI\2026_IT-Project\260023_BDI_CICD\bdi

$env:BDI_TELEMETRY_ENABLED="true"
$env:BDI_TELEMETRY_INTERVAL_SECONDS="3"
$env:BDI_TELEMETRY_GRACE_SECONDS="5"
$env:BDI_OBSERVE_PRODUCTION_CANARY_MS="25000"
$env:PAYMENT_PRODUCTION_FAILURE_MODE="none"

jason project.mas2j
```

Wait for:

```text
[CicdEnvironment][observe] start environment=production phase=canary
```

Then stop Prometheus:

```powershell
cd C:\NHI\2026_IT-Project\260023_BDI_CICD
docker compose stop prometheus
```

Watch for:

```text
percept telemetry(production, unavailable)
percept network(production, suspected)
percept environment(production, unstable)
[CicdEnvironment][decision] pause_reobserve reason=network_suspected
[CicdEnvironment][decision] manual_intervention_required reason=network_suspected
```

What it proves:

```text
Jason does not blindly rollback when it cannot trust telemetry.
It treats observability failure as a different reason.
```

## Case 5: Build/Test/Security Gate Failure

These scenarios are different.

Current model status:

```text
Build/test/security failures cannot be triggered midway by changing telemetry.
They are action-result gate failures.
```

Today, they are configured before Jason starts using controlled fault injection:

```powershell
$env:BDI_FORCE_BUILD_FAIL="true"
$env:BDI_FORCE_TEST_FAIL="true"
$env:BDI_FORCE_SECURITY_SCAN_FAIL="true"
```

Example: build failure.

```powershell
cd C:\NHI\2026_IT-Project\260023_BDI_CICD\bdi
$env:BDI_TELEMETRY_ENABLED="false"
$env:BDI_FORCE_BUILD_FAIL="true"
jason project.mas2j
```

Watch for:

```text
forced_failure stage=build
percept status(build, failed)
[CicdEnvironment][decision] delivery_failed reason=build_failed
```

What it proves:

```text
Jason records an explicit candidate delivery failure after an action-result percept.
```

What it does not prove:

```text
It does not prove Prometheus telemetry perception.
It is not the main real-time environment demo.
```

## Can We Trigger Build/Test/Security Failure Midway Today?

Not cleanly.

Reason:

```text
BDI_FORCE_* variables are read by the Java process environment.
Changing them in another terminal after Jason has started does not reliably update the running Java process.
```

Also, build/test/security are short shell actions. They are not long-running observation phases.

So this instruction is not currently correct:

```text
When MAS Console shows build OK, type a command in another terminal to make test fail.
```

The current system is not built that way yet.

## How To Make The Model Support Midway Gate Injection

To support true midway gate injection for build/test/security, add a runtime control channel that the running Java environment can read.

Recommended small implementation:

```text
runtime/control/fail_next_stage.txt
```

Example manual trigger:

```powershell
Set-Content .\runtime\control\fail_next_stage.txt "test"
```

Then `CicdEnvironment.java` would check the file immediately before running each action:

```text
if file says "test" and Jason calls test(candidate):
    consume the file
    return status(test, failed)
```

This would allow:

```text
start Jason
wait for build passed
write "test" into runtime/control/fail_next_stage.txt
Jason calls test(candidate)
CicdEnvironment returns status(test,failed)
Jason stops release
```

Even better implementation:

```text
runtime/control/stage_delay_ms.yml
runtime/control/fail_next_stage.txt
runtime/control/payment_runtime_mode.txt
```

That would let the demo operator slow or fail specific stages while the MAS is already running.

But for the current research goal, the strongest demos are already supported:

```text
successful path
telemetry high error during canary
high latency during canary
Prometheus unavailable during canary
```

These prove live environment perception better than forced build/test failures.
