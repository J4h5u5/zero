# Registry Launch Packet

ZERO currently distributes the public runtime through GitHub Releases, the
public Homebrew tap, `zero-engine` on PyPI, and `zero-os` on crates.io. GHCR
has an authenticated, smoke-tested multi-platform paper image, but it is not yet
the primary public container install path until anonymous pull access is
verified. Docker Hub publication is wired for marketplace discoverability and
waits on namespace ownership plus repository secrets.

The machine-readable packets are:

- [contracts/distribution/registry-launch.json](../contracts/distribution/registry-launch.json)
- [contracts/distribution/mcp-registry.json](../contracts/distribution/mcp-registry.json)

Schema: `zero.registry_launch_packet.v1`

MCP Registry schema: `zero.mcp_registry_packet.v1`

Regenerate and verify it with:

```bash
scripts/registry_launch_packet.py --output contracts/distribution/registry-launch.json
scripts/registry_launch_packet.py --check
scripts/mcp_registry_packet.py --output
scripts/mcp_registry_packet.py --check
scripts/mcp_registry_listing_check.py --json
```

## Current Channel State

| Channel | State | Candidate |
|---|---:|---|
| GitHub Release | published | `zero-intel/zero` |
| Homebrew tap | ready | `zero-intel/zero` |
| PyPI | published | `zero-engine` |
| crates.io | published | `zero-os`, `zero-*` workspace crates |
| GHCR | published, public-pull pending | `ghcr.io/zero-intel/zero-paper` |
| Docker Hub | ready, credentials pending | `zerointel/zero-paper` |
| MCP Registry | listed | `io.github.zero-intel/zero` |

## Enablement Rule

A package registry can only move from `blocked` to `ready` or `published` when
the release PR records:

- maintainer-controlled namespace evidence;
- tokenless or least-privilege publishing configuration;
- clean install evidence from the target channel or a staged equivalent;
- rollback, yank, delete, or deprecation procedure for that channel;
- support expectation and safety wording for paper-first operation.

The release workflow must not grow automated `cargo publish` or default-on
container publication steps until this packet and the release notes include
that evidence. PyPI `zero-engine` publication is already handled through
Trusted Publishing. crates.io publication is performed manually with a
least-privilege `CRATESIO_API_TOKEN` until a tokenless workflow is available.

## GHCR

The paper runtime image is published through the manual
[`Container Publish`](../.github/workflows/container-publish.yml) workflow.
The workflow builds and smokes the local image, pushes a multi-platform image,
then pulls and smokes the published tag.

Current evidence:

- Image: `ghcr.io/zero-intel/zero-paper:0.1.2`
- Digest: `sha256:1a9c2f0d2388ad117157b86a70d7db1ff78653d1b9e29c9d936c55efe7666de6`
- Source commit: `dcff6345320c766717d5cd95cbbf215d0506e288`
- Workflow run: <https://github.com/zero-intel/zero/actions/runs/25360430397>
- Platforms: `linux/amd64`, `linux/arm64`
- Smoke evidence: local image and published image both run the paper runtime
  and `examples/paper-trading/run.py`.
- Limitation: the workflow `GITHUB_TOKEN` could push the package but could not
  administer package visibility through the GitHub REST API. Treat the image as
  published but public-pull pending until a maintainer verifies an anonymous
  `docker pull ghcr.io/zero-intel/zero-paper:0.1.2` from a clean machine.

Rollback uses digest promotion:

```bash
docker buildx imagetools create \
  -t ghcr.io/zero-intel/zero-paper:latest \
  ghcr.io/zero-intel/zero-paper@sha256:<known-good-digest>
```

If the package cannot be made public from repository package settings, use a
least-privilege maintainer token with package administration scope only for the
visibility change, then remove the token.

## Docker Hub

Docker Hub publication is wired into the manual
[`Container Publish`](../.github/workflows/container-publish.yml) workflow for
maximum marketplace discoverability. It is opt-in with `publish_dockerhub=true`
and requires these repository secrets:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

Default candidate image:

```bash
docker pull zerointel/zero-paper:0.1.2
```

If the maintained namespace is different, override the workflow input
`dockerhub_namespace`. Before first publication, record:

- namespace owner evidence;
- token scope and rotation policy;
- successful workflow run URL;
- image digest;
- anonymous `docker pull` evidence from a clean machine;
- rollback/deprecation command used for the tag.

## crates.io

The installable CLI package is `zero-os` because `zero` is already occupied on
crates.io. The binary target remains `zero`, so operators install and run:

```bash
cargo install zero-os
zero --version
```

Published 0.1.2 workspace crates:

1. `zero-config`
2. `zero-operator-state`
3. `zero-session`
4. `zero-testkit`
5. `zero-engine-client`
6. `zero-headless`
7. `zero-onboarding`
8. `zero-doctor`
9. `zero-commands`
10. `zero-tui`
11. `zero-os`

Owner evidence: `cargo owner --list zero-os` and `cargo owner --list
zero-config` both return `squaeragent`.

Rollback uses crates.io yanking, not deletion:

```bash
cargo yank --version 0.1.2 <crate-name>
```

Yanking prevents new dependency resolution to the bad version while preserving
already-built artifacts for auditability.
