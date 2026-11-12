# Coex unified chat preview

## What changed
All capabilities live in the main chat composer. Auto routes common current-information
and image prompts; explicit Chat, Study/PDF, Web search and Create image selectors
handle ambiguous requests. Auto routing uses conservative keyword rules, not a perfect
intent classifier. The old Study screen remains an archive/alternative view.

- Attach a PDF to start the bounded Study Agent in chat. See its plan, tool results,
  quote checks, semantic verification, revisions and export. Pause finishes the current
  step; reopening a task lets you continue. No background worker runs with the app closed.
- After a completed task, click Quiz me or type `quiz me`. Answer in the usual composer.
  The grader awards 0/1/2, returns feedback and builds a weak-topic revision plan.
  Repeated quizzes prioritise missed questions from the same source-backed bank.
  This does not generate an unlimited new question bank or calibrate exam difficulty.
- Follow-up Chat questions retrieve relevant chunks from the most recent document in
  that conversation. Study mode can reuse it for a new plan without re-uploading.
- Local PDF uploads: 100 MiB, up to 3,000 pages and 3,000,000 extracted characters,
  20,000 per page. Lexical ranking searches across all extracted chunks, including
  later book sections. Only retrieved evidence goes to the model, not the entire book
  in one prompt. Extraction limits are disclosed. Scans need OCR, which is not included.
- Explicit language/style requests are learned without feedback forms. Supported phrases
  include `Hindi mein samjhao`, `explain in English`, `short answer`, `explain in detail`,
  `exam ke liye`, and `remember: ...` / `yaad rakho: ...` for an explicit note.
  This deliberately does not store every query as a preference or infer sensitive traits.
  Current instructions take precedence; corrections stay user context, not verified facts.
- Memory & preferences shows, edits, deletes and disables memory. Clearing memory does not
  delete chat or quiz history. Memory-off stops preference learning/use and weak-topic
  writes; a quiz can still adapt using its explicitly requested task's saved quiz history.
- Optional thumbs up/down stores feedback; recent disliked responses are supplied as
  private feedback context for future ordinary chat while memory is enabled. Ratings do
  not train Gemini or prove whether a factual answer is correct. No cross-user learning.
- Web search uses Gemini Google Search grounding. Only the current query is sent to the
  search request: no prior chat, PDF or memory. Remove attachments before explicit Web
  mode. Responses require returned source metadata, show numbered source links, and
  display the provider's search suggestions in a sandboxed frame. Missing sources or
  provider failures produce errors, never a fabricated claim of successful search.
- Create image sends the current text prompt to an image-capable Gemini model. Images
  are validated, saved as JPEG, displayed/downloaded in chat and served only to their
  conversation owner. This release supports text-to-image, not image editing/video.

## Provider setup and cost
Use the existing Gemini key via the desktop launcher. No key is bundled. Server-only
optional overrides: GEMINI_SEARCH_MODEL (default gemini-3.5-flash) and
GEMINI_IMAGE_MODEL (default gemini-3.1-flash-lite-image). Availability and billing depend
on your provider account. Image generation may require paid access; no billing or paid
service was enabled for you. Web requests are capped at 10/user/day, image requests at
3/user/day, with site limits of 100 and 20 respectively. Existing chat and study quotas
also apply. Provider model/access failures are visible to the user.

## Upgrade on Windows
Close Coex first and back up the working folder. Replace project files from this complete
ZIP while preserving db.sqlite3 and local_config.json. Start Coex.vbs migrates the database
and collects static files automatically. Keep the launcher open/minimised. Python is the
backend and launcher; the browser interface necessarily still uses HTML/CSS/JavaScript.

Migration 0003 adds private preferences, feedback, quiz state, message metadata and links
between study tasks and conversations. Existing chats and study tasks remain intact;
older tasks can still be opened from the Study archive.

## Validation and remaining gates
50 Django tests pass with mocked provider calls, including original auth/chat/media
regressions, study verification, 100 MiB multipart upload, routing, citation extraction,
image bytes, ownership, memory-off, edits/deletion, CSRF, quiz grading and adaptive
revision, same-chat PDF reuse and retrieval of later source chunks. System/static/JS
checks pass. Simulated DOM interactions also pass for sources, image rendering, memory controls,
saved study tasks and quiz completion. This is not a visual browser or live-provider test. These tests are not evidence of successful live Gemini/search/image calls.
Real-provider account access, Windows UI and visual browser staging verification remain
release gates. There is no production promotion in this update.

## Honest limits for the bootcamp
This is a bounded, tool-using agent with private memory and task feedback, not an
AI model that trains itself from every user. Semantic grading/verification can be wrong.
Study plans have at most 12 actions and 8 notes/quiz items; a large textbook still needs
focused goals. Source references use chunk IDs, not printed page numbers. Vercel direct
uploads stay at 4 MiB; 100 MiB cloud uploads need a separate object-storage flow.
No OCR, shared knowledge ingestion, automatic cross-user learning, video generation,
background scheduling, password-reset email or Unicode PDF fonts are added here.
