# Phase 3A — Real Per-Question Audio Analysis with Persistence

**Repository:** `D:\InterviewIQ-final` | **Branch:** `main` | **Date:** 2026-08-05

---

## Recovery Summary (this session resumed a prior, interrupted run)

Before making any change, the working tree was inspected (`git status --short`, `git diff --stat`, `git diff --name-only`) and every previously-created Phase 3A file was read in full rather than trusting the task-state summary. Confirmed state at resume time:

| Area | State found | Action taken |
|---|---|---|
| ORM models (`InterviewQuestion`, `AnswerSegment`, `AudioAnalysis`) | Complete, correct, registered in `models/__init__.py` | Kept as-is, no duplicates created |
| Alembic migration `b4d8f2a917c3_add_interview_questions_answer_.py` | Complete, single file, `down_revision='7c6f3df24fbd'` (then-current head) | Verified, applied, not recreated |
| Schemas (`interview_question.py`, `answer_segment.py`, `audio_analysis.py`, extended `interview.py`) | Complete | Kept as-is |
| `backend/app/services/audio_analysis_service.py` | Complete (345 lines), imports the real `InterviewIQ_AI/audio` code correctly | Kept as-is |
| `backend/app/config.py` | New Phase 3A settings/paths present | Kept as-is |
| `backend/app/routers/interviews.py` | **Imports and constants added, but `start_interview` was still the old (pre-Phase-3A) version and none of the new endpoints existed yet** — this is exactly what the task-state summary said was "in progress" | Completed: rewrote `start_interview`, added `GET /{id}/questions`, `POST /{id}/segments`, `POST /{id}/process-audio`, `GET /{id}/processing-status`, `POST /{id}/segments/{segment_id}/retry-audio`, extended `GET /report/{id}` |
| `backend/app/routers/dashboard.py` | Untouched (pre-Phase-3A) | Added persisted audio summary to `/dashboard/history` |
| Frontend (`InterviewRoom.jsx`, `Processing.jsx`, `Report.jsx`, `History.jsx`) | Untouched (pre-Phase-3A, single-blob recording) | Rewritten per §5–8 below |
| `backend/tests/` | Only the pre-existing `test_fusion_integration.py` | Added `conftest.py` + 5 new test files (42 tests total) |
| `backend/interviewiq_test.db` | Modified (already at Alembic head `7c6f3df24fbd`, i.e. **not yet migrated** to the new schema) | Migration applied and round-trip verified (upgrade → downgrade → upgrade) against this database before any test wrote to it |

No file was reverted, reset, or overwritten. The pre-existing, unrelated modifications under `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/` and `frontend/src/pages/FusionTest.jsx` (present before Phase 3A began) were left untouched — confirmed byte-for-byte identical (`git diff --stat` line counts match exactly) at the end of this session.

---

## A. Summary

The normal student interview flow (`Login → Dashboard → Interview Room → Processing → Report → History`) now records **one distinct answer segment per question**, deterministically binds each segment to its question, and runs **real local audio analysis** (the existing Wav2Vec2-XLSR+BiLSTM emotion classifier and the existing DSP vocal-delivery heuristic under `InterviewIQ_AI/audio/`) on every valid segment — replacing the `app/ai_modules/audio_module.py` random-score mock in this flow. Results are persisted and shown in Report and History without ever re-running inference. NLP, Vision, and Late Fusion are unchanged.

---

## B. Architecture Implemented

