#!/usr/bin/env bash
set -euo pipefail
# Mechanical operations shared by BDI and conventional execution.
case "$ENTITY" in
  build)
    if [ "${FAILURE_MODE:-none}" = "transient_failure" ]; then
    # Controlled transient failure
    (
      exit 75
    )
    fi
    if [ "${FAILURE_MODE:-none}" = "force_failure" ]; then
    # Controlled experiment failure
    (
      exit 1
    )
    fi
    # npm ci
    (
      npm ci
    )
    # npm run lint
    (
      npm run lint
    )
    # npm run build
    (
      npm run build
    )
    # docker build --tag payment-service:${{ inputs.release_sha }} .
    (
      docker build --tag payment-service:${RELEASE_SHA} .
    )
    ;;
  test)
    if [ "${FAILURE_MODE:-none}" = "transient_failure" ]; then
    # Controlled transient failure
    (
      exit 75
    )
    fi
    if [ "${FAILURE_MODE:-none}" = "force_failure" ]; then
    # Controlled experiment failure
    (
      exit 1
    )
    fi
    # npm ci
    (
      npm ci
    )
    # npm run db:migrate
    (
      npm run db:migrate
    )
    # npm test
    (
      npm test
    )
    # python -m pip install PyYAML==6.0.3
    (
      python -m pip install PyYAML==6.0.3
    )
    # python -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py' -v
    (
      python -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py' -v
    )
    ;;
  security)
    if [ "${FAILURE_MODE:-none}" = "transient_failure" ]; then
    # Controlled transient failure
    (
      exit 75
    )
    fi
    if [ "${FAILURE_MODE:-none}" = "force_failure" ]; then
    # Controlled experiment failure
    (
      exit 1
    )
    fi
    # npm ci
    (
      npm ci
    )
    # Production dependency security gate
    (
      npm audit --omit=dev --audit-level=high
    )
    ;;
  staging)
    if [ "${FAILURE_MODE:-none}" = "transient_failure" ]; then
    # Controlled transient failure
    (
      exit 75
    )
    fi
    if [ "${FAILURE_MODE:-none}" = "force_failure" ]; then
    # Controlled experiment failure
    (
      exit 1
    )
    fi
    if [ "${FAILURE_MODE:-none}" = "deployment_timeout" ]; then
    # Controlled deployment timeout before side effects
    sleep 90
    exit 124
    fi
    # Check runner tools
    (
      docker info && docker compose version && curl --version
    )
    # Deploy selected revision to staging
    (
      docker compose up -d --build
    )
    if [ "${FAILURE_MODE:-none}" = "service_unavailable" ]; then
    # Make deployment service unavailable
    (
      docker compose stop app
    )
    fi
    if [ "${FAILURE_MODE:-none}" = "infrastructure_failure" ]; then
    # Stop deployment database infrastructure
    (
      docker compose stop postgres
    )
    fi
    # Verify staging identity and readiness
    (
      for attempt in {1..12}; do
        if health=$(curl --fail --silent http://127.0.0.1:3001/health) &&
          grep -Fq "\"deploymentRunId\":\"${CI_RUN_ID}\"" <<< "$health" &&
          curl --fail --silent http://127.0.0.1:3001/ready; then exit 0; fi
        sleep 5
      done
      docker compose logs --tail=100 app
      exit 1
    )
    # Generate run-correlated telemetry
    (
      export PAYMENT_BASE_URL="http://127.0.0.1:3001"
      export PROMETHEUS_URL="http://127.0.0.1:9091"
      for attempt in {1..3}; do
        docker compose exec -T -e PAYMENT_BASE_URL=http://127.0.0.1:3000 app node --input-type=module - "$EXPERIMENT_MODE" 6 < scripts/generate-experiment-traffic.mjs
        sleep 5
      done
    )
    ;;
  production)
    if [ "${FAILURE_MODE:-none}" = "transient_failure" ]; then
    # Controlled transient failure
    (
      exit 75
    )
    fi
    if [ "${FAILURE_MODE:-none}" = "deployment_timeout" ]; then
    # Controlled deployment timeout before side effects
    sleep 90
    exit 124
    fi
    # Check runner tools
    (
      docker info && docker compose version && curl --version
    )
    # Deploy selected revision to production
    (
      docker compose up -d --build
    )
    if [ "${FAILURE_MODE:-none}" = "service_unavailable" ]; then
    # Make deployment service unavailable
    (
      docker compose stop app
    )
    fi
    if [ "${FAILURE_MODE:-none}" = "infrastructure_failure" ]; then
    # Stop deployment database infrastructure
    (
      docker compose stop postgres
    )
    fi
    if [ "${FAILURE_MODE:-none}" = "force_failure" ]; then
    # Controlled post-deployment failure
    (
      exit 1
    )
    fi
    # Verify production identity, readiness, and telemetry
    (
      for attempt in {1..12}; do
        if health=$(curl --fail --silent http://127.0.0.1:3000/health) &&
          grep -Fq "\"deploymentRunId\":\"${CI_RUN_ID}\"" <<< "$health" &&
          curl --fail --silent http://127.0.0.1:3000/ready &&
          curl --fail --silent http://127.0.0.1:9464/metrics | grep -Fq payment_http_requests_total &&
          curl --fail --silent http://127.0.0.1:9090/-/ready; then exit 0; fi
        sleep 5
      done
      docker compose logs --tail=100 app otel-collector prometheus
      exit 1
    )
    # Generate production telemetry for BDI assessment
    (
      for attempt in {1..3}; do
        docker compose exec -T -e PAYMENT_BASE_URL=http://127.0.0.1:3000 app node --input-type=module - "$EXPERIMENT_MODE" 6 < scripts/generate-experiment-traffic.mjs
        sleep 5
      done
    )
    if [ "${FAILURE_MODE:-none}" = "candidate_stopped" ]; then
    # Inject stopped candidate after successful deployment
    (
      docker compose stop app
    )
    fi
    ;;
  rollback)
    # Check runner tools
    (
      docker info && docker compose version && curl --version
    )
    if [ "${FAILURE_MODE:-none}" = "force_failure" ]; then
    # Controlled recovery failure
    (
      exit 1
    )
    fi
    # Restore selected known-good source
    (
      docker compose up -d --build
    )
    # Verify restored execution identity and readiness
    (
      for attempt in {1..12}; do
        if health=$(curl --fail --silent http://127.0.0.1:3000/health) &&
          grep -Fq "\"deploymentRunId\":\"${CI_RUN_ID}\"" <<< "$health" &&
          curl --fail --silent http://127.0.0.1:3000/ready; then exit 0; fi
        sleep 5
      done
      docker compose logs --tail=100 app
      exit 1
    )
    # Generate restored-release telemetry for BDI verification
    (
      for attempt in {1..3}; do
        docker compose exec -T -e PAYMENT_BASE_URL=http://127.0.0.1:3000 app node --input-type=module - normal 6 < scripts/generate-experiment-traffic.mjs
        sleep 5
      done
    )
    ;;
  *) echo "Unknown entity: $ENTITY" >&2; exit 2;;
esac
