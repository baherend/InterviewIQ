"""Shared pytest fixtures for the backend test suite.

Uses a dedicated, isolated SQLite database file (never the real local dev
database configured in the project's .env) and an in-process ASGI test
client (httpx.AsyncClient + httpx.ASGITransport) rather than Starlette's
TestClient — this repo's installed httpx (0.28) is not wire-compatible
with the TestClient shipped by the pinned Starlette/FastAPI versions
(Client.__init__() no longer accepts `app=`), so tests talk to the app
directly over an ASGI transport instead. No dependency versions are
changed to work around this.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import pytest

# Must run before any `app.*` import anywhere in the test session:
# pydantic-settings reads DATABASE_URL from the environment at import
# time, and tests must never run against the real configured database.
_TEST_DB_PATH = Path(tempfile.gettempdir()) / f"interviewiq_pytest_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"

import httpx  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app import models  # noqa: E402  (imports every model so Base.metadata is complete)
from app.main import app  # noqa: E402

Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_database():
    yield
    engine.dispose()
    _TEST_DB_PATH.unlink(missing_ok=True)


@pytest.fixture()
def db_session():
    """Direct DB access for test setup/assertions, independent of any
    request's own session.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _run(coro):
    return asyncio.run(coro)


class ApiClient:
    """Small sync-friendly wrapper around an in-process ASGI client, so
    test functions can stay plain `def test_...():` without needing
    pytest-asyncio.
    """

    def get(self, path, headers=None, params=None):
        return _run(self._request("GET", path, headers=headers, params=params))

    def post(self, path, json=None, data=None, files=None, headers=None):
        return _run(self._request("POST", path, json=json, data=data, files=files, headers=headers))

    async def _request(self, method, path, **kwargs):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.request(method, path, **kwargs)


@pytest.fixture()
def client():
    return ApiClient()


def register_and_login(client: ApiClient, email: Optional[str] = None) -> tuple[dict, int]:
    """Registers a fresh throwaway user (POST /auth/register already logs
    the new user in, returning a token) and returns (auth_headers, user_id).
    """
    email = email or f"pytest-{uuid.uuid4().hex}@example.com"
    password = "PytestPhase3A!12345"
    r = client.post("/api/auth/register", json={"name": "Pytest User", "email": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    token = body["access_token"]
    user_id = body["user"]["id"]
    return {"Authorization": f"Bearer {token}"}, user_id


def unique_interview_type(prefix: str = "Technical") -> str:
    """`interview_type` is a free-text field (no fixed enum, see
    app/schemas/question.py) — tests use a fresh, unique value per
    scenario so that Question rows seeded by one test can never leak
    into another test's eligible-question count. The DB is intentionally
    shared/session-scoped across tests (matching this repo's existing,
    lightweight test style) rather than reset per test, so this is the
    isolation mechanism, not a DB reset.
    """
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def seed_questions(db_session, *, interview_type=None, track="Pytest Track", count=1):
    from app.models.question import Question

    if interview_type is None:
        interview_type = unique_interview_type()

    created = []
    for i in range(count):
        q = Question(
            question=f"Pytest question {i}",
            interview_type=interview_type,
            track=track,
            difficulty="Medium",
        )
        db_session.add(q)
        created.append(q)
    db_session.commit()
    for q in created:
        db_session.refresh(q)
    return created, interview_type


def make_wav_bytes(*, duration_seconds: float = 1.0, sample_rate: int = 16000, amplitude: float = 0.0) -> bytes:
    """A tiny synthetic mono 16-bit PCM WAV, in-memory. amplitude=0.0
    produces genuine silence (used for insufficient-evidence tests);
    a positive amplitude produces a real, analyzable tone.
    """
    import io
    import math
    import struct
    import wave

    n_frames = int(duration_seconds * sample_rate)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_frames):
            value = int(amplitude * 32767 * math.sin(2 * math.pi * 220 * i / sample_rate))
            frames += struct.pack("<h", value)
        wav_file.writeframes(bytes(frames))
    return buffer.getvalue()
