# Registry Launch Packet

ZERO currently distributes the public runtime through GitHub Releases and the
public Homebrew tap. PyPI, crates.io, Docker Hub, and GHCR publication remain
blocked until ownership, tokenless publishing, and rollback evidence are
recorded.

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
| PyPI | blocked | `zero-engine` |
| crates.io | blocked | `zero`, `zero-*` workspace crates |
| Container registry | blocked | `zero-intel/zero-paper` |
| MCP Registry | workflow ready after PyPI publication | `io.github.zero-intel/zero` |

## Enablement Rule

A package registry can only move from `blocked` to `ready` when the release PR
records:

- maintainer-controlled namespace evidence;
- tokenless or least-privilege publishing configuration;
- clean install evidence from the target channel or a staged equivalent;
- rollback, yank, delete, or deprecation procedure for that channel;
- support expectation and safety wording for paper-first operation.

The release workflow must not grow `pypa/gh-action-pypi-publish`,
`cargo publish`, `docker push`, or GHCR/Docker login steps until this packet and
the release notes include that evidence.
