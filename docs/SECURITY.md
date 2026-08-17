# Security rules

## Who can see what

Each case and document has an access rule. The API checks a person's role before returning it or searching it.

## Checking requests

Before searching or writing an answer, the app asks Laya to check the request. It looks for instructions that try to bypass rules or reveal private information. A request that fails this check is stopped.

## Choosing a model service

The app checks how private the information is before choosing a model service. It only sends information to a service allowed to handle it.

## Approving work

The writing model can suggest a work order. It cannot approve or save one. A manager must approve it, and the API checks the latest case details before saving it.

**The model suggests. The app checks. A person approves.**

## Production checklist

The defaults are tuned for a local demo. Before exposing Service Desk to real users and data:

1. Set `APP_ENV=production` and a unique `SECRET_KEY` of at least 32 characters, for example from `openssl rand -hex 32`. The API refuses to start without one. It also refuses any `APP_ENV` other than `development`, `test`, or `production`, so a typo cannot fall back to the development defaults.
2. Serve the web app and the API over HTTPS behind a reverse proxy, on the same site, for example `desk.example.com` and `api.desk.example.com`. The session cookie is `SameSite=Lax`, so browsers do not send it to an API on a different site. In production the cookie is also marked `Secure`.
3. Set `WEB_ORIGIN` to the exact public origin of the web app (a comma-separated list if there are several). In production the API accepts only `https://` origins, and it never accepts `*`. Build the web image with `NEXT_PUBLIC_API_URL` pointing at the public API address.
4. Set `POSTGRES_PASSWORD` and the matching `DATABASE_URL` before the first start. PostgreSQL reads `POSTGRES_PASSWORD` only when it creates the `service_desk_db` volume; to change the password of an existing database, run `ALTER USER service_desk PASSWORD '...'` inside it, then update both settings. URL-encode characters such as `@`, `:`, or `/` in `DATABASE_URL`. The database port is published on the loopback interface only; keep it that way and back up the volume.
5. Create real accounts with `docker compose run --rm api python -m app.manage create-user ...`. Production skips the demo seed (`SEED_DEMO_DATA`), so the sample accounts and their shared password are never created, and the sign-in page stops offering them. The demo reset endpoint stays disabled (`ENABLE_DEMO_RESET`).
6. Run the real request guard: set `LAYA_MODE=remote`, point `LAYA_BASE_URL` at the Laya service, and set `LAYA_REQUIRED=true` so that investigations stop when the guard is unavailable instead of continuing without screening. The default `demo` mode only recognizes a short list of fixed phrases, and `off` skips screening.
7. Set `AI_MAX_SENSITIVITY` for each model endpoint to the most sensitive data it is approved to receive, and keep API keys in the environment or a secret store, never in the repository.
8. Add rate limiting for `/api/auth/login` at the reverse proxy, or put the app behind your single sign-on.
9. Keep uploads on storage the API's non-root user (uid 10001) can write. The bundled `service_desk_uploads` volume already is. If you mount a host directory instead, give that uid write access; the API refuses to start until it can write there.
