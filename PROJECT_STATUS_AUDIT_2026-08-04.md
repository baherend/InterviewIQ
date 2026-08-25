# InterviewIQ — Project Status Audit
**Date:** 2026-08-04 | **Repository:** `D:\InterviewIQ-final` | **Branch:** `main` | **Method:** Read-only static audit (12 parallel research passes + direct verification), evidence-based, no application code/DB modified.

---

## 1. Executive Summary

InterviewIQ has **two structurally disconnected products living in one repository**:

1. **The "normal" candidate product** (Login → Dashboard → `/interview/type` → `/interview/track` → `/interview/room` → `/interview/processing` → `/report/:id` → `/history`). This path is fully wired end-to-end — real auth, real DB persistence, real question bank, real history — but **every AI score it produces is fabricated**. `backend/app/ai_modules/{vision,audio,nlp}_module.py` are `random.uniform`/`random.gauss` generators; the transcript shown to the candidate is chosen with `random.choice` from five hard-coded sentences unrelated to what they said. Fusion here is `backend/app/ai_modules/fusion_engine.py` (`0.35·vision + 0.30·audio + 0.35·nlp`) applied to that fake data.

2. **The real AI pipeline** (`InterviewIQ_AI/fusion/`, `InterviewIQ_AI/vision/`, `InterviewIQ_AI/audio/`, `InterviewIQ_AI/nlp/`), which does genuinely invoke a trained Wav2Vec2-XLSR audio-emotion model (BAVED), a LoRA-adapted Swin-T/TCN vision model (RAVDESS), and a Whisper→claim-decomposition→BGE-M3→mDeBERTa-NLI text pipeline, fused with a real, distinct 0.60/0.40 (vocal/visual) "Delivery Confidence" formula. This pipeline is reachable **only** through the standalone, **unauthenticated**, **un-navigated**, single-question `/fusion-test` page, and it **never writes to the database** — its results exist only as a JSON file on disk and an HTTP response.

These two systems share no code, no data model, and are never reconciled. A candidate going through the real product literally cannot get a real AI score; the real AI pipeline literally cannot produce a persisted, multi-question, history-visible report. The last verified structural milestone (Phase 2C organization membership) is implementation-complete but has **zero automated test coverage**. Total first-party test suite: 6 files, ~31 tests, all currently passing, with no coverage at all of auth, organizations, questions, interviews, sessions, or history.

**Net assessment: Demo-only for the AI product; Partially Complete for the account/org/admin product.**

---

## 2. Repository and Runtime Map

| Layer | Finding | Status |
|---|---|---|
| Backend framework | FastAPI, entry `backend/app/main.py:36-41` (`app = FastAPI(title="InterviewIQ API", version="1.0.0", lifespan=lifespan)`) | Verified |
| API prefix | `/api`, routers mounted `backend/app/main.py:51-58` (`auth`, `questions`, `interviews`, `dashboard`, `organizations`, `admin_users`, `invitations`) | Verified |
| Frontend framework | React 18 + Vite 5 + React Router 6, entry `frontend/src/main.jsx:6-10` | Verified |
| Database / ORM | PostgreSQL 16 via SQLAlchemy 2.0 (`backend/app/database.py`); SQLite fallback code exists but is not the documented path | Verified/Partial |
| Migrations | Alembic, 5 linear migrations in `backend/alembic/versions/`; app never auto-creates tables, fails fast if `questions` table missing (`main.py:24-30`) | Verified |
| Auth | JWT (`python-jose`, HS256, 7-day expiry, no refresh token, no revocation list — suspension via `is_active` only), `backend/app/auth/jwt_handler.py` | Verified |
| Authorization | Explicit dependency functions in `backend/app/auth/permissions.py`: `require_global_roles`, `require_organization_access`, `require_organization_roles`, `require_membership_manager` | Verified |
| Frontend routing | `frontend/src/App.jsx`, role-gated via `RoleRoute`/`ProtectedRoute`/`PublicOnlyRoute` (`frontend/src/routes/guards.jsx`, explicitly UX-only, not a security boundary) | Verified |
| AI module locations | `InterviewIQ_AI/audio/`, `InterviewIQ_AI/vision/`, `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/`, `InterviewIQ_AI/fusion/` (orchestrator) | Verified |
| Backend-side "AI" stand-in | `backend/app/ai_modules/{vision,audio,nlp,fusion_engine}.py` — **100% `random`-based mocks**, docstrings say "Production replacement: ..." | Verified — Mocked |
| Fusion (real) | `InterviewIQ_AI/fusion/fusion_pipeline.py`, `confidence_fusion.py`, `confidence_config.py` | Verified — Real, but isolated |
| Local model paths | Vision checkpoint `InterviewIQ_AI/vision/vsc_ravdess_test73_deployment (1)/vsc_ravdess_lora_r16_test73_24.pt`; audio checkpoint `InterviewIQ_AI/audio/audio_emotion_package/audio_model.pt`; NLP reference `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/data/refdocs/reference_docs_250_FINAL_v1.json` | Verified (paths only, binaries not opened) |
| Ports | Backend 8000 (native `.bat`) / `${BACKEND_PORT:-8000}` (Docker); Frontend 5173 (native Vite) / `${FRONTEND_PORT:-3000}` (Docker); Nginx 80/443; Postgres 5432 internal-only | Verified |

### `start_local_demo.bat` trace
- `start_local_demo.bat` (5 lines) opens two `cmd /k` windows: one runs `start_backend.bat`, one runs `start_frontend.bat`. No Docker, no inline logic of its own.
- `start_backend.bat`: `cd backend`; requires **root-level** `backend.venv\Scripts\python.exe` to exist (errors if not — does not install); **runs `alembic upgrade head` automatically**; then `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- `start_frontend.bat`: `cd frontend`; requires `node_modules/` to exist (does not auto-install); runs `npm run dev -- --host 127.0.0.1` (Vite, port 5173).
- AI services (vision/audio/nlp/fusion) are **not** started as separate processes by any script — they only run when the backend spawns `InterviewIQ_AI/fusion/fusion_pipeline.py` as a subprocess, on-demand, triggered by an HTTP call to `/api/interviews/analyze`.
- Docker is a **completely separate path**, not required for and not used by `start_local_demo.bat`. Only Docker is documented in `README_LOCAL_SETUP.md`; the native `.bat` scripts (and the `backend.venv` vs `backend/.venv` split — two separate venv folders exist) are undocumented anywhere.
- Native `.bat` path: migrations **are** auto-applied (`alembic upgrade head` in `start_backend.bat`). Docker path: migrations are **not** auto-applied — `backend/Dockerfile` CMD is bare `uvicorn`, and `README_LOCAL_SETUP.md` instructs a manual `docker compose exec backend ... alembic upgrade head`.
- The database server itself must already exist/be reachable in both paths — neither script provisions a Postgres instance for the native path.

### README claims vs. code (selected contradictions)
| README claim | Verdict |
|---|---|
| "No real Vision, Audio, or NLP model integration... mock implementations" (`README_LOCAL_SETUP.md:779-781`) | **Contradictory/stale** — a real integration exists (`InterviewIQ_AI/fusion/`), just not wired into the primary student flow. |
| "Frontend role-based dashboards and route guards are still not implemented" (line ~173) | **Contradictory** — directly refuted by the same document's later sections and by working code (`guards.jsx`, `roles.js`). |
| `/fusion-test` and `/api/interviews/analyze` | **Undocumented** — not mentioned anywhere in the README, including the fact that it's unauthenticated. |
| `start_local_demo.bat` / native venv path | **Undocumented** — README only covers Docker. |

---

## 3. Git State

```
Branch: main
```
Modified (unstaged): `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/{configs/calibration.yaml, configs/decomposition.yaml, data/glossary/transliteration_glossary.json, src/interview_iq/decomposition/types.py, src/interview_iq/decomposition_llm/system_prompt.md, src/interview_iq/decomposition_llm/transliteration.py, src/interview_iq/nli/engine.py, src/interview_iq/pipeline.py}`, `backend/interviewiq_test.db`, `frontend/src/pages/FusionTest.jsx`

Untracked: `InterviewIQ_AI/nlp.zip` (525MB backup snapshot, older than current tree), `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/configs_backup_20260803/`, `.../data/glossary/transliteration_glossary_backup_20260803.json`, `.../src/interview_iq/cli/`, `.../src/interview_iq/decomposition/inference.py` (stub, `NotImplementedError`), `.../src/interview_iq/fusion/` (empty `__init__.py`, dead), `.../src/interview_iq/nli/{finetune.py,probe.py,probe_verdict.py}`, `.../src/interview_iq/refdocs/chunker.py` (**0 bytes, empty**)

```
Recent commits:
7f7be73 integrate canonical visual behavioral confidence
0c2823c backup before confidence scoring
6df2b30 Add nginx reverse proxy with self-signed HTTPS certificate
549c448 Initial commit: InterviewIQ - AI-powered mock interview platform
```

**Note:** `backend/interviewiq_test.db` is a *tracked, modified* SQLite file, and the root `.env` sets `DATABASE_URL=sqlite:///./interviewiq_test.db` — i.e., this file appears to be the actual local dev database, not a disposable fixture, despite its name.

---

## 4. Phase 2C Verification

