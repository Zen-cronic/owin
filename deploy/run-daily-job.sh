#!/usr/bin/env bash
# A2 daily refresh: start one Nebius Serverless AI job that runs `owin job daily` against the state bucket.
# Documented in DEPLOY.md section 4; not executed by the build agent. Needs the nebius CLI (configured for the
# project), IMAGE set to the pushed image, an `owin-state` bucket and an `owin-keys` SecretStash secret with
# payload key TAVILY_API_KEY. Daily trigger: cron on the Linux machine until a job schedule option is confirmed.
set -euo pipefail
: "${IMAGE:?set IMAGE to the pushed owin image, e.g. ghcr.io/zen-cronic/owin:<tag>}"
SUBNET_ID="${SUBNET_ID:-$(nebius vpc subnet list --format jsonpath='{.items[0].metadata.id}')}"
nebius ai job create \
  --name "owin-daily-$(date -u +%Y%m%d)" \
  --image "$IMAGE" \
  --container-command owin \
  --args "job daily" \
  --env "OWIN_STATE_DIR=/state,OWIN_LEDGER=/state/ledger/usage.jsonl" \
  --env-secret "TAVILY_API_KEY=owin-keys" \
  --volume "owin-state:/state:rw" \
  --platform cpu-d3 \
  --preset 2vcpu-8gb \
  --disk-size 32Gi \
  --timeout 1h \
  --restart-policy never \
  --subnet-id "$SUBNET_ID"
