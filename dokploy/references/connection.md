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

## Stdio setup

Requires Node.js 18 or newer, a running Dokploy instance, and an API key with the needed resource permissions. Adapt the enclosing configuration format to the MCP client; populate credentials locally through its secret configuration mechanism.

```json
{
  "mcpServers": {
    "dokploy-mcp": {
      "command": "npx",
      "args": ["-y", "@dokploy/mcp"],
      "env": {
        "DOKPLOY_URL": "https://dokploy.example.com",
        "DOKPLOY_API_KEY": "<configured-locally>",
        "DOKPLOY_TOOL_PRESET": "deploy"
      }
    }
  }
}
```

Supply the instance base URL without `/api`; the API client appends that prefix and authenticates with `x-api-key`. Existing connections need not be changed simply to use the skill.

## Filtering

| Preset | Included tags |
| --- | --- |
| `all` | All categories; default |
| `minimal` | `project,application` |
| `core` | `project,server,application` |
| `deploy` | `project,environment,server,application,compose,domain,deployment` |
| `databases` | `postgres,redis,mysql,mariadb,mongo,libsql` |
| `git` | `github,gitlab,bitbucket,gitea,gitProvider,registry,sshKey` |

A nonempty `DOKPLOY_ENABLED_TAGS` list overrides the preset; `DOKPLOY_DISABLED_TAGS` is applied last. Database operations that also need discovery can use `project,environment,postgres,deployment,backup`. Add categories such as `docker` or `rollback` when needed. Reload the connection after requested configuration changes.

## Secrets and transport

- `DOKPLOY_REDACT_ENV` defaults to `true`; keep it enabled for ordinary operations. Redaction covers Compose files and other secret-bearing fields too.
- A nonempty `DOKPLOY_REDACT_FIELDS` replaces the default list; avoid inadvertently removing secret protection.
- `DOKPLOY_CUSTOM_HEADERS` is a JSON object of string names and values for proxy headers, such as Cloudflare Access service tokens. It cannot override `x-api-key`, `content-type`, or `accept`. Keep token values secret.
- Stdio is default. `--http` or `MCP_TRANSPORT=http` enables `/mcp`, `/health`, and legacy `/sse` and `/messages`. Do not publish a listener as a side effect of troubleshooting.
- `DOKPLOY_TIMEOUT` defaults to 30,000 ms. The snapshot parses `DOKPLOY_RETRY_ATTEMPTS` and `DOKPLOY_RETRY_DELAY`, but its API client has no retry loop. Do not assume automatic recovery.

## Troubleshooting

| Symptom | Next action |
| --- | --- |
| Missing tools | Inspect current filters and reload after a requested change. |
| Tool listing overload | Select a suitable preset or explicit tags. |
| 401 | Check configured API key and URL locally without printing credentials. |
| 403 | Check resource permissions; do not bypass them. |
| 404 | Re-resolve IDs and check instance/API compatibility. |
| Validation error or 422 | Inspect current required fields and enum values. |
| Timeout after mutation | Inspect state and deployment history before retrying. |