Inspected: `backend/app/auth/permissions.py`, `backend/app/schemas/organization.py`, `backend/app/routers/organizations.py`, `backend/app/models/{organization,organization_membership}.py`, `frontend/src/pages/{AdminOrganizations,CompanyDashboard}.jsx`, `backend/tests/`.

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1 | Enriched member listing | Verified | `organizations.py:366-414` joins `OrganizationMembership`+`User`; `MembershipListResponse`/`MembershipListItem` schemas |
| 2 | Pagination | Verified | `organizations.py:372-412`, `page`/`page_size` clamped 1-100 |
| 3 | Add active user to org | Verified | `POST /organizations/{id}/members`, `organizations.py:417-464` |
| 4 | Block adding inactive users | Verified | `organizations.py:431-432` explicit 400 |
| 5 | Update membership role | Verified | `PATCH .../members/{id}/role`, `organizations.py:481-502` |
| 6 | Activate membership | Verified | `PATCH .../members/{id}/status`, `organizations.py:505-546` |
| 7 | Deactivate membership | Verified | same endpoint, `is_active=false` |
| 8 | Remove non-owner membership | Verified | `DELETE .../members/{id}`, `organizations.py:548-577` |
| 9 | AuthZ for system_admin/owner/admin | Verified | `require_membership_manager`, `permissions.py:177-209` |
| 10 | Universal owner-invariant **single shared guard** | **Partial** | The invariant behavior is consistent, but it is **duplicated inline three times** (`organizations.py:495-496`, `:519-520`, `:559-560`), not one reusable guard function |
| 11 | Prevent owner removal | Verified | `organizations.py:559-560`, no system_admin bypass |
| 12 | Prevent owner deactivation | Verified | `organizations.py:519-520`, no bypass |
| 13 | Prevent owner demotion | Verified | `organizations.py:495-496` + schema-level: `_ASSIGNABLE_MEMBERSHIP_ROLES` excludes `owner` entirely (`schemas/organization.py:137-141`) |
| 14 | Hide private-org existence from non-members (404 vs 403) | Verified | `permissions.py:97-171`, non-member → 404 uniformly; only an existing member with insufficient role gets 403 |
| 15 | `require_membership_manager` exists | Verified | `permissions.py:177-209` |
| 16 | Actually used as a route dependency | Verified | Used in `organizations.py` (4 routes) and reused in `invitations.py` (4 routes) — not dead code |
| 17 | Request schemas | Verified | `MembershipCreate`, `MembershipRoleUpdate`, `MembershipStatusUpdate` (`schemas/organization.py:171-204`) |
| 18 | Response schemas | Verified | `MembershipUserSummary`, `MembershipListItem`, `MembershipListResponse` (`:144-168`) |
| 19 | Frontend membership page | Verified | `AdminOrganizations.jsx` calls all 4 mutating endpoints + paginated list; owner rows render without mutation controls. `CompanyDashboard.jsx` (org self-service) is **read-only** — no management UI for an org's own owner/admin outside the system-admin console |
| 20 | Tests (success/invalid/forbidden) | **Missing** | The entire `backend/tests/` directory contains exactly **one** file, `test_fusion_integration.py`, covering fusion-response shaping only — zero tests reference organizations, memberships, or `require_membership_manager` |

### PHASE 2C PARTIAL

Justification: the implementation itself is thorough and correctly enforces every invariant checked (owner protection, privacy-preserving 404s, role-scoped access) — but it has **no automated test coverage whatsoever**, and the "universal" owner guard is copy-pasted three times rather than a single shared function, so a future edit to one branch could silently desync from the other two.

---

## 5. Candidate Workflow Audit

The app has **two role concepts** that don't overlap as the audit brief assumed: a `student` role (has the full interview flow) and a `candidate` role (dashboard is four "Coming Soon" placeholder tiles, `CandidateDashboard.jsx`, with **no path into the interview flow at all**). The workflow below describes the `student` role, the only one that can actually take an interview.

| Step | Status | Evidence |
|---|---|---|
| Login | Fully implemented | `Login.jsx` → `POST /auth/login` |
| Candidate dashboard | Fully implemented (student); UI-only stub (candidate role) | `Dashboard.jsx` (real stats) vs `CandidateDashboard.jsx` (placeholder cards) |
| Choose track | Fully implemented, client-side only | `TechnicalTrackSelection.jsx`, hardcoded track list, nothing hits backend |
| Choose interview type | Fully implemented, client-side only | `InterviewTypeSelection.jsx`, hardcoded type list |
| Choose number of questions | **Missing** | No UI control exists; `InterviewRoom.jsx:42` hardcodes `.slice(0, 5)` |
| Generate eligible questions | Fully implemented | `GET /questions` (`questions.py:15-31`), real DB filter by type/track/difficulty |
| Store ordered question sequence | **Missing** (server-side) | Sequence lives only in React state, never sent to or stored by the backend |
| Display one question at a time | Fully implemented | `InterviewRoom.jsx:287-334`, `currentQ` index |
| Request camera/mic | Fully implemented | `InterviewRoom.jsx:48-62`, single `getUserMedia({video,audio})` call |
| Record current answer | **Partially implemented / mismatched to spec** | One continuous `MediaRecorder` spans the *entire* multi-question session — there is no per-question recording |
| Click Next | Implemented, but does none of the expected segment work | `goNext()` (`InterviewRoom.jsx:103-110`) only increments `currentQ` and resets a cosmetic timer |
| Close current answer segment | **Missing** | No segment concept exists |
| Bind segment to active question ID | **Missing** | No question ID is ever sent to the backend at any point |
| Display next question | Fully implemented | same component |
| Complete session | Fully implemented | `finishInterview()` stops the single recorder, builds one Blob |
| Process NLP/Audio/Vision | **Mocked** | `POST /interviews/analyze/{id}` → `run_vision`/`run_audio`/`run_nlp`, all `random.*` |
| Late Fusion | Implemented math over fake inputs | `fusion_engine.fuse_scores`, `0.35/0.30/0.35` |
| Store results | Fully implemented (fake data) | `Result` row written |
| Display final report | Fully implemented | `Report.jsx` → `GET /interviews/report/{id}` |
| Display interview history | Fully implemented | `History.jsx` → `GET /dashboard/history` |

**Determination:** the product supports **one continuous recording covering multiple displayed questions**, not true multi-question sessions with per-answer segmentation. It is **not** "only `/fusion-test`" — a real, separate, multi-question-looking Interview Room exists — but its AI backend is entirely mocked, and the one real-AI path (`/fusion-test`) is itself strictly single-question, unauthenticated, and never persisted. This is precisely "a mixture of normal workflow and demo workflow" that never intersect.

---

## 6. Interview Session Data Model

Seven ORM models total exist in the entire codebase: `Organization`, `Interview`, `Question`, `OrganizationInvitation`, `Result`, `OrganizationMembership`, `User`. None of `InterviewSession`, `SessionQuestion`, `InterviewQuestion`, `AnswerSegment`, `ResponseSegment`, `QuestionReferenceVersion` exist, and no child table keyed by `(session_id, question_id)` exists anywhere.

**`Interview`** (`backend/app/models/interview.py:7-21`): `id, user_id, interview_type, track, video_path, audio_path, final_score, verdict, created_at`. 1:1 with `Result` (`Result.interview_id` unique).

**`Question`** (`backend/app/models/question.py:6-14`): `id (int, autoincrement), question, interview_type, track, difficulty, created_at`. No `is_active`, no `organization_id`, no version field, no reference/key-point field.

**`Result`** (`backend/app/models/result.py:7-25`): `id, interview_id (unique FK), vision_score, audio_score, nlp_score, emotion, eye_contact, wpm, pause_count, filler_count, transcript, weakest_module, recommendations (JSON), created_at`.

| Requested concept | Where stored | Status |
|---|---|---|
| session/interview ID | `interviews.id` | Verified |
| user ID | `interviews.user_id` | Verified |
| track | `interviews.track` | Verified |
| requested question count | nowhere — frontend hardcodes 5 | Missing |
| selected question IDs | nowhere — no FK/join table | Missing |
| sequence order / sequence_index | nowhere | Missing |
| current question pointer | client React state only, ephemeral | Missing (server-side) |
| answer start/end timestamps | nowhere (only interview-level `created_at`) | Missing |
| media path | `interviews.video_path` **and** `audio_path` — same single file for both | Verified, but flat (one file for whole interview) |
| transcript | `results.transcript` — one blob for the whole interview | Verified, flat |
| processing status | not a column — ephemeral response dict only | Missing |
| result ID | `results.id`, 1:1 via `interview_id` | Verified |
| model version | nowhere | Missing |
| failure reason | nowhere — only transient `HTTPException` details | Missing |

Alembic history (`backend/alembic/versions/`) confirms the `interviews`/`questions`/`results` schema has been unchanged since the baseline migration `48e6b0ce95ae` — all four subsequent migrations touched only organizations/users/invitations. **The schema does not support multiple answers per interview session**, by direct evidence of the model fields, not just naming.

---

## 7. Question Selection

**Algorithm as actually implemented** (pseudocode from real code, `InterviewRoom.jsx` + `questions.py:15-31`):
```
GET /questions?interview_type=<t>&track=<tr>
  -> SELECT * FROM questions
     WHERE interview_type = :t [AND track = :tr] [AND difficulty = :d]
     ORDER BY id ASC                      # deterministic, NOT random
questions = response.slice(0, 5)           # hardcoded ceiling of 5, no randomness
if questions.length == 0: redirect to /interview/type
```