```
InterviewRoom.jsx                         Processing.jsx
  │ POST /interviews/start-interview         │ POST /interviews/{id}/process-audio
  │  → persists InterviewQuestion[]          │ GET  /interviews/{id}/processing-status (poll)
  │ per question: fresh MediaRecorder        │
  │ POST /interviews/{id}/segments  ────────►│  (BackgroundTasks) _process_segment_audio_task
  │  (interview_question_id, question_id,    │    → app.services.audio_analysis_service
  │   sequence_index, started_at, ended_at)  │       .analyze_answer_segment_audio(media_path)
  │                                          │         ├─ ffmpeg extraction (mono 16kHz WAV)
  ▼                                          │         ├─ InterviewIQ_AI/audio/audio_confidence.py
Report.jsx / History.jsx                    │         │    ::calculate_audio_confidence  (real, in-process)
  │ GET /interviews/report/{id}              │         └─ InterviewIQ_AI/audio/audio_emotion_package
  │ GET /dashboard/history                   │              via fusion.adapters.base.run_json_component
  │  (reads persisted rows only)             │              (real, dedicated subprocess/venv)
```

---

## C. Database Changes

One Alembic migration: `backend/alembic/versions/b4d8f2a917c3_add_interview_questions_answer_.py` (`down_revision='7c6f3df24fbd'`).

**New tables:**
- `interview_questions` — server-persisted, ordered question sequence per interview. `unique(interview_id, sequence_index)`, `unique(interview_id, question_id)`, `CHECK(sequence_index >= 0)`. `question_id` FK `ON DELETE SET NULL` (a later hard-deleted `Question` never cascades away interview history); `question_text`/`difficulty` are snapshotted at creation.
- `answer_segments` — one recorded answer, bound to `interview_question_id` (authoritative) plus denormalized `question_id`/`sequence_index` (integrity/query convenience). `unique(interview_id, interview_question_id)`. `upload_status` ∈ {pending, uploaded, failed}; `processing_status` ∈ {pending, processing, completed, partial, failed, insufficient_evidence}; `failure_code`/`failure_message`.
- `audio_analyses` — 1:1 with `answer_segments` (`unique(answer_segment_id)`). Exact fields returned by the real implementation only (no invented metrics) — see §G.

**Altered table:** `interviews` gains one nullable column, `recording_completed_at`.

**No existing table is altered destructively; no existing row is touched.** `downgrade()` drops only what this migration added.

**Verified against the real local dev/test database** (`backend/interviewiq_test.db`, `DATABASE_URL=sqlite:///./interviewiq_test.db`), which had genuine existing data (1 real user, 31 seeded questions) before this phase:
```
alembic current        → 7c6f3df24fbd   (before)
alembic upgrade head    → b4d8f2a917c3   (new tables/column created, confirmed via PRAGMA table_info)
alembic downgrade 7c6f3df24fbd → tables dropped; users (1 row) and questions (31 rows) intact
alembic upgrade head    → b4d8f2a917c3   (re-applied cleanly)
```

---

## D. API Endpoints Added or Modified

| Method | Path | Change |
|---|---|---|
| POST | `/interviews/start-interview` | **Modified.** Now persists the ordered `InterviewQuestion` sequence (existing eligible-question lookup — filter by type/track, order by id, first 5 — unchanged, not redesigned) and returns it (`InterviewStartResponse`). Raises 422 if no eligible questions. |
| GET | `/interviews/{interview_id}/questions` | **New.** Re-fetches the persisted sequence (e.g. after refresh). Ownership-enforced. |
| POST | `/interviews/{interview_id}/segments` | **New.** Uploads and structurally binds one answer. Validates ownership, `recording_completed_at` not yet set, `interview_question_id` belongs to the interview, optional client-echoed `question_id`/`sequence_index` match the persisted row, extension/size/non-empty, safe server-generated path. Rejects a second finalized upload for the same question (409) but allows re-upload over a `pending`/`failed` row. |
| POST | `/interviews/{interview_id}/process-audio` | **New.** Idempotently marks recording complete and queues every `uploaded`+`pending` segment via `BackgroundTasks`. |
| GET | `/interviews/{interview_id}/processing-status` | **New.** Per-segment status + `all_terminal`. Polled by `Processing.jsx`. |
| POST | `/interviews/{interview_id}/segments/{segment_id}/retry-audio` | **New.** Re-queues one `uploaded` segment. |
| GET | `/interviews/report/{interview_id}` | **Modified (backward compatible).** Adds `questions[]` (per-question text/difficulty/segment/audio_analysis) and `audio_summary`, alongside the unchanged legacy `interview`/`result` shape. |
| GET | `/dashboard/history` | **Modified (backward compatible).** Adds `audio_summary` per interview, alongside all previously-existing fields. |

