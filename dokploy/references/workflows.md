# Operation workflows

Names below are upstream names at the reviewed revision. Use the adapter to search exact operation names and describe their schemas. Create or deploy resources only when the request calls for it.

## Applications

Resolve the project, environment, and existing application. For a new application, `application-create` requires `name` and `environmentId`; select the requested source type and server placement. Retain the returned `applicationId`.

Configure the source through `application-saveGithubProvider`, `application-saveGitlabProvider`, `application-saveBitbucketProvider`, `application-saveGiteaProvider`, `application-saveGitProvider`, or `application-saveDockerProvider`. Provider IDs come from the instance, not a repository URL. Docker inputs include `applicationId`, `dockerImage`, and nullable `username`, `password`, and `registryUrl`.

Use `application-saveBuildType` when needed. Snapshot build types include `dockerfile`, `heroku_buildpacks`, `paketo_buildpacks`, `nixpacks`, `static`, and `railpack`. This tool requires several nullable fields even for build types that do not use them; preserve intended configuration rather than filling every field with null.

`application-saveEnvironment` requires `applicationId`, `env`, `buildArgs`, `buildSecrets`, and `createEnvFile`. It is not a single-variable patch. Obtain authoritative complete values before replacing them, especially when reads are redacted.

Trigger `application-deploy` with `applicationId` and an optional descriptive title, or `application-redeploy` for a requested redeployment. Inspect `deployment-all` with the same application ID, correlate the new record, and use `deployment-readLogs` with its deployment ID as needed.

## Docker Compose

Inspect existing state with `compose-one`. For a new raw service, `compose-create` accepts `name`, `environmentId`, `sourceType: "raw"`, and `composeFile`, with optional server placement and `composeType` (`docker-compose` or `stack`). Retain `composeId`.

`compose-update` supports optional source, file, branch, provider, environment, and other settings. Send only intended changes. Do not replace a file or environment from a redacted read. `compose-loadServices` can identify service names for domain configuration.

Use `compose-deploy` or a requested `compose-redeploy`, then inspect `deployment-allByCompose` with `composeId`. Build logs use `deployment-readLogs`. Runtime logs use `compose-readLogs`, which requires both `composeId` and an actual `containerId`; a service name is not a container ID. Search available container inspection endpoints when needed.

## Domains

Inspect `domain-byApplicationId` or `domain-byComposeId` before adding mappings. `domain-create` accepts `host`, internal `port`, HTTPS/certificate options, and target IDs. Compose mappings need the intended `serviceName` and `domainType: "compose"`; application mappings use `applicationId` and the appropriate domain type.

Match the port to the service's listening port. Use `domain-validateDomain` according to its schema, then verify routing and TLS if accessible. Saving a mapping does not prove DNS propagation or certificate issuance.

## Databases and backups

Discover the actual engine's tools: `postgres`, `mysql`, `mariadb`, `mongo`, `redis`, or `libsql`. Resolve the environment and existing resource. Use engine-specific schemas for requested creation, configuration, and deployment; engine fields are not interchangeable.

Source passwords securely. Configure external ports only when requested. For backup/restore operations, inspect available `backup`, `destination`, and volume backup tools and resolve the engine, target, destination, and backup record before mutation. A failed database deployment does not imply a restore request.

## Failed deployments and rollback

Inspect `application-one` or `compose-one`, target deployment history, and bounded `deployment-readLogs` output (default tail: 100 lines). Use available queue/container tools when relevant. Diagnose source access, build configuration, missing secrets, startup, routing, or capacity from evidence.

Fix issues within the requested scope and verify a subsequent deployment when authorized. A failed build does not justify deleting resources, cancelling unrelated queue entries, pruning Docker, or changing shared Traefik settings.

`rollback-rollback` requires a `rollbackId`, not a deployment ID. Resolve a valid rollback record and verify its target before an authorized rollback. If the API does not expose that prerequisite, report it rather than inventing an ID.
