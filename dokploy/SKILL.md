---
name: dokploy
description: Deploy, inspect, configure, and troubleshoot applications, Docker Compose services, domains, and databases on Dokploy through its official MCP server. Use for Dokploy operations and MCP connection setup.
---

# Dokploy

Operate the user's Dokploy instance with the official `@dokploy/mcp` server. Discover exposed tools and read their current input schemas before calling them; installed versions and filters affect availability.

## Connect and resolve the target

Use an existing Dokploy MCP connection. For setup or missing tools, read [references/connection.md](references/connection.md). If no connection is available, report that prerequisite without claiming execution.

Upstream names use `category-operation`, such as `project-all`; clients may add namespaces or normalize names. Select the actual exposed tool. Generated annotations are hints, not proof that a mutation is harmless or safe to repeat.

Resolve projects with `project-all` or `project-one`, then environments with `environment-byProjectId` or `environment-one`. Applications and Compose resources require an `environmentId`; a project ID is not a substitute. Inspect the existing resource with its `one` tool and preserve its ID and server placement. Ask which target the user means when names are ambiguous. Reuse existing resources for requests about them rather than creating duplicates.

## Execute the requested operation

Read [references/workflows.md](references/workflows.md) for the relevant deployment, domain, database, or diagnostic workflow. Live schemas take precedence over examples. Inspect existing configuration, send only intended changes where partial updates are supported, and save configuration before a requested deployment.

Required nullable fields are not permission to clear existing values. Obtain intended values from an authoritative source. The server redacts environment variables, Compose files, passwords, tokens, and other sensitive fields by default. Treat redacted values as unknown: never write redaction markers back or replace a complete environment block from a redacted response. If required values are unavailable, obtain a secure source or let the user apply that part in Dokploy. Keep secret values out of reports and repository files.

Carry out changes within the user's requested scope. Stop, delete, restore, rollback, expose a database port, or change shared server settings only when the request covers that action and the target is clear. Diagnosis alone does not authorize these changes.

## Verify and report

Parse JSON text in the MCP result: success returns `success`, `message`, and optional `data`; failure sets `isError` and returns `success: false`, `error`, and optional `details`.

A successful deploy call confirms API request acceptance. Inspect deployment history, correlate the new record by ID, time, or title, and check status. Read bounded logs on failure. Verify service/container state and the requested URL when accessible. After a bounded observation period, report a still-running deployment as pending with its ID. Distinguish build completion from verified application health.

After a timeout or lost mutation response, inspect resource state and deployment history before retrying. Stop when the outcome cannot be determined instead of repeatedly creating resources or triggering builds. Correct authentication, permission, or validation errors before retrying.

Report the target, changes made, deployment ID and observed status, verification performed, and remaining issues.

## Source

Based on [Dokploy's official MCP implementation](https://github.com/Dokploy/mcp). Reviewed revision and source links are in [references/connection.md](references/connection.md).
