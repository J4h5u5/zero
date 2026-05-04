# MCP Registry Submission Packet

ZERO has a public-safe MCP server and a committed MCP Registry manifest, but it
is not listed in the Official MCP Registry yet.

The blocker is intentional: the Official MCP Registry metadata points to a
public package or public remote server, and ZERO package registries remain
blocked until ownership, tokenless publishing, and rollback evidence are
recorded.

Machine-readable files:

- [server.json](../server.json)
- [contracts/distribution/mcp-registry.json](../contracts/distribution/mcp-registry.json)

Schemas:

- `zero.mcp_registry_packet.v1`
- `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`

Regenerate and verify:

```bash
scripts/mcp_registry_packet.py --output
scripts/mcp_registry_packet.py --check
PYTHONPATH="$PWD/engine/src" python3 -m zero_engine.mcp --smoke
PYTHONPATH="$PWD/engine/src" scripts/mcp_transcript.py --check
```

## Registry Identity

| Field | Value |
|---|---|
| Server name | `io.github.zero-intel/zero` |
| Title | `ZERO MCP` |
| Package | `zero-engine` |
| Transport | `stdio` |
| Auth path | GitHub OIDC from `zero-intel/zero` |
| Safety class | `read-only-public` |

The PyPI package README carries the MCP package proof string:

```html
<!-- mcp-name: io.github.zero-intel/zero -->
```

## Current Listing Evidence

As of `2026-05-04T05:08:00Z`, the Official MCP Registry query returns no ZERO
server:

```bash
curl -fsS 'https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.zero-intel/zero'
```

```json
{"servers":[],"metadata":{"count":0}}
```

That is the expected state until `zero-engine` is published on PyPI and the MCP
publisher run records a successful listing.

## Publish Runbook

Only run this after package-registry publication is deliberately enabled for a
release:

```bash
just registry-readiness
just package-dry-run
mcp-publisher login github-oidc
mcp-publisher publish
curl -fsS 'https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.zero-intel/zero'
```

Record the command output in the release evidence before calling the MCP
registry gap closed.

## Safety Boundary

The public MCP server remains read-only:

- no order placement;
- no live control;
- no wallet or secret access;
- no runtime mutation.

Every public tool reports `canPlaceOrders=false`,
`canChangeRuntimeState=false`, and `canReadSecrets=false`; the transcript and
smoke test are committed gates.
