# Railway Partner Application Packet

This packet is the source of truth for submitting ZERO to Railway's Open Source
& Technology Partners program. Railway templates are the first hosted
distribution channel for ZERO because the public runtime is paper-first,
stateful, and useful without exchange keys.

## Application

| Field | Value |
| --- | --- |
| Program | Open Source Partnership first; Technology Partnership after community templates exist. |
| Application URL | https://railway.com/partners |
| Workspace | `zero` |
| Maintainer | `zero-intel` |
| Project | `ZERO` |
| Public repo | `https://github.com/zero-intel/zero` |
| Template name | `ZERO Paper Runtime` |
| Live demo | `https://zero-production-5214.up.railway.app` |
| Template docs | `docs/railway-template.md` |
| Evidence packet | `contracts/distribution/railway-template.json` |
| Support queue | https://station.railway.com/my-template-queue |
| Marketplace category | AI agents / developer tools / finance infrastructure |

## Partner Summary

ZERO is an autonomous operating system for self-custodial onchain operations.
The Railway template deploys the public paper runtime: live Hyperliquid prices
are read-only, execution is simulated, journals persist on a Railway volume, and
live-risk endpoints fail closed unless an operator configures a separate local
live executor outside the template.

The template is useful for operator onboarding, public proof capture, coding
agent development, and first-run demos. It does not custody funds, does not
require exchange private keys, and defaults to `ZERO_MODE=paper`.

## Template Verification Evidence

- Public demo is live and doctor-checked.
- `/health` is configured in `railway.toml`.
- `/data` is mounted as the durable journal volume.
- `scripts/railway_doctor.py` verifies the remote runtime posture.
- `scripts/deployment_evidence.sh` creates redacted evidence bundles.
- `contracts/distribution/railway-template.json` records current deployment
  evidence, doctor result, variables, and marketplace publish state.

## Support Commitment

ZERO will treat Railway template users as first-class operators:

- Monitor the Template Queue on business days during launch.
- Answer template deployment questions in Railway Central Station.
- Keep `docs/railway-template.md` updated before template-impacting releases.
- Publish breaking template changes in `docs/release.md`.
- Keep the public demo doctor-green before social promotion.

The support-bonus goal is practical product feedback, not just commission. Every
repeated Railway issue should become either a doc fix, a doctor check, or a
starter backlog issue.

## Template Update Policy

The template is sourced from the GitHub `main` branch so Railway can notify
deployed users about upstream updates. Template-impacting changes must update:

- `docs/railway-template.md`
- `docs/railway-deploy.md`, if runtime behavior changes
- `contracts/distribution/railway-template.json`
- `docs/release.md`, if operator action is required
- the public demo evidence bundle, when deployment posture changes

Docker-image-only private templates are reserved for future commercial
components. The open paper runtime template should stay GitHub-repo based so
Railway update notifications work for operators.

## Submission Message

```text
ZERO is an open-source autonomous operating system for self-custodial onchain
operations. We want Railway to be the one-click paper-runtime path for new
operators and contributors.

The template deploys ZERO Paper Runtime from github.com/zero-intel/zero. It
uses Dockerfile build, /health health checks, a /data volume for the append-only
paper journal, and live Hyperliquid public prices in read-only mode. It does
not require exchange private keys and live execution is refused by default.

Live demo: https://zero-production-5214.up.railway.app
Template docs: https://github.com/zero-intel/zero/blob/main/docs/railway-template.md
Evidence packet: https://github.com/zero-intel/zero/blob/main/contracts/distribution/railway-template.json
```
