# coex — Python migration

A Django/Python backend with a plain HTML, CSS and JavaScript browser interface. No TypeScript, Node build, Next.js or eve runtime is required by this branch.

## Included

- Native username/password registration and sign-in using Django authentication, password validation, database sessions, CSRF protection and logout.
- Gemini streaming chat using the existing `gemini-3.5-flash-lite` model via the official Python SDK. API keys stay on the server.
- Per-account conversation history, title search, copy, edit/resend, stop and PDF response export.
- PDF/PNG/JPEG/WebP validation and attachment delivery to the model. Uploaded files are stored with their chat in the database.
- Owner checks on conversation reads and writes. Database-backed per-user and site-wide chat quotas, login throttling and file-request limits.
- No project-management MCP tools or access to the owner's Vercel/browser connections.

## Local run

Requires Python 3.12 or newer.

```sh
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
pip install -r requirements.lock
# Set COEX_ENV=development and GOOGLE_GENERATIVE_AI_API_KEY in your shell.
# Example Linux/macOS: export COEX_ENV=development
# Example PowerShell: $env:COEX_ENV='development'
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000 and create a coex account. `.env.example` documents configuration; the app does not automatically read `.env` files. Never put keys in source control.

## Production

Set a random `DJANGO_SECRET_KEY`, persistent PostgreSQL `DATABASE_URL`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `GOOGLE_GENERATIVE_AI_API_KEY`. Keep `COEX_ENV=production`. Configure HTTPS at your host. Set `TRUST_PROXY_HTTPS=1` only behind a trusted proxy that strips and replaces `X-Forwarded-Proto`.

Run `python manage.py migrate`, `python manage.py collectstatic --noinput`, and `python manage.py check --deploy` before serving with Gunicorn (see Procfile). Database tables must be migrated once during release, never created on every request. SQLite is restricted to local development; it must not be used as persistent storage on Vercel Functions.

This migration is on a separate branch. The existing production deployment remains on the TypeScript main branch until a persistent database is provisioned and the Python release passes live authentication and model tests. Do not merge into the existing Next.js deployment without changing its framework/build configuration.

## Tests and limits

Run `COEX_ENV=development python manage.py test`. Model calls in the tests are mocked; this proves application flows and ownership checks, not availability of your live API quota/model.

- Existing eve conversations are not imported automatically. The original deployment/history remains available separately.
- Edit/resend appends a new message; it does not rewrite the previous conversation.
- Attachments: 2 MB; PDFs: 40 pages; images: 12 MP. Up to 100 messages per conversation. Provider context is bounded to the latest 20 messages / approximately 4 MB.
- PDF export currently supports Latin script; other scripts return an explicit error. Image/video generation remains unimplemented.
- Browser responses use plain text; rich Markdown, tool execution and background agent workflows are not ported.
- Accounts use usernames; email verification and self-service password reset are not configured. An operator can reset passwords via Django's management command.
- Default usage limits are 50 messages/user/day and 500/site/day. These limit request counts, not exact currency spend. Configure provider-side budget limits before opening a public hosted service.
- For public deployment add proxy-level body/concurrency limits and run untrusted PDF processing with memory/time limits. Delete expired quota rows periodically (`Quota.objects.filter(expires_at__lt=timezone.now()).delete()`) and configure database backups/retention.

## Verification for this migration

13 Django integration tests passed using an isolated test database and mocked model output. `manage.py check`, static asset collection and JavaScript syntax validation passed. Real provider streaming, PostgreSQL deployment concurrency and the browser UI still need staging verification before production cutover.

## Vercel migration configuration

`vercel.json` selects Django on this branch even while the project dashboard still defaults to Next.js for `main`. It clears inherited install/output overrides. `pyproject.toml` points to `coex.wsgi:application`, and Python is pinned to 3.12. Requirements resolve through the tested lock file.

Before redeploying this branch, configure **Preview** variables `DJANGO_SECRET_KEY`, `DATABASE_URL`, and `GOOGLE_GENERATIVE_AI_API_KEY`. Vercel deployment/branch/production hostname variables are added as exact allowed hosts and trusted CSRF origins; custom domains need explicit entries. No wildcard host trust is enabled. Production still refuses to start with missing secrets or ephemeral SQLite storage.

For the first preview release, use a separate PostgreSQL database and set `COEX_RUN_MIGRATIONS=1` to apply committed migrations during the build. Remove this flag after provisioning if migrations are run separately by your release pipeline. `build.py` runs deployment checks; Vercel runs static collection automatically.

Historical failed deployments remain immutable records. The `NEXT_NO_VERSION` failure on the Python branch is corrected by the branch-specific Django framework selection; old lockfile errors were superseded by successful main deployments. A new deployment can only become usable after its database and secrets are provisioned.
