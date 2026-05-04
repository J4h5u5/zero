# Deploy and Host ZERO with Railway

ZERO is an autonomous operating system for self-custodial onchain operations.
This Railway template runs the public paper runtime: live Hyperliquid prices are
read-only, execution is simulated, journals are durable, and live-risk endpoints
fail closed unless an operator-owned local live executor is configured outside
the template.

## About Hosting ZERO

Hosting ZERO on Railway gives an operator a public paper runtime with a stable
URL, logs, metrics, health checks, and a persistent journal volume. It does not
custody funds and does not need exchange keys. The deployment is useful for
operator onboarding, public demos, proof capture, Railway doctor checks, and
agentic contribution work against a real HTTP runtime.

## Common Use Cases

- Paper-mode operator demos with live read-only Hyperliquid mids.
- Public proof capture before sharing a profile or leaderboard claim.
- Agentic development against a stable remote ZERO runtime.
- Railway doctor, deployment evidence, and rollback rehearsal practice.
- ZERO Intelligence contract testing with local aggregate persistence.

## Dependencies for ZERO Hosting

- Railway service sourced from `https://github.com/zero-intel/zero`.
- Dockerfile build from the repository root.
- Public HTTP networking enabled for the runtime service.
- Persistent Railway volume mounted at `/data`.
- Railway-provided `PORT`; do not hardcode a port.

### Deployment Dependencies

- Railway template docs: https://docs.railway.com/templates
- Railway template best practices: https://docs.railway.com/templates/best-practices
- Railway publish/share docs: https://docs.railway.com/templates/publish-and-share
- ZERO Railway deploy guide: [railway-deploy.md](railway-deploy.md)

### Template Service Settings

| Setting | Value |
| --- | --- |
| Template name | `ZERO Paper Runtime` |
| Service name | `ZERO` |
| Source | GitHub repository |
| Repository | `zero-intel/zero` |
| Branch | `main` |
| Builder | Dockerfile |
| Dockerfile path | `Dockerfile` |
| Start command | from `railway.toml`: `/app/scripts/railway_start.sh` |
| Healthcheck path | `/health` |
| Healthcheck timeout | `60` |
| Public networking | HTTP enabled |
| Volume mount | `/data` |

### Template Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `ZERO_MODE` | yes | `paper` | Keeps the template in paper mode. |
| `ZERO_JOURNAL_PATH` | yes | `/data/decisions.jsonl` | Durable append-only paper journal on the Railway volume. |
| `ZERO_HYPERLIQUID_LIVE_PRICES` | yes | `true` | Uses Hyperliquid public mids as read-only market data. |
| `ZERO_INTELLIGENCE_STORE_PATH` | yes | `/data/zero/intelligence.jsonl` | Durable aggregate store for hosted-compatible Intelligence reference endpoints. |
| `ZERO_INTELLIGENCE_API_TOKEN` | optional | empty | Disposable demo bearer token for hosted-compatible protected Intelligence routes. |
| `ZERO_INTELLIGENCE_API_PLAN` | optional | `free` | Reference account plan shown by local hosted-compatible packets. |
| `ZERO_INTELLIGENCE_API_ACCOUNT_ID` | optional | `acct_railway` | Public-safe local account label for reference packets. |
| `ZERO_INTELLIGENCE_WEBHOOK_SIGNING_KEY` | optional | `${{secret(64, "abcdef0123456789")}}` | Demo HMAC key for webhook fixture signatures. Never reuse production keys. |

### Publish Checklist

1. Install and authenticate the Railway CLI:

```bash
npm install -g @railway/cli
railway login --browserless
scripts/railway_cli_preflight.py
```

2. Create the template from a Railway project based on this GitHub repository.
3. Confirm the `/data` volume is attached before the first public deploy.
4. Publish the template from Railway workspace settings.
5. Add the live demo project after `scripts/railway_doctor.py "$ZERO_RAILWAY_URL"` passes.
6. Replace `<template-code>` in the README button with Railway's issued template code:

```md
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template/<template-code>?utm_medium=integration&utm_source=button&utm_campaign=zero)
```

7. Keep [CHANGELOG.md](../CHANGELOG.md) current before merging template-impacting changes to `main`.

## Why Deploy ZERO on Railway?

Railway gives operators a fast paper-runtime rollout path without asking ZERO
to host custody infrastructure. Operators keep their own project boundary,
volume, logs, domains, variables, and billing relationship while ZERO stays
inspectable, interruptible, and paper-first by default.
