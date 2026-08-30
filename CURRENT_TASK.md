# Current Task

- Task ID: `TASK-REPOSITORY-COMPLETENESS-001`
- Status: `CANONICAL_VALIDATED_PUSH_PENDING`
- Checkpoint: `CP-021 — repository completeness repair validated in canonical tree`
- Authorized repositories: investigation work in `D:\InterviewIQ-github-test`, then intentional sync/commit/push from `D:\InterviewIQ-final`
- Read-only evidence repositories: `D:\InterviewIQ-final-1`, `D:\InterviewIQ-defense-test`, and `D:\Interview project`

## Objective

Audit every supplied local copy against GitHub, restore all required source,
repair reproducibility/import/Docker defects, validate the complete stack,
sync only the proven changes to the canonical repository, push `main`, and
prove the pushed state with a brand-new GitHub clone.

## Verified outcome so far

- Canonical and the original GitHub test clone started at the same pushed
  commit, `3f60c683cba4061b2b41f74f6e765bd3d7c22735`.
- No required source/config/test from the three read-only copies is newer or
  missing from GitHub. Their unique files are generated databases, archives,
  experimental material, or ignored model artifacts.
- The Docker backend failure was caused by a backend-only build context that
  omitted `InterviewIQ_AI`, compounded by an image layout incompatible with
  `PROJECT_ROOT`. The repaired image uses the repository root context and
  preserves `/app/backend` plus `/app/InterviewIQ_AI`.
- Fresh-database startup now applies Alembic migrations automatically; the
  empty `backend/alembic/__init__.py` that shadowed the installed Alembic
  package was removed.
- The missing BGE relevance/same-cell NLI behavior documented by existing
  tests, CLI code, memory, and ADR-20260823-005 was restored.
- Windows-only AI interpreter defaults were replaced by platform-native paths
  with explicit overrides.
- Large ignored checkpoints are documented by exact path, byte size, and
  SHA-256. They are not authorized for ordinary Git.

## Verification

- Backend: `71 passed, 1 skipped` (the skip is the opt-in real-model smoke).
- NLP: `24 passed`.
- Fusion: `15 passed`.
- Vision behavioral confidence: `12 passed`.
- Frontend production build: PASS, 2,533 modules; existing chunk-size advisory only.
- Direct source imports: backend, Audio, Vision, Fusion, and NLP PASS.
- Real artifact checks: audio sample inference PASS; Vision checkpoint strict load PASS.
- Full isolated Docker Compose: db/backend/frontend/nginx running; PostgreSQL
  healthy; Alembic `e7a2c4f19b6d (head)`; 31 questions; backend health 200;
  frontend 200; nginx HTTPS 200; protected nginx API 401 as expected.
- Secret signature scan, tracked-env audit, ignore-rule audit, Python
  compileall, and `git diff --check`: PASS.
- Canonical-only context audit: full backend context is 6.15 MB; the built
  image contains 576 KB backend plus 6.1 MB AI source and none of the forbidden
  secret/model/media/database/archive/cache/environment categories.
- Canonical Compose also passed with a native Windows `UPLOAD_DIR` and native
  SQLite `DATABASE_URL` present locally: container storage stayed at
  `/app/storage/uploads`, the backend used PostgreSQL, all nine migrations
  reached head, and 31 questions were seeded.

## Exact next action

Review and stage only the enumerated task files, commit and push `origin/main`
without force, then clone GitHub into a new empty validation directory and
repeat critical clean-clone installation/build/Docker checks.
