# Coex Study Agent — bootcamp prototype

A Python/Django agent that turns an uploaded PDF and learning goal into a study pack.
Open **Study Agent** from chat, upload a text PDF, enter your goal and start.
The model decides which allowlisted tool to call next: plan, read, search, draft,
verify, export or clarify. Tool observations feed the next decision. Failed checks
can trigger a revised draft; missing evidence can trigger a clarification.
This is a bounded model-directed loop, not a fixed prompt chain.

## Tools and evidence
- PDF extraction: existing pypdf path, maximum 100 MiB in the local desktop app, 3,000 pages, 3,000,000 extracted
  characters total and 20,000 per page. Partial extraction is disclosed in the activity log and model state. Scans require a readable replacement; there is no OCR.
- Read/search: stable 2,400-character source chunks. Citations are **chunk IDs**,
  not page numbers. Search is literal keyword matching, not web research.
- Draft: schedule, revision notes, short-answer questions and answers.
- Verify: exact quote matching plus a separate Gemini semantic/goal review.
  Model review can be wrong; it is not proof of truth or full source coverage.
- Export: PDF after successful verification; UTF-8 text fallback for scripts the
  existing PDF exporter cannot represent. No arbitrary file writes or shell tools.
- Activity log: public action summaries, tool inputs/results and verification feedback;
  no private reasoning requested. Each run belongs to its authenticated user.

## Limits and runtime
12 actions per run; up to two model calls per step; 5 runs per user/day;
60 steps per user/day and 250 steps site-wide/day (up to 120 / 500 model calls).
Each step is a separate POST with a 120-second lease, so duplicate requests cannot
normally execute the same step concurrently. Provider requests time out at 45 seconds.
The browser drives subsequent steps; closing it pauses execution after the in-flight
step. Reopen a saved run and Continue. Pause does not cancel an in-flight provider call.
No durable worker or automatic resume while the app is closed.
If a run needs input, update the goal/PDF and start a new run.
If the host kills a request, its lease expires and a retry may repeat a provider call.

Uploaded extracted text, outputs and activity are stored in the account database.
Relevant source evidence is sent to Gemini. Never upload confidential material without
permission. The original PDF binary is not saved by Study Agent.

## Run locally
Windows: regular Python 3.14 with Tcl/Tk. Double-click `Start Coex.vbs`, use your
Gemini key, then open Study Agent from chat. The launcher migrates the database.
For existing accounts/history, back up your old folder and copy only `db.sqlite3`
and `local_config.json` into the new Coex folder while both copies are stopped.
Do not distribute those two personal files. No API key is bundled in this package.

CLI: install requirements, set COEX_ENV=development and
GOOGLE_GENERATIVE_AI_API_KEY, run `python manage.py migrate`, then
`python manage.py runserver`. Production also requires the existing PostgreSQL,
Django secret and domain settings. Apply migration 0002 before enabling this screen.

## Verification recorded for this version
50 Django tests pass across chat, study, uploads and unified-chat capabilities. See UNIFIED_CHAT.md.
A synthetic valid PDF padded to exactly 100 MiB was accepted through the real multipart
endpoint, stored in a temporary disk file and parsed. This verifies size handling,
not performance for every complex 100 MB PDF.
Provider calls are mocked. Tests cover complete workflow, rejected quotations,
failed review followed by revision, missing source, clarification, unknown tools,
step budget, ownership, CSRF, concurrent-step lease, provider error handling,
PDF upload, keyword search and invalidation of previous verification.
Large-file browser upload, live Gemini behavior and the Windows GUI have not been re-verified for this version.
The existing launcher is carried over from the version the user reported working.

## Bootcamp demo script
1. Upload short course notes and request a one-day study pack.
2. Show the agent's plan, source reads, draft, verification and PDF export.
3. Run a goal about a topic absent from the notes; show clarification or failed review.
4. Upload a scan; show the request for a text-based source.
5. Show saved run isolation and explain budget/verification limits.
Use a real Gemini run for the submission recording; do not present mocked tests as a
live autonomous demo. A successful real-provider run and demo recording remain gates
before claiming submission readiness. Main chat now includes quiz grading and web search; see UNIFIED_CHAT.md. Multiple simultaneous PDFs and OCR are not implemented. Acceptance is decided by bootcamp evaluators.

## Large PDF upload update
Study Agent now sends binary multipart uploads with a percentage indicator, avoiding
base64 expansion. Files over 1 MiB spool to temporary disk and are closed/removed
when the request ends. A streaming handler enforces the 100 MiB aggregate file limit.
The normal chat attachment path remains 2 MB. JSON compatibility requests remain small.
The UI says MB; the exact local limit is 104,857,600 bytes (100 MiB).
On Vercel this direct-upload path is capped at 4 MiB; 100 MB online uploads need a
separate object-storage upload flow. No new storage service or deployment is enabled.
Self-hosted reverse proxies must also permit the intended request size.
The 3,000,000-character analysis cap is separate from file size; split long documents
into relevant sections for full coverage. OCR remains unavailable.
