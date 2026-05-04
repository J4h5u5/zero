# Registry Launch Packet

ZERO currently distributes the public runtime through GitHub Releases, the
public Homebrew tap, `zero-engine` on PyPI, and `zero-os` on crates.io. Docker
Hub and GHCR publication remain blocked until ownership, provenance, and
rollback evidence are recorded.

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
| Container registry | blocked | `zero-intel/zero-paper` |
| MCP Registry | listed | `io.github.zero-intel/zero` |

## Enablement Rule

A package registry can only move from `blocked` to `ready` or `published` when
the release PR records:

- maintainer-controlled namespace evidence;
- tokenless or least-privilege publishing configuration;
- clean install evidence from the target channel or a staged equivalent;
- rollback, yank, delete, or deprecation procedure for that channel;
- support expectation and safety wording for paper-first operation.

The release workflow must not grow automated `cargo publish`, `docker push`, or
GHCR/Docker login steps until this packet and the release notes include that
evidence. PyPI `zero-engine` publication is already handled through Trusted
Publishing. crates.io publication is performed manually with a least-privilege
`CRATESIO_API_TOKEN` until a tokenless workflow is available.

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