Unmodified and still present (legacy, backward-compatible, not called by the new frontend flow): `GET /interviews/analysis-questions`, `POST /interviews/analyze`, `POST /interviews/upload-video/{interview_id}`, `POST /interviews/analyze/{interview_id}`.

---

## E. Frontend Changes

- **`InterviewRoom.jsx`** — rewritten. Calls `start-interview` on mount (not `GET /questions`); one fresh `MediaRecorder` per question; Next stops the recorder, uploads the segment, waits for a `201`, then advances (button disabled + spinner while `uploading`, preventing double submission). On upload failure: stays on the same question, keeps the recorded Blob in state, shows the error and a "Retry Upload" button that resubmits the same Blob. After the last answer: navigates to `/interview/processing` with only `{ interviewId }` (no Blob).
- **`Processing.jsx`** — rewritten. Calls `process-audio` once, then polls `processing-status` every 2s, rendering a real per-segment status list (pending/analyzing/completed/partial/insufficient evidence/failed) with a per-segment Retry button on failure; navigates to `/report/:id` only once `all_terminal` is true. No timer-simulated fake progress.
- **`Report.jsx`** — extended. Legacy Vision/Audio/NLP score cards and radar chart now render **only if a legacy `Result` row actually exists** (fixes the pre-existing "`?? 0`" issue where a missing score silently plotted as zero — a Phase-3A interview with no legacy `Result` row no longer shows a misleading all-zero radar). New per-question audio panel: emotion classification + probabilities, Audio Model Confidence (labeled *"Diagnostic model confidence; not candidate confidence."*), Vocal Delivery Score (labeled *"Experimental vocal-delivery indicator."*), Speaking Rate/Pause Control/Volume Stability/Speech Continuity, evidence status, failure reason. Every missing value renders **"Not available"**, never `0%`. Interview-level audio summary card. Legacy/no-segment interviews show an honest "not available" note.
- **`History.jsx`** — extended with a per-item "Vocal Delivery: X.X (n/total answers)" line when `audio_summary.available`, and an honest "not available" note otherwise; legacy module bars only render when legacy scores exist.

No new frontend framework/library was introduced.

---

## F. Real Audio Execution Path

`backend/app/services/audio_analysis_service.py::analyze_answer_segment_audio(media_path)`:

