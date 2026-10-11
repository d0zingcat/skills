# Connection and implementation notes

## Source snapshot

Reviewed commit: `26799a777e444a7cad6bb7ecf0d5969fb859fa58`, package version `0.30.7`. This snapshot is not a required installed version.

- [Server and tool filtering](https://github.com/Dokploy/mcp/blob/26799a777e444a7cad6bb7ecf0d5969fb859fa58/src/server.ts)
- [Generated schemas](https://github.com/Dokploy/mcp/blob/26799a777e444a7cad6bb7ecf0d5969fb859fa58/src/generated/tools.ts)
- [Environment configuration](https://github.com/Dokploy/mcp/blob/26799a777e444a7cad6bb7ecf0d5969fb859fa58/src/utils/clientConfig.ts)
- [Request handler](https://github.com/Dokploy/mcp/blob/26799a777e444a7cad6bb7ecf0d5969fb859fa58/src/handler.ts)
- [API client](https://github.com/Dokploy/mcp/blob/26799a777e444a7cad6bb7ecf0d5969fb859fa58/src/utils/apiClient.ts)
- [Response formatter](https://github.com/Dokploy/mcp/blob/26799a777e444a7cad6bb7ecf0d5969fb859fa58/src/utils/responseFormatter.ts)
- [Official setup guide](https://github.com/Dokploy/mcp/blob/26799a777e444a7cad6bb7ecf0d5969fb859fa58/README.md)

## Direct API setup

Requires Python 3.9 or newer and a running Dokploy instance. No third-party Python packages or MCP server are required. Supply `DOKPLOY_URL` and `DOKPLOY_API_KEY` through the process environment using local secret configuration. Use the instance base URL without `/api`; the adapter adds that prefix and sends the key as `x-api-key`.

Optional settings:

- `DOKPLOY_TIMEOUT`: milliseconds, default 30,000.
- `DOKPLOY_CUSTOM_HEADERS`: JSON object of string proxy headers, for example Cloudflare Access service tokens. Cannot override `x-api-key`, `content-type`, or `accept`.

The adapter never retries automatically and refuses HTTP redirects to prevent forwarding credentials. GET inputs become scalar query parameters; POST inputs become JSON bodies. Structured GET inputs are rejected rather than silently encoded incorrectly. Responses are recursively redacted using the upstream default field suffixes. Raw-secret output is deliberately not provided. Arbitrary text/log strings can still contain secrets; keep them private.

## Catalog maintenance

The catalog covers all 604 operations in the reviewed generated tool source. It stores methods, paths, tags, descriptions, input schemas, and schema components locally. Search and describe read this file in the process without loading it into the agent's context.

To update from a reviewed checkout of the official repository:

```bash
python3 scripts/generate_catalog.py /path/to/Dokploy-mcp
```

The generator verifies that OpenAPI operations match generated tools and records the checkout commit and package version. Review endpoint changes and update the source snapshot above when refreshing. The catalog is derived from Apache-2.0 upstream material; attribution and license are in `assets/UPSTREAM-LICENSE`.

## Troubleshooting

| Symptom | Next action |
| --- | --- |
| Missing endpoint | Search the local catalog; check upstream and instance versions. |
| 401 | Check configured API key and URL locally without printing credentials. |
| 403 | Check resource permissions; do not bypass them. |
| 404 | Re-resolve IDs and check instance/API compatibility. |
| Validation error or 422 | Inspect current required fields and enum values. |
| Timeout after mutation | Inspect state and deployment history before retrying. |