| Check | Status | Evidence |
|---|---|---|
| Random selection | **Missing** | No `random.sample`/`shuffle`/`ORDER BY RANDOM()` anywhere in the question-fetch path (repo-wide grep) |
| Duplicates prevented | N/A (trivial) | Structurally impossible since it's an ordered SQL slice of unique PKs, not a sampling loop |
| Inactive questions excluded | **Missing** | `Question` model has no `is_active` column to filter on at all |
| Organization restriction | **Missing** | `Question` has no `organization_id`; comment in code (`questions.py:41-43`) explicitly says "no organization-owned question bank yet" |
| Order persisted | **Missing** | Lives only in React state, refetched fresh every mount |
| Refresh changes sequence? | Coincidentally no (same deterministic query), but all in-progress recording is lost | Missing (no real session persistence) |
| Reconnect resumes sequence? | Same reasoning — "resumes" only by accident of determinism | Missing |
| Requested count > available | Handled incidentally — `.slice(0,5)` on a shorter array just returns what exists; empty list redirects | Partial |
| Question IDs stable within session | Verified | array fetched once, only read thereafter |
| Seed used | No | grep confirms no `random.seed` anywhere |
| Normal route uses this algorithm | Verified | `InterviewRoom.jsx` is the only consumer |

---

## 8. One-Question-at-a-Time Flow

Component: `frontend/src/pages/InterviewRoom.jsx`.

- Only one question shown at a time: **Verified** (`currentQ` index, `AnimatePresence mode="wait"`).
- Camera/mic permission: **Verified**, single combined `getUserMedia` call, dedicated full-screen error state on denial.
- Recording: **Verified but session-wide, not per-question** — one `MediaRecorder` started once (`beginRecording()`), stopped once (`finishInterview()`).
- Recording timer: **cosmetic only** — a per-question countdown that does not stop recording or auto-advance at zero.
- Preview / Retry: **Missing** — no playback-before-submit, no re-record control.

**Next button — exact behavior** (`InterviewRoom.jsx:103-110`):
```js
const goNext = () => {
  if (currentQ < questions.length - 1) {
    setCurrentQ(q => q + 1)
    resetQuestionTimer()
  } else {
    finishInterview()
  }
}
```
Does it: stop MediaRecorder? **No.** Close/finalize a segment? **No segment exists.** Upload the segment? **No.** Associate with question ID? **No — never happens anywhere in this component or backend.** Wait for upload before advancing? **N/A, no upload occurs here.** Advance immediately? **Yes, fully synchronous.** The practical risk is not "losing the current answer" on Next — it's that **no individual answer is ever captured or bound to its question at all**; the whole session becomes one undifferentiated recording.

- Page refresh: **destructive** — no `localStorage`/`sessionStorage` persistence; a refresh mid-interview loses the entire in-progress recording and bounces to `/interview/type`.
- Browser back button: unhandled, no `beforeunload`/`popstate` guard.
- Upload failure: handled one level up (`Processing.jsx`) with a generic error screen whose "Try Again" discards the recorded blob entirely.
- Permission failure: **Verified**, dedicated full-screen "Camera Access Required" UI.

---

## 9. Question–Answer Binding

**Normal workflow: Missing entirely.** No `question_id` is ever transmitted from `InterviewRoom.jsx`/`Processing.jsx` to any backend endpoint. `Interview` and `Result` have no `question_id` column. The candidate sees real, distinct questions, but the system records zero information about which spoken content, if any, answered which question.

**`/fusion-test` (demo) workflow: a `question_answer_match`/`question_answer_validity` field exists, but it is NOT structural binding — classify it as Heuristic.**

Exact function, `InterviewIQ_AI/fusion/schemas.py:16-28`:
```python
def assess_question_answer_match(question: str, transcript: str | None) -> dict[str, Any]:
    if not transcript or not transcript.strip():
        return {"valid": None, "reason": "No usable NLP transcript was produced."}
    q, t = _tokens(question), _tokens(transcript)
    if not q:
        return {"valid": None, "reason": "Question text has no comparable terms."}
    overlap = sorted(q & t)
    ratio = len(overlap) / len(q)
    if ratio >= 0.18 and overlap:
        return {"valid": True, "reason": f"Transcript overlaps ... {', '.join(overlap[:8])}."}
    if ratio < 0.08:
        return {"valid": False, "reason": "... technical score is withheld."}
    return {"valid": None, "reason": "Automated comparison is inconclusive; human review required."}
```
This is a bag-of-words token-overlap ratio (thresholds 0.18/0.08) between question text and ASR transcript — a **Heuristic**, not embeddings, not NLI, not a session-structural check. It gates whether `fusion_summary.final_technical_score` is populated (`fusion_pipeline.py:228`).

Because `/fusion-test` is entirely stateless (one video + one client-supplied `question_id`, no session, no persistence), the concepts of "duplicate binding," "one segment→two questions," or "sequence mismatch" don't apply — there is no session for them to violate.

**Recommended rename (report-only, no code changed):** the field is presentation-correctly named `question_answer_validity`/`question_answer_match` for what it does (a lexical relevance heuristic) — it should **not** be renamed to imply "binding," since no structural binding exists anywhere in this codebase to rename toward.

---

## 10. Semantic Relevance

> "Semantic answer relevance is not implemented as a separately calibrated classifier."

The only relevance-adjacent mechanism is the lexical-overlap heuristic in Section 9 (thresholds 0.18/0.08, unrelated to BGE-M3/embeddings/NLI). Off-topic answers are instead penalized **indirectly**, through the NLI claim-scoring pipeline:

`InterviewIQ_AI/nlp/interview-iq-fusion-handoff/src/interview_iq/scoring/aggregation.py:50-56` (`score_claim`):
```python
if max_e >= tau_e:  VERIFIED,     score = 1.0
elif max_c > tau:   CONTRADICTED, score = -max_c
else:                NEUTRAL,     score = alpha
```
An off-topic transcript produces claims with no matching reference chunks → low `max_e`/`max_c` → NEUTRAL verdicts (`alpha = 0.0` in the current pre-calibration defaults) → low Precision/Coverage → low/zero final Answer Content Score. This is the indirect off-topic penalty. Thresholds (`configs/calibration.yaml`, `configs/scoring.yaml`, `configs/retrieval.yaml`): `tau=0.5`, `tau_e=0.9`, `alpha=0.0`, `k=10` (BGE-M3 top-k) — all explicitly tagged in code as `"PRE-CALIBRATION DEFAULT — NOT VALIDATED"`.

---

## 11. Question Bank

| # | Feature | Status | Evidence |
|---|---|---|---|
| 1 | List questions | Verified | `GET /questions`, `questions.py:15-31` |
| 2 | Pagination | **Missing** | `.order_by(Question.id).all()` — no limit/offset anywhere |
| 3 | Search | **Missing (backend)** / Partial (client-side text filter only) | `AdminQuestions.jsx:81-85` filters the full fetched list client-side |
| 4 | Track filtering | Verified (backend); no UI control | `questions.py:18,27-28` |
| 5 | Active/inactive filtering | **Missing** | No `is_active` column exists at all |
| 6 | Create question | Verified | `POST /questions`, 201 |
| 7 | Update question | Verified | `PUT /questions/{id}` |
| 8 | Activate question | **Missing** | No such route/field exists |
| 9 | Deactivate question | **Missing** | Same |
| 10 | Delete question | Verified — **hard delete** | `db.delete(question)` |
| 11 | Authorization | Verified, coarse | `require_global_roles(SYSTEM_ADMIN)` on all mutations; `GET` open to any authenticated user |
| 12 | System-admin access | Verified | as above |
| 13 | Organization-admin access | **Missing** | `company_admin` has zero mutation access; code comment confirms it's intentional (no org-owned bank yet) |
| 14 | Stable question ID | Verified — plain autoincrement int, not UUID | `question.py:9` |
| 15 | Prompt text | Verified | `question.py:10` |
| 16 | Track | Verified | free-text string, not enum |
| 17 | Difficulty | Verified | free-text string, not enum, defaults "Medium" |
| 18 | Reference material field | **Missing** | `Question` has exactly 5 real columns; no reference text at all |
| 19 | Reference chunks | **Contradictory/Partial** | Real chunks exist, but pre-authored inline in a static JSON, not produced by any chunker; `refdocs/chunker.py` is a **0-byte empty file** |
| 20 | Required key points | Verified — but only in the NLP JSON, not the DB | `data/refdocs/reference_docs_250_FINAL_v1.json` |
| 21 | Organization ownership | **Missing** | Global question bank, no `organization_id` |
| 22 | Versioning | **Missing** (DB); informal filename-suffix only on the NLP side (`_v1`, `_v2`) | — |
| 23 | Frontend Admin Questions page | Verified | `AdminQuestions.jsx` calls list/create/update/delete |
| 24 | Tests | **Missing** | Zero tests reference the questions router/model/schema |

