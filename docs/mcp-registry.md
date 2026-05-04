# MCP Registry Submission Packet

ZERO has a public-safe MCP server, a committed MCP Registry manifest, and a
manual GitHub OIDC publication workflow. It is not listed in the Official MCP
Registry yet.

The blocker is intentional: the Official MCP Registry metadata points to a
public package or public remote server, and ZERO package registries remain
blocked until ownership, tokenless publishing, and rollback evidence are
recorded.

Machine-readable files:

- [server.json](../server.json)
- [contracts/distribution/mcp-registry.json](../contracts/distribution/mcp-registry.json)
- [.github/workflows/mcp-registry.yml](../.github/workflows/mcp-registry.yml)

Schemas:

- `zero.mcp_registry_packet.v1`
- `zero.mcp_registry_listing_check.v1`
- `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`

Regenerate and verify:

```bash
scripts/mcp_registry_packet.py --output
scripts/mcp_registry_packet.py --check
scripts/mcp_registry_listing_check.py --json
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
| Registry base URL | `https://pypi.org` |
| Runtime hint | `uvx` |
| Auth path | GitHub OIDC from `zero-intel/zero` |
| Safety class | `read-only-public` |

The PyPI package README carries the MCP package proof string:

```html
<!-- mcp-name: io.github.zero-intel/zero -->
```

## Current Listing Evidence

As of `2026-05-04T05:59:55Z`, the Official MCP Registry query returns no ZERO
server and PyPI returns no `zero-engine` package:

```bash
curl -fsS 'https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.zero-intel/zero'
curl -fsS 'https://pypi.org/pypi/zero-engine/json'
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
just mcp-registry-listing-check
mcp-publisher login github-oidc
mcp-publisher publish
curl -fsS 'https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.zero-intel/zero'
```

The preferred path is the manual
[`MCP Registry Publication`](../.github/workflows/mcp-registry.yml) workflow.
Run it first with `publish=false` to verify local MCP surfaces, server metadata,
and current listing state. After the `zero-engine` PyPI package is public and
its README description contains `mcp-name: io.github.zero-intel/zero`, rerun the
workflow with `publish=true` and confirmation text
`publish io.github.zero-intel/zero`. The workflow uses GitHub OIDC, installs
the official `mcp-publisher`, publishes `server.json`, and then requires
`scripts/mcp_registry_listing_check.py --expect-listed` to pass.

Record the workflow URL and listing JSON in the release evidence before calling
the MCP registry gap closed.

## Upstream Requirements

The Official MCP Registry hosts metadata, not artifacts; the referenced package
must already exist in a supported public registry. For PyPI packages, the
package README must include an `mcp-name: <server-name>` marker that matches
`server.json`. GitHub OIDC publication does not require a dedicated MCP secret,
but it does require `id-token: write` in the workflow.

Primary references:

- [MCP Registry quickstart](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx)
- [MCP Registry GitHub Actions guide](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/github-actions.mdx)
- [MCP Registry package types](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/package-types.mdx)

## Safety Boundary

The public MCP server remains read-only:

- no order placement;
- no live control;
- no wallet or secret access;
- no runtime mutation.

Every public tool reports `canPlaceOrders=false`,
`canChangeRuntimeState=false`, and `canReadSecrets=false`; the transcript and
smoke test are committed gates.
