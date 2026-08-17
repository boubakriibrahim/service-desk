# Validation status

Checks recorded on 2026-10-17 on macOS with Docker Desktop 28.5.1. Re-run them with the commands below.

## Automated checks

| Check | Command | Result |
|---|---|---|
| API unit tests | `make test` | 18 passed (integration tests skip without a test database) |
| API unit and integration tests | `make test-integration` | 32 passed |
| Web lint | `cd apps/web && npm run lint` | No errors |
| Web type check | `cd apps/web && npm run typecheck` | No errors |
| Web production build | `cd apps/web && npm run build` | Passed |
| Docker images | `docker compose build api web` | Built |
| Running stack | `make up`, then `GET /health/ready` | db, api and web healthy; API reports `ready` |

The integration tests run against a dedicated PostgreSQL database whose name must end in `_test`; they check both the URL and the database the API engine actually uses before resetting it. They cover sign-in, the sign-in options, unauthenticated access, scope isolation for the finance account, a full investigation with citation checks, the blocked request, the engineer's refused approval, approval and double approval, stale proposals, the demo reset permission, the health endpoints and response headers, and a user created with `python -m app.manage create-user` who lands in their own organization.

GitHub Actions runs the same API tests against a pgvector service container, the web lint, type check and build, and both Docker image builds.

## Production settings

Checked in the API container:

- `APP_ENV=production` with the placeholder `SECRET_KEY` stops startup with a clear error.
- An unknown `APP_ENV` such as `prod` stops startup instead of falling back to the development defaults.
- `APP_ENV=production` refuses `http://` web origins, and every environment refuses `WEB_ORIGIN=*`.
- These checks also run in the seed step, which runs before the API starts.
- `APP_ENV=production` with a strong secret and an HTTPS origin skips the demo seed, so no account with the public demo password is created.
- A URL-encoded password in `DATABASE_URL` reaches PostgreSQL intact during migrations.
- An upload directory the API user cannot write stops startup with the command that fixes it.
- `python -m app.manage create-user` rejects passwords shorter than 12 characters.

## Browser walkthrough

A Playwright run against the running stack with the sample models, signed in as each role:

- the engineer sees the Northstar Foods case, runs an investigation, gets a brief that needs approval, and opens a cited document;
- the engineer sees the four documents in their scopes and is told that only an approver can authorize the write;
- the manager approves the proposal and the work order is written.

A second run checked the sign-in page and the screens around it:

- with sample data, the sign-in page offers the sample accounts and pre-fills the engineer's;
- when the API reports no sample data, the page offers none and starts with empty fields, the walkthrough hints are hidden, a new case asks for a task instead of offering the sample scenarios, and the new-work form starts empty;
- the sidebar shows the signed-in organization;
- a missing work item shows an error and a way back;
- documents open, close, and reopen cleanly;
- only an approver sees the reset panel, and only while the reset is enabled.

Neither run reported browser console errors.

## With real models

The full pipeline also ran with Laya as the request guard (on CPU), the local `BAAI/bge-small-en-v1.5` embedding service, and an OpenAI-compatible chat endpoint writing the report:

- the investigation completed in about 28 seconds, with 6 retrieved passages and 6 citations that all matched them;
- the prompt-injection example was classified as a jailbreak with block probability 1.0 and stopped before retrieval, in under a second;
- the engineer's approval attempt returned 403, and the manager's approval wrote work order WO-1926.

## Known limits

- The investigation request is synchronous. With a slow model the HTTP request stays open until the brief is ready, while the page polls the run's events to show progress.
- Laya on an Apple GPU (MPS) stopped with a Metal assertion during this check. Running it on the CPU worked; see the troubleshooting table in [`apps/laya/README.md`](../apps/laya/README.md).
- Sign-in has no rate limiting of its own. Put the app behind a reverse proxy that limits requests (see [`SECURITY.md`](SECURITY.md)).
- The seeded company, documents and accounts are sample data for local demos.
