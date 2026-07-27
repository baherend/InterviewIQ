"""
test_real_nlp_pipeline.py — minimal local test driver for a real, end-to-end
run of the Interview IQ NLP pipeline (ASR -> question matching -> evaluate_answer).

Two phases, run as separate CLI subcommands so semantic question-matching
stays a human/agent judgment call rather than a hardcoded heuristic:

  1. `transcribe_and_match` — runs the REAL ASR (faster-whisper) on each pilot
     audio file, then embeds the transcript against every reference document's
     chunks with the REAL BGE-M3 embedder and writes ranked candidates to
     results/local_nlp_test/match_candidates_<audio>.json for inspection.

  2. `evaluate --correct-qid <QID|none> --wrong-qid <QID|none>` — given the
     question_id chosen for each pilot audio (or "none" for no reliable
     match), loads that document's exact chunks/key_points from the reference
     JSON and calls the real evaluate_answer() end-to-end, saving the full
     result dict and a test_summary.json.

Nothing here is mocked: real transcribe_audio, real BgeM3Embedder, real
evaluate_answer (real Whisper ASR, real Groq decomposition, real mDeBERTa
NLI, real BGE-M3 retrieval).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from interview_iq.asr.engine import ASRError, transcribe_audio  # noqa: E402
from interview_iq.audio.segmentation import AudioSegmentationError  # noqa: E402
from interview_iq.config import Config  # noqa: E402
from interview_iq.pipeline import evaluate_answer  # noqa: E402
from interview_iq.refdocs.loader import load_reference_docs  # noqa: E402

REFDOCS_PATH = REPO_ROOT / "data" / "refdocs" / "reference_docs_250_FINAL_v1.json"
RESULTS_DIR = REPO_ROOT / "results" / "local_nlp_test"
# evaluate_answer/transcribe_audio's documented contract is mono 16kHz WAV
# (pipeline.py: "already-extracted answer-segment audio file ... per
# configs/asr.yaml" -- video/audio extraction to that format is explicitly a
# CLI-level concern, not evaluate_answer's job). The pilot files are MP3s
# that torchaudio/Silero VAD cannot decode on Windows (no sox/ffmpeg backend
# registered), so this test pre-converts them with ffmpeg -- a preprocessing
# step, not a pipeline modification. See AUDIO_CONVERTED_DIR.
AUDIO_DIR = RESULTS_DIR / "audio_converted"
AUDIO_FILES = ["answer_correct.wav", "answer_wrong.wav"]


class _MatchingEmbedder:
    """Real BGE-M3 embedder used ONLY by this test script's own
    question-matching helper (not part of the production pipeline).

    Deliberately not reusing interview_iq.retrieval.chunk_cap.BgeM3Embedder:
    that class constructs BGEM3FlagModel without use_fp16=False, which
    crashes on CPU with `RuntimeError: "LayerNormKernelImpl" not implemented
    for 'Half'` (fp16 LayerNorm has no CPU kernel in this torch build). That
    is a real latent bug in the production retrieval module -- it does not
    surface in the actual evaluate_answer() pipeline because every
    reference-doc chunk count here is <=12 <= k=10's neighborhood (max 12,
    per data invariants), so select_top_k_chunks's n_chunks<=k short-circuit
    means chunk_cap never actually constructs an embedder for this dataset.
    Per the task constraint against editing production retrieval logic, the
    fix (use_fp16=False) is applied here, in test-only code, instead of in
    chunk_cap.py.
    """

    def __init__(self, model_name: str, device: str = "cpu") -> None:
        from FlagEmbedding import BGEM3FlagModel

        self._model = BGEM3FlagModel(model_name, use_fp16=False, device=device)

    def encode(self, texts: list[str]) -> list[list[float]]:
        out = self._model.encode(list(texts))
        return [list(vec) for vec in out["dense_vecs"]]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def cmd_transcribe_and_match(args: argparse.Namespace) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = Config()
    refdocs = load_reference_docs(REFDOCS_PATH)

    print("[phase1] Loading BGE-M3 embedder for question-matching (real model, may download) ...")
    embedder = _MatchingEmbedder(model_name=cfg.embedding_model, device="cpu")

    # Embed all chunks across all 250 documents once.
    all_chunks = []
    for doc in refdocs.documents:
        for chunk in doc.chunks:
            all_chunks.append((doc, chunk))
    print(f"[phase1] Embedding {len(all_chunks)} reference chunks across {len(refdocs.documents)} documents ...")
    chunk_texts = [c.text for _, c in all_chunks]
    chunk_vecs = embedder.encode(chunk_texts)
    print("[phase1] Chunk embedding complete.")

    for audio_name in AUDIO_FILES:
        audio_path = AUDIO_DIR / audio_name
        print(f"\n[phase1] === Transcribing {audio_name} (real faster-whisper) ===")
        try:
            asr_record = transcribe_audio(str(audio_path), config=cfg, question_id=None)
        except (ASRError, AudioSegmentationError) as exc:
            out = {
                "audio": audio_name,
                "asr_status": "ERROR",
                "error": f"{type(exc).__name__}: {exc}",
            }
            out_path = RESULTS_DIR / f"match_candidates_{Path(audio_name).stem}.json"
            out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[phase1] ASR FAILED for {audio_name}: {type(exc).__name__}: {exc}")
            continue

        transcript = asr_record.get("normalized_transcript") or ""
        print(f"[phase1] ASR status: {asr_record['status']}")
        print(f"[phase1] Transcript length: {len(transcript)} chars")

        candidates = []
        if transcript.strip():
            t_vec = embedder.encode([transcript])[0]
            scored = []
            for (doc, chunk), vec in zip(all_chunks, chunk_vecs):
                sim = _cosine(t_vec, vec)
                scored.append((sim, doc, chunk))
            scored.sort(key=lambda x: x[0], reverse=True)
            for sim, doc, chunk in scored[:15]:
                candidates.append(
                    {
                        "similarity": round(sim, 4),
                        "question_id": doc.question_id,
                        "question": doc.question,
                        "best_chunk_id": chunk.chunk_id,
                        "best_chunk_text": chunk.text,
                    }
                )

        out = {
            "audio": audio_name,
            "asr_status": asr_record["status"],
            "raw_transcript": asr_record.get("raw_transcript"),
            "normalized_transcript": transcript,
            "avg_logprob": asr_record.get("avg_logprob"),
            "top_candidates": candidates,
        }
        out_path = RESULTS_DIR / f"match_candidates_{Path(audio_name).stem}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[phase1] Wrote candidates to {out_path}")


def _select_document(refdocs, question_id: str | None):
    if question_id is None:
        return None
    doc = refdocs.get_document(question_id)
    if doc is None:
        raise SystemExit(f"question_id {question_id!r} not found in reference docs")
    return doc


def cmd_evaluate(args: argparse.Namespace) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = Config()
    refdocs = load_reference_docs(REFDOCS_PATH)

    selections = {
        "answer_correct.wav": {
            "question_id": None if args.correct_qid.lower() == "none" else args.correct_qid,
            "reason": args.correct_reason,
            "reliable": args.correct_qid.lower() != "none",
        },
        "answer_wrong.wav": {
            "question_id": None if args.wrong_qid.lower() == "none" else args.wrong_qid,
            "reason": args.wrong_reason,
            "reliable": args.wrong_qid.lower() != "none",
        },
    }

    summary = []

    for audio_name, sel in selections.items():
        entry = {
            "audio": audio_name,
            "transcript": None,
            "selected_question_id": sel["question_id"],
            "selected_question": None,
            "reason": sel["reason"],
            "match_reliable": sel["reliable"],
            "result_file": None,
            "execution_status": None,
            "error": None,
        }

        candidates_path = RESULTS_DIR / f"match_candidates_{Path(audio_name).stem}.json"
        transcript = None
        if candidates_path.exists():
            cand_data = json.loads(candidates_path.read_text(encoding="utf-8"))
            transcript = cand_data.get("normalized_transcript")
        entry["transcript"] = transcript

        if sel["question_id"] is None:
            entry["execution_status"] = "no_reliable_question_match"
            summary.append(entry)
            print(f"[phase2] {audio_name}: no reliable question match -- skipping evaluate_answer.")
            continue

        doc = _select_document(refdocs, sel["question_id"])
        entry["selected_question"] = doc.question

        audio_path = AUDIO_DIR / audio_name
        print(f"\n[phase2] === Running real evaluate_answer for {audio_name} against {doc.question_id} ===")
        try:
            result = evaluate_answer(
                str(audio_path),
                doc.question,
                doc.chunks,
                doc.key_points,
                config=cfg,
                question_id=doc.question_id,
            )
            result_path = RESULTS_DIR / f"{Path(audio_name).stem}_result.json"
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            entry["result_file"] = str(result_path.relative_to(REPO_ROOT))
            entry["execution_status"] = result["status"]
            entry["error"] = result.get("error")
            print(f"[phase2] status={result['status']} score={result.get('score')} -> {result_path}")
        except Exception as exc:  # noqa: BLE001 -- test driver must capture, not crash
            entry["execution_status"] = "EXCEPTION"
            entry["error"] = f"{type(exc).__name__}: {exc}"
            print(f"[phase2] EXCEPTION for {audio_name}: {type(exc).__name__}: {exc}")

        summary.append(entry)

    summary_path = RESULTS_DIR / "test_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[phase2] Wrote summary to {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("transcribe_and_match")

    p_eval = sub.add_parser("evaluate")
    p_eval.add_argument("--correct-qid", required=True, help="question_id for answer_correct.mp3, or 'none'")
    p_eval.add_argument("--wrong-qid", required=True, help="question_id for answer_wrong.mp3, or 'none'")
    p_eval.add_argument("--correct-reason", default="", help="reason for the correct-audio match decision")
    p_eval.add_argument("--wrong-reason", default="", help="reason for the wrong-audio match decision")

    args = parser.parse_args()
    if args.cmd == "transcribe_and_match":
        cmd_transcribe_and_match(args)
    elif args.cmd == "evaluate":
        cmd_evaluate(args)


if __name__ == "__main__":
    main()
