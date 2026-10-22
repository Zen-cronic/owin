# Deploying Owin on Nebius AI Cloud (Serverless AI endpoint)

Owin is one container: the answer screen, `/judge` and the JSON API on one HTTP port. Serving a page never calls a
paid API (every answer is computed from recorded Nemotron runs and committed page captures), so the public endpoint
needs **no keys**: it runs in **demo mode**, labelled in the app footer and in `GET /healthz`. The keys belong only to
the daily refresh job (A2, below).

Sources, read 2026-10-22: [Serverless AI endpoints: manage](https://docs.nebius.com/serverless/endpoints/manage),
[Tutorial: deploy a model](https://docs.nebius.com/serverless/tutorials/deploy-model),
[VM types and presets](https://docs.nebius.com/compute/virtual-machines/types),
[Compute pricing](https://docs.nebius.com/compute/resources/pricing),
[Serverless AI jobs: manage](https://docs.nebius.com/serverless/jobs/manage).
Anything not in those pages is marked **UNVERIFIED**.

## Configuration (environment variables only)

| variable | endpoint | daily job | meaning |
|---|---|---|---|
| `PORT` | `8080` (image default) | not used | port `owin serve` binds; must equal `--container-port` |
| `OWIN_HOST` | `0.0.0.0` (image default) | not used | bind address |
| `OWIN_STATE_DIR` | optional, `/state` (read-only bucket) | **required**, `/state` (read-write bucket) | refreshed observations and list snapshots; unset = committed state only |
| `TOKEN_FACTORY_API_KEY` | **do not set** | not needed for `owin job daily` | only `owin pack extract` / `owin eval run` call Token Factory |
| `TAVILY_API_KEY` | **do not set** | SecretStash secret | `owin job daily` re-fetches vendor pages with Tavily |
| `OWIN_LEDGER` | image default | `/state/ledger/usage.jsonl` | Token Factory spend ledger |

The image never contains `.env`, `fixtures/raw/` (vendor page text), `var/`, the spend ledger, tests or design files:
`.dockerignore` is an allowlist. It runs as the non-root user `owin` (uid 10001). Without `fixtures/raw/` the line-one
number recomputes identically (27/33, 26/27, 6); only `quotes_rechecked_against_source` in `/api/selective` reads
`false`, because quote re-checking needs the page text.

## 1. Build and push the image (on the Linux machine; Docker is not installed on the Mac)

The CPU platforms are x86 (`cpu-d3` is AMD EPYC Genoa), so build for `linux/amd64`.

```bash
cd /path/to/owin
git checkout main            # or feat/owin/finish
TAG=$(git rev-parse --short HEAD)
docker build --platform linux/amd64 -t owin:$TAG .
# Local check before pushing: demo mode, no keys, same env contract as the endpoint.
docker run --rm -d --name owin-local -p 8080:8080 owin:$TAG
scripts/smoke.sh http://127.0.0.1:8080          # expect: SMOKE PASS
docker exec owin-local id -u                     # expect: 10001 (not root)
docker exec owin-local sh -c 'ls -a /app; test ! -e /app/.env && test ! -e /app/fixtures/raw/datause'   # no secrets, no raw pages
docker rm -f owin-local
```

Option A, **GitHub Container Registry** (public image, so the endpoint needs no registry credentials):

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u zen-cronic --password-stdin   # PAT with write:packages
docker tag owin:$TAG ghcr.io/zen-cronic/owin:$TAG
docker push ghcr.io/zen-cronic/owin:$TAG
# Then GitHub -> Profile -> Packages -> owin -> Package settings -> Change visibility -> Public.
export IMAGE=ghcr.io/zen-cronic/owin:$TAG
```

Option B, **Nebius Container Registry** in the same project. The endpoint docs say no credentials are needed for
"Container Registry in the same project". The registry create/login commands and the image path format below are
**UNVERIFIED** (not on the pages read); check `nebius registry --help` and the Container Registry docs first.

```bash
nebius registry create --name owin                         # UNVERIFIED syntax
# docker login / tag / push to cr.<region>.nebius.cloud/<registry-id>/owin:$TAG   # UNVERIFIED path format
export IMAGE=cr.<region>.nebius.cloud/<registry-id>/owin:$TAG
```

## 2. Create the endpoint

Smallest CPU option in the docs: platform **`cpu-d3`** (Non-GPU AMD EPYC Genoa, all regions), preset **`2vcpu-8gb`**.
Price (USD, regular VM): $0.012 per vCPU-hour + $0.0032 per GiB-hour = 2 x 0.012 + 8 x 0.0032 = **$0.0496/hour,
about $1.19/day or $36.2 per 730-hour month**, plus the container disk (Network SSD $0.071 per GiB-month: 32 GiB is
about $2.27/month; the 250 GiB default would be about $17.75/month). The disk type the endpoint uses, and whether
32 GiB is above its minimum, are **UNVERIFIED**. Stopped endpoints are not charged for compute. Each endpoint's
managed URL is limited to 120 Mbps and 300 new connections per second (Nebius Tunnels limits).

No `--auth`: the default is no authentication, so judges reach the app with no login. Do not pass `--auth token`.

### Console

1. **Serverless AI -> Endpoints -> Create endpoint.** Name `owin`. **Configuration:** Custom.
2. **Image path:** the `$IMAGE` above. **Private registry:** leave empty (public ghcr.io image, or Nebius registry in
   the same project). **Ports:** `8080`. **Entrypoint command:** leave empty (the image's `CMD` runs `owin serve`).
3. **Environment variables:** `PORT=8080`, `OWIN_HOST=0.0.0.0`. **Secret environment variables:** none.
   **Authentication:** leave disabled.
4. **Computing resources:** without GPU, regular VM, platform Non-GPU AMD EPYC Genoa (`cpu-d3`), preset `2vcpu-8gb`.
5. **Storage:** container disk 32 GiB. No volume for the first deploy.
6. **Network:** the project's subnet, **Public static IP** (chosen for this deploy; the docs note the managed HTTPS URL
   works without it).
7. **Create endpoint.** Wait for `Running` (the GPU tutorial quotes about five minutes).

### CLI (same settings)

```bash
export SUBNET_ID=$(nebius vpc subnet list --format jsonpath='{.items[0].metadata.id}')
nebius ai endpoint create \
  --name owin \
  --image "$IMAGE" \
  --container-port 8080 \
  --env "PORT=8080,OWIN_HOST=0.0.0.0" \
  --platform cpu-d3 \
  --preset 2vcpu-8gb \
  --disk-size 32Gi \
  --public \
  --subnet-id "$SUBNET_ID"
export ENDPOINT_ID=$(nebius ai endpoint get-by-name --name owin --format json | jq -r '.metadata.id')
nebius ai endpoint get "$ENDPOINT_ID"            # wait for status Running
export ENDPOINT_URL=$(nebius ai endpoint get-by-name --name owin --format json \
  | jq -r '.status.public_endpoints[] | select(startswith("https://"))' | head -1)
echo "$ENDPOINT_URL"
```

## 3. Smoke test (required before handing anyone the URL)

```bash
scripts/smoke.sh "$ENDPOINT_URL"
```

It checks `/healthz`, `/`, `/judge`, `/api/selective`, `/api/pack`, `/pack/print` (plus `/app.js`, `/api/catalog`)
return 200 **on the deployment itself** (the effective URL after redirects must still start with `$ENDPOINT_URL`, so
a login wall fails), that `/healthz` says `ok`, that the line-one number recomputes, and that 12 concurrent pack
builds all return 200. Expected last line: `SMOKE PASS <url>`. Then open `$ENDPOINT_URL/judge` in a private window.

Stop or delete when done: `nebius ai endpoint stop "$ENDPOINT_ID"` (keeps it, no compute charge; API path documented
as `/ai/v1/endpoints/stop`, CLI verb **UNVERIFIED**) or `nebius ai endpoint delete "$ENDPOINT_ID"`.

## 4. A2: daily refresh on Serverless AI jobs (documented, not executed)

`owin job daily` runs `owin sweep --live` (29-vendor index) and `owin pack refresh` (Tavily `extract` on the 7
pages the demo relies on, about 7 credits per run) in one process and writes only into `$OWIN_STATE_DIR`. It refuses to
run without `OWIN_STATE_DIR`. A free wiring check that makes no Tavily calls: `OWIN_STATE_DIR=$(mktemp -d) owin job daily --no-fetch`.

1. Create an Object Storage bucket for state, for example `owin-state` (console: Object Storage -> Create bucket).
2. Store the Tavily key in SecretStash: console -> SecretStash -> Create secret, name `owin-keys`, payload key
   `TAVILY_API_KEY`, value = the key. (The endpoint's console form also offers "Create secret" under **Secret
   environment variables**.) Never put the key in `--env`, the image or the repo.
3. Run the job:

```bash
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
```

4. Point the endpoint at the same bucket, read-only, so "last checked" on the app is real: add
   `--volume "owin-state:/state:ro"` and `OWIN_STATE_DIR=/state` to the endpoint (console: Storage -> Mounted volumes;
   Environment variables). With an empty bucket the app falls back to the committed state, so this is safe to do first.
5. **Daily trigger: UNVERIFIED.** The jobs page describes jobs as "one-off or scheduled" but documents no schedule
   flag. Until a schedule option is confirmed in `nebius ai job create --help`, trigger it from the Linux machine:
   `crontab -e` -> `0 10 * * * cd /path/to/owin && ./deploy/run-daily-job.sh`
   (10:00 UTC = 06:00 EDT), where that script holds the command in step 3. Each run is a new job; delete old ones
   with `nebius ai job delete <id>`.

Cost of the job: the same `cpu-d3` / `2vcpu-8gb` rate ($0.0496/hour), billed only while it runs (a sweep plus a
refresh takes minutes), plus about 7 Tavily credits per day.

## What was and was not validated (2026-10-22, no Docker on this machine)

- Validated: the build context was emulated from the `.dockerignore` allowlist (97 files, 1.5 MB, no `.env`, no
  `fixtures/raw/`); `owin serve` ran from that tree with an empty environment (no keys, no `.env`) bound to
  `0.0.0.0:$PORT`, and `scripts/smoke.sh` passed against it (demo mode, 12 concurrent requests). `owin job daily
  --no-fetch` wrote only into a temporary `OWIN_STATE_DIR`. `tests/test_deploy.py` checks the env contract, `/healthz`,
  the state-dir fallback and the Dockerfile/allowlist rules.
- Not validated: `docker build` itself (Poetry 2.5.1 editable install into `/venv` in the build stage), the
  `HEALTHCHECK`, any `nebius` command, registry pushes, and the endpoint's behaviour with `--public`. No hadolint was
  available; the Dockerfile was reviewed by hand (pinned base family, no secrets in `ENV`/`ARG`, non-root `USER`,
  exec-form-equivalent `CMD` via `exec`, no `apt-get`, no cache left by pip).
