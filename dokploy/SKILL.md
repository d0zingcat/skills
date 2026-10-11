---
name: dokploy
description: Deploy, inspect, configure, and troubleshoot applications, Docker Compose services, domains, and databases on Dokploy directly through its API without loading hundreds of MCP tools. Use for Dokploy operations and deployment diagnostics.
---

# Dokploy

Operate the user's Dokploy instance through the bundled Python 3 API adapter, derived from the official MCP implementation. No MCP installation is required. Requires `DOKPLOY_URL` and `DOKPLOY_API_KEY` in the process environment. Read [references/connection.md](references/connection.md) for setup and compatibility details.

## Discover and call endpoints

Run commands relative to this skill's directory (or use absolute script paths):

```bash
python3 scripts/dokploy.py search deploy --tag application
python3 scripts/dokploy.py describe application-deploy
python3 scripts/dokploy.py call application-deploy --input /path/to/request.json
```

`call` also accepts JSON from stdin by default. Keep secrets in securely supplied input, never command arguments. Search returns at most 20 matches by default; narrow the query or tag when more exist. Describe only the selected endpoint before constructing input. The catalog contains all 604 upstream generated operations at the reviewed revision. Do not read the full `assets/endpoints.json` into context. The adapter checks top-level required fields; the server validates nested types, enums, and other constraints. Do not assume local schema validation is complete.

## Connect and resolve the target

Endpoint names retain upstream `category-operation` identifiers, such as `project-all`. Use `search` and `describe` to select exact names instead of guessing. The instance's API may differ from the bundled snapshot; investigate a version mismatch rather than retrying an incompatible request.

Resolve projects with `project-all` or `project-one`, then environments with `environment-byProjectId` or `environment-one`. Applications and Compose resources require an `environmentId`; a project ID is not a substitute. Inspect the existing resource with its `one` tool and preserve its ID and server placement. Ask which target the user means when names are ambiguous. Reuse existing resources for requests about them rather than creating duplicates.

## Execute the requested operation

Read [references/workflows.md](references/workflows.md) for the relevant deployment, domain, database, or diagnostic workflow. Endpoint descriptions take precedence over workflow examples; confirm instance compatibility when they differ. Inspect existing configuration, send only intended changes where partial updates are supported, and save configuration before a requested deployment.

Required nullable fields are not permission to clear existing values. Obtain intended values from an authoritative source. The adapter redacts environment variables, Compose files, passwords, tokens, and other sensitive fields by default. Treat redacted values as unknown: never write redaction markers back or replace a complete environment block from a redacted response. If required values are unavailable, obtain a secure source or let the user apply that part in Dokploy. Keep secret values out of reports and repository files.

Carry out changes within the user's requested scope. Stop, delete, restore, rollback, expose a database port, or change shared server settings only when the request covers that action and the target is clear. Diagnosis alone does not authorize these changes.

## Verify and report

The adapter emits JSON with `success` and `data` on successful HTTP requests. Failures return `success: false`, an error, and HTTP status when available, and exit nonzero. HTTP error bodies are withheld to avoid leaking secrets. Inspect returned application data for operation-specific failures too.

A successful deploy call confirms API request acceptance. Inspect deployment history, correlate the new record by ID, time, or title, and check status. Read bounded logs on failure. Field redaction does not sanitize arbitrary log strings; avoid publishing secret-bearing log excerpts. Verify service/container state and the requested URL when accessible. After a bounded observation period, report a still-running deployment as pending with its ID. Distinguish build completion from verified application health.

After a timeout or lost mutation response, inspect resource state and deployment history before retrying. Stop when the outcome cannot be determined instead of repeatedly creating resources or triggering builds. Correct authentication, permission, or validation errors before retrying.

Report the target, changes made, deployment ID and observed status, verification performed, and remaining issues.

## Source

Based on [Dokploy's official MCP implementation](https://github.com/Dokploy/mcp). Reviewed revision and source links are in [references/connection.md](references/connection.md).