### NLP source of truth — mixed and disconnected
The GUI-managed `questions` DB table (integer IDs) is **entirely separate** from the actual NLP grading source: a static JSON file, `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/data/refdocs/reference_docs_250_FINAL_v1.json` (250 hand-authored documents, string IDs like `SE-028`, `DA-001`). This file is what backs `GET /interviews/analysis-questions` and `POST /interviews/analyze` (the `/fusion-test` pipeline) — the Admin Questions GUI has **zero effect** on it. Only **one** of the 250 NLP questions has any counterpart row in the DB (`backend/app/utils/seed.py:4-12`, an acknowledged manual copy of `SE-028`, with no synchronization mechanism — the two copies can silently drift). The other 249 real-scoring questions are invisible to/unmanageable from the Admin Questions page. `InterviewIQ_AI/nlp.zip` (525MB, untracked) is confirmed to be an older backup snapshot of the same `interview-iq-fusion-handoff` tree, predating several current files (`fusion/`, `cli/`, `nli/finetune.py`, etc.) — not a separate lineage.

---

## 12. Real AI Flow

Two independent pipelines; only Pipeline 2 exercises real models end-to-end.

**Pipeline 1 (normal/`student` flow) — Status: Mocked at every AI stage.**
`InterviewRoom.jsx` → `Processing.jsx` → `POST /interviews/start-interview` → `POST /interviews/upload-video/{id}` → `POST /interviews/analyze/{id}` (`interviews.py:241-290`) → `run_vision`/`run_audio`/`run_nlp` (all `random.*`, `backend/app/ai_modules/*.py`) → `fuse_scores` (`fusion_engine.py`, real math, fake inputs) → `Result` DB row → `Report.jsx`.

**Pipeline 2 (`/fusion-test`) — Status: Real, subprocess-orchestrated, isolated, not persisted.**
`FusionTest.jsx` → `POST /interviews/analyze` (no id, `interviews.py:139-193`, **unauthenticated**) → `_execute_fusion` (`interviews.py:58-130`, `asyncio.to_thread(subprocess.run)`, timeout 3900s) → `InterviewIQ_AI/fusion/fusion_pipeline.py`:
1. Preflight checks (venv paths, checkpoints, `GROQ_API_KEY` presence)
2. ffmpeg audio extraction (own 180s timeout)
3. Vision inference (separate `.venv_vision`, real Swin-T/LoRA/TCN checkpoint)
4. Audio inference (separate `.venv_audio`, real Wav2Vec2-XLSR+BiLSTM checkpoint)
5. NLP: ASR (faster-whisper `large-v3`, Arabic) → glossary normalization (deterministic, 892-entry glossary) → claim decomposition (Groq LLM, `GROQ_API_KEY` **currently empty on disk**, so this stage is presently non-functional without manual `.env` configuration) → BGE-M3 retrieval (top-k=10) → mDeBERTa NLI (base model only — see §14) → Precision/Coverage/Answer Content Score
6. `confidence_fusion.fuse_confidence` — 0.60/0.40 Delivery Confidence
7. `backend/app/fusion_response.py:clean_fusion_response` — presentation mapping, withholds negative raw scores
8. Result written to `output.json` on disk and returned directly in the HTTP response — **never written to any database table** (the route takes no `db: Session` dependency at all)
9. `FusionTest.jsx` renders it

