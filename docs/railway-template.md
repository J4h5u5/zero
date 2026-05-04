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

Current verified public demo:
[https://zero-production-5214.up.railway.app](https://zero-production-5214.up.railway.app)

The latest Railway Template Publish Packet is committed at
[`contracts/distribution/railway-template.json`](../contracts/distribution/railway-template.json).
It records the live demo URL, point-in-time verified deployment id, evidence
bundle path, doctor result, required variables, autodeploy config, and
marketplace publish steps.

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
| Template icon | `docs/assets/zero-template-icon.svg` |
| Service icon | `docs/assets/zero-template-icon.svg` |
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

### Marketplace Overview Copy

Use this copy in Railway's template overview editor. It follows Railway's
recommended H1/H2 structure and should stay in sync with this page.

```md
# Deploy and Host ZERO with Railway

ZERO is an autonomous operating system for self-custodial onchain operations.
This template runs the public paper runtime: live Hyperliquid prices are
read-only, execution is simulated, journals persist on a Railway volume, and
live-risk endpoints fail closed by default.

## About Hosting ZERO

Hosting ZERO on Railway gives operators a public paper runtime with a stable
URL, logs, metrics, health checks, and a persistent journal volume. It does not
custody funds and does not need exchange private keys. Use it for operator
onboarding, public proof capture, agentic development, and first-run demos
against a real HTTP runtime.

## Common Use Cases

- Paper-mode operator demos with live read-only Hyperliquid mids.
- Public proof capture before sharing a profile or leaderboard claim.
- Agentic development against a stable remote ZERO runtime.
- Railway doctor, deployment evidence, and rollback rehearsal practice.

## Dependencies for ZERO Hosting

- Railway service sourced from `https://github.com/zero-intel/zero`.
- Dockerfile build from the repository root.
- Public HTTP networking enabled for the runtime service.
- Persistent Railway volume mounted at `/data`.
- Railway-provided `PORT`.

### Why Deploy ZERO on Railway?

Railway gives operators a fast paper-runtime rollout path without asking ZERO
to host custody infrastructure. Operators keep their own project boundary,
volume, logs, domains, variables, and billing relationship while ZERO stays
inspectable, interruptible, and paper-first by default.
```

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

## Railway Template Publish Packet

The packet schema is `zero.railway_template_packet.v1`. Regenerate it after any
template-impacting deployment, Railway variable change, domain change, or
marketplace copy change. Deployment ids are point-in-time evidence; always run
the doctor against the live URL before sharing the current service:

```bash
scripts/railway_template_packet.py --output contracts/distribution/railway-template.json
scripts/railway_template_packet.py --check
```

Before replacing the README deploy button placeholder with Railway's issued
template URL, verify the live demo:

```bash
scripts/railway_doctor.py https://zero-production-5214.up.railway.app
scripts/deployment_evidence.sh https://zero-production-5214.up.railway.app --railway-logs
scripts/deployment_evidence_verify.py artifacts/deployment-evidence/<timestamp>
```

The expected public demo posture is `17 ok / 1 warn / 0 fail`: the warning is
the tokened paid-scope Intelligence check when no demo bearer token is supplied.
Live mode must remain refused and risk-increasing actions must remain blocked.

### Publish Checklist

1. Install and authenticate the Railway CLI:

```bash
npm install -g @railway/cli
railway login --browserless
scripts/railway_cli_preflight.py
```

2. From the live project canvas, open **Settings** and use **Generate Template from Project**.
   Railway documents template creation through the dashboard,
   not the normal CLI.
3. Confirm the generated template keeps the GitHub source, Dockerfile build,
   `/health` health check, public HTTP networking, and `/data` volume.
4. Add `docs/assets/zero-template-icon.svg` as the template and service icon.
5. Paste the Marketplace Overview Copy from this page.
6. Publish the template from Railway workspace settings.
7. Apply to the Open Source Partner Program at
   `https://railway.com/partners` using [railway-partner.md](railway-partner.md).
8. Add the live demo project after `scripts/railway_doctor.py "$ZERO_RAILWAY_URL"` passes.
9. Replace `<template-code>` in the README button with Railway's issued template code:

```md
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template/<template-code>?utm_medium=integration&utm_source=button&utm_campaign=zero)
```

10. Keep [docs/release.md](release.md) and the template packet current before
   merging template-impacting changes to `main`.

### Partner And Support Packet

Railway's partner program is a manual application. The prepared application
packet lives in [railway-partner.md](railway-partner.md) and includes the
maintainer summary, template evidence, support queue commitment, update policy,
and submission message. After publishing the template, keep the Template Queue
at https://station.railway.com/my-template-queue clear during launch week.

## Why Deploy ZERO on Railway?

Railway gives operators a fast paper-runtime rollout path without asking ZERO
to host custody infrastructure. Operators keep their own project boundary,
volume, logs, domains, variables, and billing relationship while ZERO stays
inspectable, interruptible, and paper-first by default.