1. Validates the media file is present/non-empty (`AUDIO_FILE_EMPTY` otherwise).
2. Extracts mono 16kHz PCM WAV via `ffmpeg` (mirrors `InterviewIQ_AI/fusion/fusion_pipeline.py::extract_audio`'s exact arguments; own timeout, no `shell=True`) → `AUDIO_EXTRACTION_FAILED`/`AUDIO_TIMEOUT` on failure.
3. Calls the real `InterviewIQ_AI/audio/audio_confidence.py::calculate_audio_confidence` **in-process** (pure numpy/wave, imported directly — `InterviewIQ_AI` is added to `sys.path` once, giving `audio.*`/`fusion.*` as namespace packages; `InterviewIQ_AI/fusion` itself is deliberately never added to `sys.path`, to avoid a long-lived process ever shadowing a bare `config`/`adapters` import with that directory's same-named files). If the audio is genuinely empty/silent (detected via the function's own "empty" sentinel — no sub-scores at all, not just a missing composite), returns `insufficient_evidence` immediately and **never invokes the model subprocess**.
4. Otherwise calls the real emotion classifier out-of-process, in its own dedicated `.venv_audio` environment, reusing the **existing** `fusion.adapters.base.run_json_component` subprocess/JSON-validation helper (explicit timeout, captured stdout/stderr, structured JSON, schema-validated, no `shell=True`) rather than re-implementing it — only the ~3-line env/command setup that `fusion.adapters.audio_adapter.run_audio` also does is duplicated, to avoid adding `InterviewIQ_AI/fusion` to `sys.path`.
5. Normalizes both results into one typed `AudioAnalysisOutcome`, with `model_confidence` (emotion classifier, diagnostic) always reported independently from `vocal_delivery_score` (DSP heuristic) — never derived from one another.

**Verified with real execution** (not just unit tests): a manual end-to-end run against the real emotion model (`InterviewIQ_AI/audio/audio_emotion_package/test_sample.wav`) returned `emotion_label="Low Emotion"`, `model_confidence=0.4706` — matching the package's own `expected_output.json` (0.4718) — with `vocal_delivery_score=None` and a correct, honest `failure_message` explaining the missing transcript, while `pause_control_score`/`volume_stability_score`/`speech_continuity_score` were real computed values. The optional gated test (`tests/test_real_audio_smoke.py`, `RUN_REAL_AUDIO_TESTS=1`) reproduces this and passed in 25.8s.

**Never invokes** NLP, Vision, Groq, BGE-M3, NLI, or Late Fusion — confirmed both by code inspection and by a source-level regression test (`test_mock_audio_removed_from_hot_path.py`).

---

## G. Exact Fields Persisted

`AudioAnalysis` — every field is either a real value from the two wrapped implementations, or honest metadata about the run; nothing is invented:

- **Emotion classifier:** `emotion_label`, `emotion_probabilities` (JSON), `model_confidence`, `model_confidence_calibrated` (always `False` — no calibration exists anywhere for this model).
- **Vocal delivery:** `vocal_delivery_score`, `speaking_rate_wpm`, `speaking_rate_score`, `pause_ratio`, `pause_control_score`, `volume_stability_score`, `speech_continuity_score`, `sufficient_evidence`, `failure_reason`.
- **Metadata:** `model_identifier` (constant string naming the real module/architecture/dataset), `model_version` (read live from the package's own `config.json`, e.g. `"09:Cosine_Warmup10pct"` — `None` if unavailable, never guessed), `sample_rate_hz`, `duration_seconds`, `raw_diagnostic` (JSON, persisted but not returned by the API), `analyzed_at`.

`AnswerSegment` — `media_path` (never exposed via the API), `media_type`, `file_size_bytes`, `started_at`, `ended_at`, `upload_status`, `processing_status`, `failure_code`, `failure_message`, timestamps.

`InterviewQuestion` — `question_id`, `sequence_index`, `question_text` (snapshot), `difficulty` (snapshot).

`Interview.recording_completed_at` — set once by `process-audio`.

---

## H. Failure Handling

Stable `AudioFailureCode` values: `AUDIO_FILE_EMPTY`, `AUDIO_FORMAT_UNSUPPORTED`, `AUDIO_EXTRACTION_FAILED`, `AUDIO_MODEL_UNAVAILABLE`, `AUDIO_INFERENCE_FAILED`, `AUDIO_INSUFFICIENT_EVIDENCE`, `AUDIO_TIMEOUT`. Every failure/insufficient-evidence path persists a code + human-readable message; the frontend renders "Not available" plus the reason, never `0%` and never a random/mock value. If the background task itself raises unexpectedly, the segment is explicitly set to `failed` with `AUDIO_INFERENCE_FAILED` rather than being left stuck in `processing` silently.

---

## I. Security and Ownership Enforcement

All six new/modified endpoints require `Depends(get_current_user)` and re-check `Interview.user_id == current_user.id` (generic 404 on mismatch, consistent with the codebase's existing privacy-preserving pattern — confirmed for both a nonexistent interview and another user's real interview). `interview_question_id`/`question_id`/`sequence_index` are always re-validated server-side against the persisted `InterviewQuestion` row — client-supplied values are never trusted blindly. Upload path is server-generated (`uuid4().hex` + validated extension), written under `backend/storage/answer_segments/{interview_id}/`, with a resolved-parent-directory check against path traversal. No internal filesystem path is ever returned in an API response (`AnswerSegmentResponse` excludes `media_path`).

---

## J. Tests Added

`backend/tests/conftest.py` — isolated temp SQLite database (never the real configured `DATABASE_URL`), an in-process ASGI test client (`httpx.AsyncClient` + `httpx.ASGITransport`, since this repo's installed `httpx` 0.28 is not wire-compatible with Starlette's `TestClient` under the pinned FastAPI/Starlette versions — no dependency was upgraded to work around this), and shared fixtures/helpers.

| File | Tests | Covers |
|---|---|---|
| `test_interview_questions.py` | 5 | Persisted order, ownership, no-eligible-questions 422, DB-level duplicate-`sequence_index` rejection |
| `test_answer_segments.py` | 11 | Auth, valid upload (no path leak), wrong interview, wrong question, question_id/sequence_index mismatch, unsupported extension, empty upload, duplicate finalized segment, upload rejected after recording marked complete |
| `test_audio_analysis_service.py` | 11 | Missing/empty file, silent audio → insufficient_evidence (model never called), successful normalized output (confidence vs. vocal score independence, real DSP + mocked model boundary), timeout, model-unavailable, malformed JSON, incomplete schema, extraction failure/timeout, no-random-values source check |
| `test_report_and_history_persistence.py` | 7 | Correct-segment persistence, failed-analysis persistence (no `AudioAnalysis` row), report/history never re-run inference, aggregation ignores missing scores, no-valid-scores → unavailable, legacy (no-segment) interview handled honestly |
| `test_mock_audio_removed_from_hot_path.py` | 3 | New flow never calls the legacy mock; source-level check confining `run_audio(` to the legacy endpoint only; no `random.*` call usage in Phase 3A source files |
| `test_real_audio_smoke.py` | 1 (opt-in) | Real model + real DSP, gated by `RUN_REAL_AUDIO_TESTS=1`, skipped by default |

**Total: 42 tests, 41 passed + 1 correctly skipped by default, 0 failed.** No paid API called. The default suite never loads the large audio model (verified: the 41 default-run tests complete in ~10s; the model only loads in the explicitly opted-in smoke test).

---

## K. Commands Run and Results

```
alembic current / upgrade head / downgrade 7c6f3df24fbd / upgrade head   → clean, data-preserving round trip
python -m py_compile <all touched .py files>                             → OK
python -c "from app.main import app; ...list routes..."                  → all 6 new/modified routes wired, 0 warnings
pytest tests/ -q                                                          → 41 passed, 1 skipped in ~10s
RUN_REAL_AUDIO_TESTS=1 pytest tests/test_real_audio_smoke.py -v          → 1 passed in 25.80s
npm run build (frontend)                                                  → success, 2533 modules, ~6-14s,
                                                                              1 pre-existing chunk-size advisory (unrelated)
Manual live smoke test (uvicorn on 127.0.0.1:8010 + real HTTP requests): full
  register → start-interview → binding-validation negatives (404/422/415/422/409)
  → ownership (404) → real process-audio (72.4s) → report/history         → all passed
```

---

## L. Files Changed

**New:**
```
backend/alembic/versions/b4d8f2a917c3_add_interview_questions_answer_.py
backend/app/models/{interview_question,answer_segment,audio_analysis}.py
backend/app/schemas/{interview_question,answer_segment,audio_analysis}.py
backend/app/services/__init__.py
backend/app/services/audio_analysis_service.py
backend/tests/conftest.py
backend/tests/test_interview_questions.py
backend/tests/test_answer_segments.py
backend/tests/test_audio_analysis_service.py
backend/tests/test_report_and_history_persistence.py
backend/tests/test_mock_audio_removed_from_hot_path.py
backend/tests/test_real_audio_smoke.py
```

**Modified:**
```
backend/app/config.py                    (+ Phase 3A settings/paths)
backend/app/models/__init__.py           (+ new model imports)
backend/app/models/interview.py          (+ recording_completed_at, + relationships)
backend/app/routers/interviews.py        (+ 5 new endpoints, start-interview + report rewritten)
backend/app/routers/dashboard.py         (+ audio_summary on /history)
backend/app/schemas/interview.py         (+ InterviewStartResponse)
frontend/src/pages/InterviewRoom.jsx     (rewritten — per-question recording)
frontend/src/pages/Processing.jsx        (rewritten — real status polling)
frontend/src/pages/Report.jsx            (rewritten — real audio panel, radar-zero-fill fix)
frontend/src/pages/History.jsx           (+ audio summary line)
README_LOCAL_SETUP.md                    (+ Phase 3A section, updated stale "no real audio" claim)
```

**Untouched** (pre-existing, unrelated changes present before this session; verified byte-identical): `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/**`, `frontend/src/pages/FusionTest.jsx`. Phase 2C behavior (`organizations.py`, `permissions.py`, membership endpoints/tests) was not touched. NLP, Vision, and Late Fusion source code was not touched.

---

## M. Known Limitations

- **`vocal_delivery_score` and `speaking_rate_*` are "Not available" for most/all answers in this phase** — the real formula requires a transcript for speaking-rate scoring, and ASR/NLP is out of scope for Phase 3A. This is the existing formula's honest behavior given a genuinely missing input, not a bug; documented in code, the API, and the UI.
- **`model_confidence` is uncalibrated** — max-softmax probability only, no temperature/Platt/isotonic scaling exists for this model anywhere in the codebase.
- **Background processing is FastAPI `BackgroundTasks`, not a durable queue.** A backend restart mid-analysis leaves a segment in `processing`; recovery requires the explicit retry endpoint. Documented in code and README.
- **The legacy whole-interview mock path is not removed**, only bypassed — `app/ai_modules/audio_module.py` and `POST /interviews/analyze/{interview_id}` still exist for backward compatibility and are confirmed (by test) to be unreachable from the new flow.
- **Real audio processing is slow per answer** (~25–75s observed for the emotion-model subprocess, dominated by venv/model load), which is why it runs as a background task with client-side polling rather than inline in the upload request.
- Two throwaway users/one interview were created in `backend/interviewiq_test.db` during manual verification (`phase3a-smoketest@example.com` etc.) — left in place per the instruction not to reset/delete existing database content.

## N. Deferred Work

- **NLP** (ASR/claim decomposition/BGE-M3/NLI/Answer Content Score) — entirely out of scope for this phase, unchanged.
- **Vision** — entirely out of scope for this phase, unchanged.
- **Late Fusion / Delivery Confidence** — not calculated anywhere in this phase, as instructed.
- **Scientific calibration** of model confidence or the vocal-delivery formula — not attempted; both remain explicitly labeled experimental/diagnostic.
- **A durable, production-grade job queue** (e.g. Celery) — not introduced; `BackgroundTasks` is used and its limitations are documented.

---

PHASE STATUS: COMPLETE
NORMAL FLOW USES REAL AUDIO: YES
PER-QUESTION AUDIO BINDING: VERIFIED
REAL AUDIO PERSISTENCE: VERIFIED
MOCK AUDIO REMOVED FROM HOT PATH: YES
REPORT INTEGRATION: VERIFIED
HISTORY INTEGRATION: VERIFIED
TEST STATUS: 41 passed, 1 skipped (opt-in real-model smoke test), 0 failed
FRONTEND BUILD: PASSED
NEXT RECOMMENDED PHASE: Phase 3B — Real Per-Question Vision Analysis with Persistence (extend the same per-question segment/processing architecture to the existing real Vision model), followed by Phase 3C (NLP/Answer Content Score) and only then a Late Fusion phase once all three modalities are real and persisted per-question.