**Frontend label check:** "Answer Content Score" (`FusionTest.jsx:257,330`) traces cleanly to backend `technical_score`; no stray "Technical Score" string exists in `frontend/src` (only `Report.jsx`'s unrelated mocked "NLP Score" label, a different random field).

---

## 13. Fusion Test Audit

`frontend/src/pages/FusionTest.jsx`, route `/fusion-test` (`App.jsx:42`), self-labeled in its own UI as **"Local real-model test."**

| Check | Status |
|---|---|
| Requires authentication | **No** — neither the frontend route nor `GET /interviews/analysis-questions`/`POST /interviews/analyze` have any auth dependency |
| Question loading | Real API (`_load_fusion_questions()` reads the reference JSON) |
| Uploaded video real | Yes, real file upload input |
| Browser recording real | Yes, real `MediaRecorder` |
| One combined file | Yes, single `video` field + `question_id` in `FormData` |
| Sends `question_id` | Yes |
| NLP/Audio/Vision/Fusion real | Yes, all real (see §12) |
| Hardcoded/static displayed metrics | None found — all render from `result.*` with explicit "Not available" fallbacks |
| Fallback demo response on error | None — `catch` only sets an error banner, never substitutes canned data |
| Errors hidden | No — visible `role="alert"` banner |
| Results stored in DB | **No** |
| Part of normal candidate workflow | **No** — not linked from `Navbar`, `Dashboard`, `History`, or any candidate page; reachable only by direct URL |

**Classification: Real integration page**, but architecturally isolated — an unauthenticated, unlinked, non-persisting engineering test harness, not the production candidate flow.

---

## 14. NLP Audit

| Component | Status | Detail |
|---|---|---|
| ASR | Real | `faster-whisper`, checkpoint `large-v3`, language `ar`, `int8` on CPU (`configs/asr.yaml`) |
| VAD | Real | Silero VAD gates ASR; `no_speech`/`too_short` short-circuit before Whisper runs |
| Transliteration/glossary | Real, deterministic | `data/glossary/transliteration_glossary.json`, 892 entries, pure regex substitution, no network call |
| Claim decomposition | Real (Groq LLM) but **currently dead on disk** | `GROQ_API_KEY`/`GROQ_MODEL` are **empty** in `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/.env`; preflight will mark this component `failed` until manually configured. Also: `client.py:22`'s docstring claims it's "NOT wired into production" — **stale/contradictory**, since `pipeline.py` does default to it |
| `configs/decomposition.yaml` | **Superseded/dead** | Describes an archived AraT5 approach; `decomposition/inference.py` is `raise NotImplementedError` |
| BGE-M3 retrieval | Real, top-k=10 | Marked "PRE-CALIBRATION DEFAULT — NOT VALIDATED" in `configs/retrieval.yaml`. Documented latent bug: production embedder omits `use_fp16=False`, crashes on CPU (`RuntimeError`) for any question with >10 reference chunks — doesn't surface today only because the current dataset stays ≤12 chunks/doc |
| NLI | Real, base model only | `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` |
| **LoRA adapter** | **Trained but never loaded in production** | `nli/finetune.py` (real training) and evaluation tooling exist, but `pipeline.py:evaluate_answer()`'s `adapter_path` defaults to `None`, and the actual production entry point (`runners/run_nlp_json.py`) never passes one — the live pipeline always runs zero-shot |

**Exact formulas:**
- Precision (`scoring/aggregation.py:50`, `scoring/metrics.py:114`): per-claim `VERIFIED(1.0) / CONTRADICTED(-max_c) / NEUTRAL(alpha)` via `max_e>=tau_e` / `max_c>tau`; `precision = mean(scores)`.
- Coverage (`scoring/metrics.py:132`): `coverage = mean(max_e_per_keypoint)`.
- Final merge, harmonic F (`scoring/metrics.py:142,171`): `if precision<0: return precision` (bypasses coverage entirely); `elif precision+coverage<=0: 0.0`; `else: 2·P·C/(P+C)`; `score = harmonic_f × 100`. Range **[-100, +100]**, not clipped to 0.
- Thresholds: `tau=0.5, tau_e=0.9, alpha=0.0, k=10, score_scale=100` — all tagged "PRE-CALIBRATION DEFAULT — NOT VALIDATED".
- Silence: VAD `no_speech`/`too_short` → typed status `ASR_NO_SPEECH`/`ASR_TOO_SHORT`, short-circuits before scoring.
- Negative contradiction: a single confident contradiction can push the whole score negative and unbounded below — intentional (documented ranking "correct > silence > wrong answer"), withheld from the UI as a raw percentage (`raw_values_withheld` flag).

**Real-model tests exist**: `test_real_nlp_pipeline.py` is an explicit, non-mocked, real-Groq-API-calling driver (not run in this audit — paid API, out of scope). No pytest unit-test suite exists for the NLP module otherwise.

**Question reference consistency:** within `/fusion-test`, the same reference JSON is loaded three times (question listing, backend validation, subprocess lookup) with consistent integrity validation (`refdocs/loader.py` rejects duplicate/dangling IDs) — no mismatch found there. But there is **no versioning mechanism** — if the JSON changes between listing and analysis, nothing detects it. And critically, the normal workflow has **no reference lookup at all** (§9/§10), so the "displayed question vs. evaluated reference" question is moot there — nothing is evaluated.

---

## 15. Audio Audit

Two class of finding: the **real model** (used only by `/fusion-test`) and the **candidate-facing score arithmetic** claim from the audit brief (Variant A/B formulas).

- **Class mapping**: Verified exact match — `labels.json`: `{"0":"Low Emotion","1":"Neutral Emotion","2":"High Emotion"}`.
- **Model Confidence**: Verified exact match to `probabilities=softmax(logits); confidence=max(probabilities)` (`audio_module.py:293-306`). Output range 0.0–1.0 (not percent); percent conversion happens only in the frontend display formatter.
- **Calibration**: **None** — no temperature scaling, Platt/isotonic scaling, ECE, or Brier score anywhere for the audio classifier (the only calibration-tagged files in the repo belong to the unrelated NLI scoring subsystem). **Label: "Uncalibrated maximum softmax probability."**
- **Variant A (15/50/100) and Variant B (0/50/100) formulas**: **Neither exists anywhere in the repository.** Repo-wide search for these weight patterns against Low/Neutral/High probability variables returns zero matches.
- **What actually produces the candidate-facing audio number**: a completely separate, DSP-based function, `InterviewIQ_AI/audio/audio_confidence.py:114-121` (`vocal_confidence_score`), self-labeled `"""Deterministic vocal-delivery features; no emotion inference is performed."""`:
```python
score = 100.0 * (
    weights["speaking_rate"]*rate_score + weights["pause_control"]*pause_score
    + weights["volume_stability"]*volume_score + weights["speech_continuity"]*continuity
)
```
weights `0.30/0.30/0.25/0.15` (`confidence_config.py:23-26`), range 0-100, `None` if insufficient evidence. This never consumes the emotion-classifier's probabilities at all.
- **The "97.1% → 44.5%" example**: traced to a real pipeline output artifact (`InterviewIQ_AI/fusion/outputs/website/...SE-028.json`) where `model_confidence: 0.9709` (emotion classifier max-softmax) and `vocal_confidence_score: 44.504` (DSP composite) **co-occur but have no mathematical relationship to each other** — two independent metrics, not a transformation. **No implemented transformation from raw model confidence to a lower candidate-facing score exists.**
- **Speaking Rate / Pause Control / Volume Stability / Speech Continuity**: **Real** (waveform-derived) in the `/fusion-test` pipeline; **hard-coded/random** (`wpm`, `pause_count` via `random.uniform`/`randint`) in the normal-flow mock.
- **Classification: Contradictory** — two systems of fundamentally different validity coexist unreconciled: the normal-flow `audio_score` is Hard-coded/Demo-only; the `/fusion-test` `vocal_confidence_score` is an Implemented heuristic (self-labeled "Experimental... requiring human validation"); raw `model_confidence` is an Unvalidated experimental indicator.

**Dataset/model metadata**: BAVED (not RAVDESS — RAVDESS is used only by the *vision* model), 1,935 recordings, 60 speakers, 3 classes, 16kHz mono. Architecture: `elgeish/wav2vec2-large-xlsr-53-arabic` backbone + BiLSTM(50, bidirectional) + Linear(100→3), ~315M params. **NB09 metrics (89.15%/89.19%)**: found only in `config.json` (packaged deployment metadata) + README + a code docstring — **no notebook, training log, or CSV artifact exists anywhere** to independently verify them; not repository-verified as an experimental result. **NB07 metrics (87.86%/88.03%)**: **do not exist anywhere in the repository** — zero matches for the numbers or the label.

---

## 16. Vision Audit

Real inference, traced end-to-end for `/fusion-test` only: `FusionTest.jsx` → `POST /interviews/analyze` → `fusion_pipeline.py` → `adapters/vision_adapter.py` (separate `.venv_vision`) → `InterviewIQ_AI/vision/vision_module.py:analyze_visual_confidence` → real MTCNN face detection + Swin-T/LoRA checkpoint (`vsc_ravdess_lora_r16_test73_24.pt`, 118,788,254 bytes, confirmed on disk).

- Windowing: 4.0s windows, 4.0s stride, trailing partial window kept only if ≥1.5s (`vision_module.py:819-848`).
- Formula — **verified exact match** to the audited claim:
```python
base = 0.35*comfort + 0.25*stability + 0.20*recovery + 0.20*(1 - negative_persistence)
score = clip(base*100, 0, 100)
```
(`visual_behavioral_confidence.py:261-268`; weights validated to sum to 1.0.)
- Evidence gates — **verified exact match**: minimum windows = 3, minimum mean face-detection ratio = 0.60 (`visual_behavioral_confidence.py:37-38`).
- Notebook vs. canonical module vs. runtime: all three are numerically identical (weights, thresholds confirmed present verbatim in `VSC_RAVDESS_LoRA_R16_Visual_Confidence.ipynb`).
- **Dead-code finding**: `vision_module.py` contains its own duplicate copies of the scoring functions/config (never called — `calculate_visual_confidence_summary()` delegates to the canonical `visual_behavioral_confidence.py` module instead). Not a live bug, but a drift risk since nothing enforces the duplicate stays in sync.
- **Displayed values are real inference from the uploaded video** on `/fusion-test`; on the normal-flow `Report.jsx`, the "Vision" score is the unrelated `random.uniform` stub from `backend/app/ai_modules/vision_module.py` — **Contradictory** between the two paths sharing a filename/label but not an implementation.

---

## 17. Late Fusion Audit

**Three fusion implementations exist; two are live, and they are not the same formula:**

| Impl | Formula | Live route | Frontend |
|---|---|---|---|
| A — `InterviewIQ_AI/fusion/confidence_fusion.py` + `confidence_config.py` | Delivery = 0.60·vocal + 0.40·visual | `POST /interviews/analyze` | `/fusion-test` only |
| B — `backend/app/ai_modules/fusion_engine.py` | `0.35·vision + 0.30·audio + 0.35·nlp` | `POST /interviews/analyze/{id}` | Normal flow (`Report.jsx`) — **on mocked `random` inputs** |
| C — `interview_iq/fusion/__init__.py` | none (empty file) | not imported anywhere | dead |

**Implementation A (the real 60/40 "Delivery Confidence") — verified in full:**
- Weight source: hard-coded dataclass literal (`FusionConfidenceConfig`, `confidence_config.py:29-31`), self-labeled `"""Experimental delivery-confidence defaults requiring human validation."""` — **not** config/env/DB/frontend-controlled.
- **Audio input is NOT raw emotion-model confidence** — it is `vocal_confidence_score`, the deterministic 4-factor DSP composite from §15 (speaking rate/pause/volume/continuity), explicitly documented `"no emotion inference is performed"`.
- Visual input is the composite Visual Behavioral Score from §16, not raw classifier confidence.
- Branch logic (`confidence_fusion.py:9-58`): both valid → `0.60·vocal+0.40·visual`, `status="complete"`; one valid → that modality's score passes through unchanged after renormalization (`status="partial"`); neither valid → `final=None, status="insufficient"`. Confirmed against real unit tests (`InterviewIQ_AI/fusion/test_confidence.py:77-101`, e.g. `fuse_confidence(80,50) == 68`).
- **Verified excluded from Delivery**: `technical_score`/Answer Content Score, raw audio model confidence, raw vision model confidence, visual reliability (used only as an evidence gate), question relevance score — confirmed both by code inspection (function signature `**_ignored: Any` swallows extras) and by a dedicated test, `test_model_and_technical_confidence_are_ignored`.
- `used_modalities` **as a literal field name does not exist** — the equivalent concept is expressed as `confidence_evidence_status` (`complete`/`partial`/`insufficient`) and `effective_weights`.
- `limitations` field: Verified, populated with 3-5 human-readable caveats (`fusion_pipeline.py:200-207`).
- **No calibration artifact found for the 60/40 split** — one commit total introduces the file already at 0.60/0.40, no weight-sweep script, no human-ground-truth comparison, no A/B test artifact anywhere. Per audit instructions: **"Reasoned baseline configuration, not a calibrated result."**

**Implementation B is what the main product actually uses**, and it has no relationship to the 60/40 formula at all — different weights, different three inputs, all of which are `random.uniform` mocks (`backend/app/ai_modules/{vision,audio,nlp}_module.py`).

---

## 18. Final Report Audit

`frontend/src/pages/Report.jsx` (route `/report/:id`) — distinct page from `FusionTest.jsx`, and it has **no knowledge of the Fusion schema at all**.

| Requested field | Displayed? |
|---|---|
| Question text / ID | Missing (no binding exists to display) |
| Answer Content Score / Precision / Coverage / claims | Missing — only shows mocked `nlp_score` |
| Audio class / model confidence / candidate-facing score / validity | Missing — only mocked `emotion`, `wpm`, `pause_count` |
| Visual behavioral score / reliability / sufficient evidence / windows | Missing |
| Delivery Confidence / used_modalities / limitations / failure reasons | Missing |
| Transcript | Shown, but is one of 5 hard-coded canned strings, `random.choice`-selected, unrelated to actual audio |
| Processing timestamp | Partial — only interview creation time |

**Semantics checks:**
- Unavailable values shown as 0% rather than "N/A": **Contradictory finding** — `Report.jsx` plots null scores as `0` on its radar chart (`?? 0`), whereas the Fusion pipeline correctly distinguishes "Not available" from a real zero. `Report.jsx` never inherited that discipline because it has no concept of insufficient evidence to begin with.
- Candidate-facing audio score mislabeled: **Contradictory** — `Report.jsx` presents the random mock `audio_score` as real "Pace, clarity & confidence" performance with no diagnostic caveat.
- Loads persisted results by ID: **Verified** — `GET /interviews/report/{id}`, DB-backed, ownership-checked (`user_id` filter, generic 404 on mismatch).

---

## 19. Persistence Audit

| Field | Persisted? |
|---|---|
| Interview/session | Verified |
| Ordered question IDs / sequence_index | **Missing** |
| Answer segments | **Missing** — one video/audio path per whole interview |
| Media path / transcript | Verified (flat, whole-interview) |
| Question-answer binding | **Missing** |
| Precision, Coverage, claims | **Missing** |
| Answer Content Score | Partial — `results.nlp_score` exists but stores mocked data, not the real Fusion concept |
| Audio class/probabilities/model confidence/candidate score/validity | **Missing** |
| Visual class/probabilities/model confidence/behavioral score/reliability/evidence/windows | **Missing** |
| Delivery Confidence / used_modalities / limitations / failure reasons | **Missing** |
| Model versions / per-stage processing timestamps | **Missing** |

**Fields in the API response but never persisted**: the entire Fusion response shape (`technical_score`, `precision`, `coverage`, `visual_behavioral_confidence_score`, `final_confidence_score`, `question_answer_validity`, `sufficient_evidence`, `number_of_windows`, `score_range`, `confidence_margin`, `warnings`, etc., all defined in `fusion_response.py:59-130`) — none have a DB column; they exist only in the HTTP response and an on-disk JSON artifact.

**Fields persisted but never displayed**: `interviews.video_path`/`audio_path` are stored but never surfaced/linked in any frontend page. `results.weakest_module`/`recommendations` are both persisted and displayed — no silent drop found there.

---

## 20. History Audit

`frontend/src/pages/History.jsx` (`/history`, `student`-only) → `GET /dashboard/history` (`backend/app/routers/dashboard.py:13-40`).

| Check | Status |
|---|---|
| List previous interviews | Verified — filtered by `user_id` |
| Pagination | **Missing** — `.all()`, no limit/offset |
| Filtering | Partial — client-side only, by `interview_type` |
| Sort order | Verified — `created_at.desc()` |
| Open previous report (real ID, re-fetch) | Verified |
| Ownership checks | Verified — `user_id` filter both in list and detail routes, generic 404 on mismatch |
| Organization access scoping | **Missing** — `Interview` has no `organization_id` |
| Question text | Missing (no binding) |
| Result summary / full detail | Verified |
| Failed-processing / retry state | Partial — no modeled failure state exists because the mock pipeline can't fail; "Try Again" restarts the whole flow, no per-interview retry |
| Tests | **Missing** |

**Classification: Partially implemented.** Genuinely database-backed and ownership-scoped — not mock/in-memory — but missing pagination, org scoping, question display, and any real failure/retry model, and it sits entirely on top of the mocked scoring pipeline.

---

## 21. Authentication and Authorization

Solid overall design (bcrypt hashing, DB-refreshed role checks on every request, no client-controlled role/JWT claim escalation, privacy-preserving 404-vs-403 semantics, "last active system_admin" self-lockout protection). Specific gaps:

- **No token refresh endpoint** — sessions rely solely on a 7-day access token; no revocation mechanism beyond flipping `is_active`.
- **CRITICAL — two unauthenticated, resource-heavy routes**: `GET /api/interviews/analysis-questions` and `POST /api/interviews/analyze` (`interviews.py:133-193`) have no `Depends(get_current_user)`, unlike every other route in the same file. This is by design (the frontend route is deliberately unguarded per an `App.jsx` comment), but it means **anyone on the internet can trigger a real, up-to-65-minute ML subprocess** with only a 500MB per-request size cap and no rate limiting, CAPTCHA, or per-IP throttling — a real DoS/resource-exhaustion exposure regardless of intent.
- **Upload-validation gap in the main flow**: `POST /interviews/upload-video/{id}` has no extension whitelist, no size limit, no empty-file check — unlike the hardened `/analyze` (Fusion) upload path.
- Frontend stores JWT in `localStorage` (XSS-exposed by design choice), with an axios interceptor that force-redirects to `/login` on any 401.

---

## 22. Error Handling

Strong, typed error handling exists throughout the **real** Fusion/NLP pipeline (typed statuses: `ASR_NO_SPEECH`, `ASR_TOO_SHORT`, `DECOMPOSITION_FAILED`, `NLI_FAILED`, `PreflightError`, per-component `errors[]`, no stack-trace leakage — exceptions serialized as `ClassName: message`, never `traceback.format_exc()`). Partial-results are preserved on failure at every stage.

Gaps: no server-side `track`/`interview_type` enum validation on interview start; generic (non-distinguishing) network-error message in `Processing.jsx` (timeout, 500, and 404 all render identically); no `beforeunload` guard for mid-recording refresh; duplicate-submission protection exists in the normal flow (`already_analyzed` short-circuit) but not framed as a general idempotency pattern elsewhere.

The single largest "error handling" finding is architectural, not a missing try/except: **the main candidate flow's AI modules cannot fail because they never do real work** — there is no "processing failed" state modeled anywhere in `Interview`/`Result` because `random.uniform` never throws.

---

## 23. Tests and Build Results

**Test inventory**: 6 first-party test files total, **zero** covering auth, organizations, memberships, questions, interviews, sessions, recording, answer binding, or history.

| File | Area | Real/Mock | Result |
|---|---|---|---|
| `backend/tests/test_fusion_integration.py` | Fusion response shaping | Pure unit, no mocks needed | 4 passed |
| `InterviewIQ_AI/fusion/test_confidence.py` | Audio confidence + fusion math | Real synthetic-WAV signal processing | 10 passed |
| `InterviewIQ_AI/fusion/test_fusion.py` | Fusion orchestration/error paths | Mix real + `unittest.mock` for failure injection | 5 passed |
| `InterviewIQ_AI/vision/test_visual_behavioral_confidence.py` | Vision scoring math | Pure numpy unit tests | 12 passed |
| `InterviewIQ_AI/vision/test_vision.py` | CLI smoke driver, not pytest | 0 collectible | N/A — collection error due to a `torch`/`torchvision` version mismatch in the venv (environment failure, not a source bug) |
| `.../test_real_nlp_pipeline.py` | Real, paid-API NLP driver | Not pytest | Skipped — calls paid Groq API, out of audit scope |

**Total: 31/31 pytest tests passed, 0 failed.** All ~65 first-party Python source files across backend/fusion/vision/audio/NLP compiled cleanly (`py_compile`).

**Frontend build**: `npm run build` → success, 2533 modules, 7.70s, one advisory warning (911KB main chunk > 500KB threshold). No broken imports, no missing env values beyond the one documented `VITE_API_BASE_URL`. `vite.config.js` dev proxy and `.env.local`/`.env.example` agree on backend port 8000 — no mismatch. No lint script is configured.

**Old-label search**: no occurrences of "Technical Score" (exact case), "Candidate Confidence", or `question_answer_match` (as a literal frontend string) found anywhere in `frontend/src`. "Vocal Confidence" label in `FusionTest.jsx:266` correctly matches its backing field. Frontend consistently consumes the backend's cleaned/renamed field names, not raw internal keys.

---

## 24. Deployment Readiness

**Classification: Local demo ready (Docker path) / Development ready (native `.bat` path, HTTP only). Not staging or production ready.**

Blockers, with evidence:
1. **Nginx has no `client_max_body_size`** (defaults to nginx's 1MB), directly conflicting with the app's own 500MB upload allowance (`FUSION_MAX_UPLOAD_BYTES`) — video uploads would be silently rejected by the reverse proxy in the Docker/production topology.
2. Two unauthenticated, unthrottled, compute-heavy routes (`/api/interviews/analyze*`) reachable from an unguarded frontend route — no rate limiting anywhere in the stack (no `slowapi`, no nginx `limit_req`).
3. Self-signed, `localhost`-only TLS certificate generated at Docker build time, no ACME/renewal story.
4. No restart policies on any Docker service; health checks exist only for `db` (backend exposes `/health` but nothing references it in compose).
5. No structured logging framework anywhere in `backend/app` (only default `uvicorn`/traceback output).
6. No backup strategy, no media retention/TTL policy — uploaded videos and Fusion artifacts accumulate indefinitely.
7. `frontend/Dockerfile` runs the Vite **dev server** in the container (`npm run dev`), not a production build.
8. Migrations are not auto-applied in the Docker path — a fresh `db` volume requires a manual `alembic upgrade head` or the backend fails fast on boot.
9. Secrets are handled correctly via `.env` (git-ignored, hard startup failure if missing) — this is one part of the deployment story that is genuinely solid — but a **second, undocumented secret source** exists (`InterviewIQ_AI/nlp/.../  .env` for `GROQ_API_KEY`), outside the documented `.env`/`.env.example` convention, and currently empty on disk.

---

## 25. Feature Status Matrix

| # | Feature | Status | Evidence | Runtime Connection | Test Evidence | Blocking Issue | Recommended Next Action |
|---|---|---|---|---|---|---|---|
| 1 | Registration | Verified | `auth.py:15-36` | Connected | None | — | Add tests |
| 2 | Login | Verified | `auth.py:39-55` | Connected | None | — | Add tests |
| 3 | Authentication | Verified | `jwt_handler.py`, `permissions.py` | Connected | None | 2 unauth'd interview routes | Guard `/interviews/analyze*` or explicitly document/rate-limit |
| 4 | Candidate dashboard | Partial | `Dashboard.jsx` (student, real) vs `CandidateDashboard.jsx` (stub) | Connected (student only) | None | `candidate` role dead-ends | Decide: merge roles or build candidate flow |
| 5 | Track selection | Verified (client-only) | `TechnicalTrackSelection.jsx` | Connected | None | — | — |
| 6 | Interview type selection | Verified (client-only) | `InterviewTypeSelection.jsx` | Connected | None | — | — |
| 7 | Question-count selection | Missing | — | — | None | No UI/backend concept exists | Build it (Phase target) |
| 8 | Question bank | Partial | §11 | Connected (global only) | None | No is_active/org/reference fields | Add reference linkage, tests |
| 9 | Random question selection | Missing | `questions.py:24-31`, deterministic `ORDER BY id` | Connected but not random | None | No randomization anywhere | Implement `ORDER BY random()` or `random.sample` |
| 10 | Ordered question sequence | Missing (server-side) | §6/§7 | Client-state only | None | No persistence | Add session/sequence table |
| 11 | Multi-question session | Contradictory | §5 | Displays multiple Qs, records one blob | None | No per-question segmentation | Core of next phase |
| 12 | One-question-at-a-time UI | Verified | `InterviewRoom.jsx` | Connected | None | Cosmetic timer, no preview/retry | Minor polish |
| 13 | Camera recording | Verified | `InterviewRoom.jsx:48-90` | Connected | None | — | — |
| 14 | Microphone recording | Verified | same | Connected | None | — | — |
| 15 | Next-question segmentation | Missing | §8 | Not connected | None | `goNext()` does no media work | Core of next phase |
| 16 | Question-answer structural binding | Missing | §9 | Not connected | None | No `question_id` ever sent | Core of next phase |
| 17 | Semantic answer relevance | Missing (as calibrated classifier) | §10 | Indirect only, via NLI neutrality | Real-model driver only | Pre-calibration thresholds | Calibrate or accept as-is with disclaimer |
| 18 | ASR | Verified (fusion-test only) | faster-whisper | Connected (fusion-test) | Real-model driver | Not reachable from normal flow | Wire into main flow |
| 19 | Claim decomposition | Verified but currently dead | Groq LLM, empty API key on disk | Connected (fusion-test), non-functional as shipped | Real-model driver | Missing `GROQ_API_KEY` | Configure secret |
| 20 | BGE-M3 retrieval | Verified, with a latent bug | top-k=10, `use_fp16` bug for >10-chunk docs | Connected (fusion-test) | Real-model driver | CPU crash risk | Fix `use_fp16=False` |
| 21 | NLI | Partial (base model only) | LoRA adapter trained but unused | Connected (fusion-test), zero-shot only | Probe scripts, not wired to prod call | Adapter never loaded | Wire `adapter_path` into `run_nlp_json.py` |
| 22 | Precision | Verified | `aggregation.py`/`metrics.py` | Connected (fusion-test) | Indirectly via real driver | Uncalibrated thresholds | Calibration pass |
| 23 | Coverage | Verified | same | Connected (fusion-test) | same | same | same |
| 24 | Answer Content Score | Verified (fusion-test) / Contradictory (main flow shows unrelated mock) | §12,§18 | Split | Partial | Main flow shows fake `nlp_score` instead | Replace main-flow mock |
| 25 | Audio emotion classification | Verified (fusion-test only) | Wav2Vec2-XLSR+BiLSTM, BAVED | Connected (fusion-test) | None dedicated | Not reachable from normal flow | Wire into main flow |
| 26 | Audio model confidence | Verified, uncalibrated | `audio_module.py:293-306` | Connected (fusion-test) | None | Uncalibrated softmax | Calibrate or label clearly |
| 27 | Candidate-facing audio score | Contradictory | §15 | Split — real heuristic (fusion-test) vs random (main) | `test_confidence.py` (fusion-test only) | Main flow is 100% fake | Replace main-flow mock |
| 28 | Audio validity | Verified (fusion-test) | `audio_confidence.py:110-113` | Connected (fusion-test) | `test_confidence.py` | — | — |
| 29 | Vision classification | Verified (fusion-test only) | Swin-T/LoRA/TCN, RAVDESS | Connected (fusion-test) | None dedicated | Not reachable from normal flow | Wire into main flow |
| 30 | Visual behavioral score | Verified, exact formula match | §16 | Connected (fusion-test) | `test_visual_behavioral_confidence.py` | Main flow shows unrelated mock | Replace main-flow mock |
| 31 | Visual reliability | Verified | `visual_behavioral_confidence.py:222-233` | Connected (fusion-test) | same | — | — |
| 32 | Visual evidence gate | Verified, exact threshold match | min 3 windows, 0.60 face ratio | Connected (fusion-test) | same | — | — |
| 33 | Late Fusion | Contradictory | §17 | Two disconnected formulas live | `test_confidence.py` (Impl A only) | Impl B (main flow) unrelated to Impl A | Unify or clearly separate |
| 34 | Dynamic weight redistribution | Verified (Impl A only) | `confidence_fusion.py:19-58` | Connected (fusion-test) | `test_confidence.py` | — | — |
| 35 | Final candidate report | Partial | §18 | Connected, DB-backed, but shows only mock fields | None | Missing all real-AI fields | Extend schema + UI |
| 36 | Interview history | Partial | §20 | Connected, DB-backed | None | No pagination/org scope | Add pagination |
| 37 | Database persistence | Contradictory | §19 | Normal-flow persists fake data; fusion-test persists nothing | None | Real AI results never persisted | Add fusion-test persistence |
| 38 | Organization management | Verified | §4 | Connected | None | — | — |
| 39 | Phase 2C membership management | Partial | §4 | Connected | **None** | Zero test coverage; guard duplicated 3x | Write tests, refactor guard |
| 40 | Frontend build | Verified | §23 | — | Build succeeded | Large main chunk (911KB) | Code-split |
| 41 | Automated tests | Partial | §23 | — | 31/31 passing, near-zero coverage breadth | Huge coverage gap | Write auth/org/interview tests |
| 42 | Docker deployment | Verified, dev-grade | §2/§24 | Connected | None | Dev server in prod container, no auto-migrate | Harden for staging |
| 43 | Production readiness | Missing | §24 | — | — | 9 blockers listed | See §24 |

---

## 26. GUI–Implementation Mismatches

**A. Visible in GUI, not backed by real logic**
- Candidate dashboard's four "Coming Soon" tiles (`CandidateDashboard.jsx`) — no backend exists for any of them.
- Question-count selector implied by the audit brief's expected journey — no such control exists in the UI at all.

**B. Visible in GUI, backed only by mock values**
- `Report.jsx`'s Vision/Audio/NLP scores, emotion, transcript, WPM, pause/filler counts — all `random.*`.
- `History.jsx` list summaries — same underlying mock data.

**C. Implemented in backend, not connected to normal frontend workflow**
- The entire real AI stack (`InterviewIQ_AI/vision`, `InterviewIQ_AI/audio`, `InterviewIQ_AI/nlp`, `InterviewIQ_AI/fusion`) — reachable only via `/fusion-test`.
- The real 0.60/0.40 Delivery Confidence fusion — same isolation.

**D. Implemented and tested but not persisted**
- Everything the Fusion pipeline produces (`technical_score`, precision, coverage, confidence fields, `used_modalities`-equivalent, limitations) — exists only as an HTTP response + disk JSON, never a DB row.

**E. Labels that don't match their mathematical meaning**
- `Report.jsx`'s "Audio Score" is presented as real delivery performance; it is a `random.uniform` value.
- `Report.jsx`'s null-score radar plotting as literal `0` misrepresents "no evidence" as "zero performance" (contrast with the Fusion pipeline's correct "Not available" handling).
- No mislabeling found *within* the Fusion/`FusionTest.jsx` path itself — its labels (Answer Content Score, Vocal Confidence, Delivery Confidence, Model Confidence) all correctly match their backing fields.

**F. Old/superseded terminology still visible**
- None of "Technical Score" (exact case), "Candidate Confidence", or literal `question_answer_match` strings were found anywhere in `frontend/src` — this migration already appears complete. The only near-hit is one internal constant string in `FusionTest.jsx:15` using the lowercase phrase "technical score" in explanatory prose, not as a UI label, and it does not contradict the actual displayed label ("Answer Content Score").

---

## 27. Top Blockers

Ranked by dependency and impact:

1. **The main candidate product's AI is entirely fake.** Nothing else matters until this is addressed — `backend/app/ai_modules/*.py` must be replaced by real calls into `InterviewIQ_AI/*`. Files: `backend/app/ai_modules/{vision,audio,nlp,fusion_engine}.py`, `backend/app/routers/interviews.py:241-290`. Acceptance: `Report.jsx` displays scores traceable to real model inference on the actual uploaded media, with test coverage proving no `random` call remains in the hot path.
2. **No multi-question session/answer-segmentation data model.** Blocks (1) from being meaningful for anything beyond a single question. Files: `backend/app/models/{interview,result}.py`, new `InterviewSession`/`AnswerSegment`-equivalent tables, `backend/alembic/versions/`. Acceptance: DB supports N answers per interview, each bound to a `question_id` and a discrete media segment with start/end timestamps.
3. **No question-answer structural binding in the normal flow at all.** Depends on #2. Files: `InterviewRoom.jsx`, `interviews.py`. Acceptance: every persisted answer segment carries the question ID that was active when it was recorded, validated server-side against the session's question list.
4. **Real AI results are never persisted (fusion-test path).** Blocks any real report/history from ever showing real data. Files: `interviews.py:_execute_fusion`, needs a `db: Session` dependency and `Result`-equivalent write. Acceptance: a `/fusion-test`-equivalent authenticated flow writes a queryable, history-visible result row.
5. **Two unauthenticated, unthrottled, 65-minute-capable ML endpoints.** Real production risk independent of the others. Files: `interviews.py:133-193`. Acceptance: auth + rate limiting, or explicit removal/gating of the public demo path before any non-local deployment.
6. **LoRA NLI adapter trained but never loaded; Groq API key empty on disk.** The "Answer Content Score" pipeline is currently non-functional as shipped even on the real path. Files: `runners/run_nlp_json.py`, `.env` at `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/`. Acceptance: adapter path wired in, key configured, `test_real_nlp_pipeline.py` run successfully end-to-end.
7. **Zero automated test coverage for Phase 2C, auth, questions, interviews, history.** Everything above will regress silently without it. Acceptance: a test suite per area exercising success/invalid-state/forbidden-access.
8. **Nginx 1MB body limit vs. app's 500MB allowance.** Blocks any real video upload once behind the reverse proxy. Files: `nginx/nginx.conf`. Acceptance: `client_max_body_size` set consistent with `FUSION_MAX_UPLOAD_BYTES`.
9. **Fusion weight/threshold values are all self-labeled "pre-calibration"/"experimental."** Not a hard blocker to shipping a v1, but a correctness/trust risk if presented as validated. Acceptance: either run a calibration pass or keep the existing "experimental" disclaimers visible in the UI (currently they are, on `/fusion-test`; they would need to carry over to any production report page).

---

## 28. Recommended Next Phase

### PHASE 3 — Real Multi-Question Session with Bound, Persisted AI Results

**Objective:** Close the two largest verified gaps in dependency order — (a) a real session/segmentation data model, and (b) routing the already-real AI pipeline through it — so that a logged-in `student` produces a persisted, history-visible report built from actual model inference on actual per-question recordings, replacing `backend/app/ai_modules/*` mocks.

**Included scope:**
- New/extended data model: session-level question sequence (ordered, persisted at session start), per-question `AnswerSegment` (question_id, media path, start/end timestamps, transcript, processing status, failure reason).
- `InterviewRoom.jsx`: per-question `MediaRecorder` start/stop bound to the active question, upload-and-confirm before advancing (or reliable background upload with segment IDs), question-count selector.
- Backend: new routes to create a session with a persisted question sequence, upload a segment bound to a question ID, and trigger the **real** Fusion pipeline (`InterviewIQ_AI/fusion/fusion_pipeline.py`) per segment (or per full session, per design decision) instead of `backend/app/ai_modules/*`.
- Persist the real Fusion pipeline's output fields (technical/precision/coverage, audio/vision confidence + validity, Delivery Confidence, limitations, failure reasons) to new `Result`-equivalent columns/tables.
- Authenticate and rate-limit the real-model invocation route(s); retire or clearly firewall the standalone unauthenticated `/fusion-test` demo path from any non-local deployment.
- Configure the currently-empty `GROQ_API_KEY` and wire the trained LoRA NLI adapter into `run_nlp_json.py`.

**Explicitly excluded from this phase:** semantic-relevance calibration/threshold tuning (§10, keep current pre-calibration heuristic with disclaimers), question-bank reference-material CRUD/versioning UI (§11 gap, separate phase), organization-scoped question banks, Phase 2C guard refactor into a single shared function (do alongside its own test-writing effort), production-hardening items in §24 not directly blocking this phase (logging framework, backup strategy, TLS/ACME).

**Required backend changes:** new ORM models + Alembic migration for session/segment persistence; new/modified routes in `interviews.py` for segment upload and real-pipeline invocation; auth guard added to the real-pipeline route; `Result` schema extended for the real Fusion fields; `GROQ_API_KEY` configuration.

**Required frontend changes:** `InterviewRoom.jsx` per-question recording lifecycle; `Report.jsx` extended to render the real Fusion fields (Answer Content Score, Delivery Confidence, audio/vision validity, limitations) instead of the mocked fields; question-count selector.

**Required database changes:** new tables/columns for ordered question sequence, per-question answer segments, and the full real-Fusion result shape (see §19's "never persisted" list).

**Required tests:** end-to-end test recording→segment→real-pipeline→persisted-result→report/history round trip; unit tests for the new session/segment model; regression tests confirming the old mock path is fully removed (no `random` call remains in the scoring hot path).

**Definition of done:** a `student` can complete a real multi-question interview where each answer is bound to its question, the real AI models score it, the result is persisted, and it is visible (with correct field semantics — no 0%-for-missing, no mislabeled scores) in both the immediate report and interview history.

**Risks:** the real pipeline's per-component timeout (up to 65 minutes total) is unsuitable for a synchronous request-response UX at scale — this phase should introduce at least a polling/async job status pattern rather than blocking the HTTP request; the BGE-M3 `use_fp16` crash bug (§16) must be fixed before this phase, since expanding real usage will surface it.

**Execution order:** (1) data model + migration → (2) backend segment-upload + real-pipeline route + auth/rate-limit → (3) frontend recording-lifecycle rewrite → (4) Report/History field wiring → (5) tests → (6) retire/firewall the old mock path and the standalone `/fusion-test` demo route.

---

## 29. Exact Implementation Plan

1. Design & migrate: `InterviewSession` (or extend `Interview`) with a persisted ordered question list; `AnswerSegment` table (`session_id`, `question_id`, `sequence_index`, `media_path`, `start_ts`, `end_ts`, `transcript`, `status`, `failure_reason`); extend `Result`-equivalent for the full real-Fusion field set from §19.
2. Backend: `POST /interviews/{id}/segments` (upload one answer bound to a question ID, validated against the session's stored sequence); background/async job to invoke `InterviewIQ_AI/fusion/fusion_pipeline.py` per segment; persist its output; add auth + rate limiting to this path.
3. Fix the BGE-M3 `use_fp16=False` bug (`InterviewIQ_AI/nlp/.../retrieval/chunk_cap.py`); configure `GROQ_API_KEY`; wire `adapter_path` into `runners/run_nlp_json.py`.
4. Frontend: rewrite `InterviewRoom.jsx`'s recording lifecycle to start/stop `MediaRecorder` per question, upload-and-confirm each segment, add a question-count selector; extend `Processing.jsx` to poll job status instead of a single blocking call.
5. Frontend: extend `Report.jsx` to render the real Fusion result shape with correct semantics (Answer Content Score separate from Delivery, "Not available" vs. 0%, diagnostic vs. performance labeling).
6. Retire `backend/app/ai_modules/*.py` mocks and `fusion_engine.fuse_scores`; remove or firewall the unauthenticated standalone `/fusion-test` route from non-local deployments.
7. Write tests: session/segment model, segment-upload-to-real-pipeline round trip, Report/History rendering of real fields, Phase 2C org/membership suite (parallel workstream, same effort category as §27 item 7).
8. Nginx: raise `client_max_body_size` to match `FUSION_MAX_UPLOAD_BYTES`.

---

## Final Conclusion

**A. Last fully verified milestone:** Phase 2C organization membership management — implementation-complete and correctly enforced, but with zero automated test coverage (§4).

**B. Highest working end-to-end workflow currently available:** Login → Dashboard → multi-question-looking Interview Room → mocked analysis → persisted (fake) Result → Report → History, entirely on the `student` role. Separately, and disconnected from that: an unauthenticated, single-question, real-AI `/fusion-test` page whose results are never persisted.

**C. Does the normal multi-question candidate workflow work?** It displays multiple questions and records through them, but produces one undifferentiated recording with no per-question binding, and scores everything with `random`-generated numbers — so functionally, **no**, not as a real assessment product.

**D. Does `/fusion-test` use real models?** Yes — verified real ASR, claim decomposition (currently non-functional without a `GROQ_API_KEY`), BGE-M3 retrieval, NLI (base model only, trained LoRA adapter unused), audio emotion classification, and vision behavioral scoring, all subprocess-orchestrated against real checkpoints.

**E. Is the candidate-facing audio score traceable?** In the normal flow, no — it's `random.uniform`. In `/fusion-test`, yes and fully traceable — a documented, deterministic DSP formula (`vocal_confidence_score`) — but it is unrelated to the raw emotion-model confidence value, and neither of the two audited weighted-probability formulas (15/50/100 or 0/50/100) exists anywhere in the repository.

**F. Is Late Fusion connected to the normal workflow?** No. The real 0.60/0.40 Delivery Confidence fusion only runs on `/fusion-test`. The normal workflow uses a different, unrelated 0.35/0.30/0.35 formula over mock inputs.

**G. Are results persisted and accessible through History?** Only the fake results are. The real Fusion pipeline's output is never written to the database.

**H. Top five blockers:** (1) main product's AI is entirely mocked; (2) no multi-question session/answer-segmentation data model; (3) no question-answer structural binding in the normal flow; (4) real AI results are never persisted; (5) two unauthenticated, unthrottled, up-to-65-minute ML endpoints.

**I. Exact next phase:** PHASE 3 — Real Multi-Question Session with Bound, Persisted AI Results (§28).

---

LAST VERIFIED MILESTONE: Phase 2C organization membership management (implementation-complete, zero test coverage)
CURRENT WORKING DEMO: Multi-question Interview Room → mocked Report/History (student role) + separate unauthenticated single-question real-AI /fusion-test page (not persisted, not linked to the product)
NORMAL CANDIDATE WORKFLOW: PARTIAL
REAL AI EXECUTION: PARTIAL
CANDIDATE AUDIO SCORE: CONTRADICTORY
LATE FUSION STATUS: PARTIAL
REPORT PERSISTENCE: PARTIAL
INTERVIEW HISTORY: PARTIAL
NEXT REQUIRED PHASE: PHASE 3 — Real Multi-Question Session with Bound, Persisted AI Results
OVERALL STATUS: PARTIALLY COMPLETE
