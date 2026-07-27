"""
D74 LLM-based Claim Decomposition client.

Calls an external LLM (Groq, OpenAI-compatible chat completions API) to
perform answer normalization + claim decomposition, per decisions.md D74.
This REPLACES the archived AraT5 fine-tuning approach (Phase 8, superseded
-- see archive/phase8_arat5_superseded/).

Per D86's amendment (decisions.md), Groq is the sole decomposition
provider -- this module previously called OpenRouter; that code has been
fully removed (not kept dormant), not made a fallback. A fresh D77-style
sanity gate run against the current GROQ_MODEL is required before this is
trusted for any real O9/Coverage/pipeline work (see D87).

The hard constraints (no correction of answer correctness, Latin-script
term preservation, atomicity, self-containment) are enforced by the
system prompt in system_prompt.md -- this module does NOT itself verify
that the model honored them. See scripts/llm_decomposition_sanity_gate.py
for that check. Do not trust this module's output in any production path
until that gate has been run and passed for the current GROQ_MODEL.

NOT wired into configs/decomposition.yaml or any production pipeline yet.
"""

from __future__ import annotations

import os
import random
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from interview_iq.decomposition.types import DecompositionResult

_MODULE_DIR = Path(__file__).resolve().parent
_SYSTEM_PROMPT_PATH = _MODULE_DIR / "system_prompt.md"
_REPO_ROOT_ENV = _MODULE_DIR.parents[3] / ".env"

load_dotenv(_REPO_ROOT_ENV if _REPO_ROOT_ENV.exists() else None)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
# Verify the current model id at https://console.groq.com/docs/models
# before setting this -- do not assume a stale id still works.
GROQ_MODEL = os.environ.get("GROQ_MODEL")

_MAX_RETRIES = 5
_BASE_BACKOFF_SECONDS = 2.0
_MAX_BACKOFF_SECONDS = 60.0

NO_EXTRACTABLE_CLAIMS_SENTINEL = "NO_EXTRACTABLE_CLAIMS"


class LLMDecompositionError(RuntimeError):
    """Raised when the LLM call fails after all retries, or returns an
    unparseable response. Callers must not silently swallow this -- a
    failed decomposition must not be treated as an empty/valid result."""


def _load_system_prompt() -> str:
    if not _SYSTEM_PROMPT_PATH.exists():
        raise LLMDecompositionError(f"system_prompt.md not found at {_SYSTEM_PROMPT_PATH}")
    return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _parse_numbered_claims(raw_output: str) -> list[str]:
    """Parse the model's plain numbered-list output per the OUTPUT FORMAT
    section of system_prompt.md."""
    stripped = raw_output.strip()
    if stripped == NO_EXTRACTABLE_CLAIMS_SENTINEL:
        return []

    claims: list[str] = []
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(".", 1)
        if len(parts) == 2 and parts[0].strip().isdigit():
            claim_text = parts[1].strip()
            if claim_text:
                claims.append(claim_text)
        else:
            raise LLMDecompositionError(
                f"Output line does not match 'N. claim' format: {line!r}\n"
                f"Full raw output:\n{raw_output}"
            )
    return claims


def _sleep_before_retry(attempt: int, retry_after: str | None) -> None:
    if retry_after is not None:
        try:
            delay = float(retry_after)
        except ValueError:
            delay = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
    else:
        delay = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
    delay = min(delay, _MAX_BACKOFF_SECONDS)
    delay += random.uniform(0, 1)
    time.sleep(delay)


def _call_groq(asr_text: str, system_prompt: str) -> str:
    if not GROQ_API_KEY:
        raise LLMDecompositionError(
            "GROQ_API_KEY is not set. Add it to a .env file at the "
            "repo root (see .env.example)."
        )
    if not GROQ_MODEL:
        raise LLMDecompositionError(
            "GROQ_MODEL is not set. Verify the current model id at "
            "https://console.groq.com/docs/models and add it to .env "
            "-- do not assume a stale id still works."
        )

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": asr_text},
        ],
        "temperature": 0,
    }

    last_error: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
        except requests.RequestException as exc:
            last_error = exc
            if attempt < _MAX_RETRIES:
                _sleep_before_retry(attempt, retry_after=None)
                continue
            raise LLMDecompositionError(
                f"Groq call failed after {_MAX_RETRIES} attempts (connection error): {exc}"
            ) from exc

        if response.status_code == 200:
            data = response.json()
            try:
                message = data["choices"][0]["message"]
                content = message["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise LLMDecompositionError(f"Unexpected response shape from Groq: {data!r}") from exc
            if content is None:
                finish_reason = data["choices"][0].get("finish_reason")
                raise LLMDecompositionError(
                    f"Groq returned null message content (finish_reason={finish_reason!r}): {data!r}"
                )
            return content

        # 429 is confirmed retryable per Groq's docs (console.groq.com/docs/rate-limits).
        # The >=500 half of this condition is a carried-over assumption from the
        # former OpenRouter code, NOT independently confirmed in Groq's docs --
        # standard REST convention makes it a reasonable default, but it is not
        # verified the way the 429 case is (see d86_groq_migration_scope.md).
        if response.status_code == 429 or response.status_code >= 500:
            retry_after = response.headers.get("Retry-After")
            last_error = LLMDecompositionError(
                f"Groq returned {response.status_code}: {response.text[:500]}"
            )
            if attempt < _MAX_RETRIES:
                _sleep_before_retry(attempt, retry_after=retry_after)
                continue
            raise last_error

        raise LLMDecompositionError(f"Groq returned {response.status_code}: {response.text[:500]}")

    raise LLMDecompositionError(f"Groq call failed after {_MAX_RETRIES} attempts: {last_error}")


def decompose_via_llm(asr_text: str) -> DecompositionResult:
    """
    Convert a raw ASR transcript of a candidate's spoken answer into a
    DecompositionResult, via an external LLM API call.

    Per D74, this function does NOT validate that the LLM honored the
    hard constraints in system_prompt.md. That validation is the job of
    the separate D74 mandatory sanity gate
    (scripts/llm_decomposition_sanity_gate.py, not yet implemented).
    """
    if not asr_text or not asr_text.strip():
        raise LLMDecompositionError("asr_text is empty -- nothing to decompose.")

    system_prompt = _load_system_prompt()
    raw_output = _call_groq(asr_text, system_prompt)
    claims = _parse_numbered_claims(raw_output)

    return DecompositionResult(source_text=asr_text, claims=claims)
