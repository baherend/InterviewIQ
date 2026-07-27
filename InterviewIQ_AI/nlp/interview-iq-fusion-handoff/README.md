# Fusion Handoff Manifest — Interview IQ NLP Module

Generated from a read-only repo inspection. `[REPO]` = tracked in this repository, path is real and can be pulled directly. `[LOCAL-UNTRACKED]` = required at runtime but not present in the repo — the fusion colleague must supply/build it locally.

---

## Provider note

- **LLM provider:** Groq (OpenAI-compatible chat completions API). Endpoint defined in `src/interview_iq/decomposition_llm/client.py:43`.
- **Model:** value of the `GROQ_MODEL` env var — currently `"llama-3.3-70b-versatile"` (confirmed in a real run artifact, `results/pipeline_demo/SE-028.json:346`).
- **No OpenRouter/cohere code is live.** Both are historical only, referenced in `decisions.md` and `archive/` (superseded providers/models from earlier decision entries D74–D87). The only OpenRouter references remaining in `src/` are two code comments in `client.py` documenting its removal (`client.py:10`, `client.py:161`).

---

## Claim Decomposition

- `[REPO]` `src/interview_iq/decomposition_llm/client.py`
- `[REPO]` `src/interview_iq/decomposition_llm/system_prompt.md` — Constraint 1 = no fact-correction (never correct/complete/improve the candidate's answer, including numeric errors); Constraint 8 = Arabic-only output register (claim sentences must be simplified-MSA Arabic prose; only individual technical terms stay in Latin script). This is the corrected constraint numbering per the D90 fix (`decisions.md:627`) — D88's original text mislabeled the fact-correction rule as "constraint 8."
- `[REPO]` `src/interview_iq/decomposition/types.py` — note: this is a **different package path** than `decomposition_llm/`. Per D97 (`decisions.md:847`), `src/interview_iq/decomposition/` is a legacy stub package (`NotImplementedError`); the production module is `decomposition_llm/`. Don't confuse the two when wiring in fusion code.
- `[REPO]` `.env.example` — vars: `GROQ_API_KEY`, `GROQ_MODEL`.

---

## BGE-M3 (retrieval / chunk cap)

- `[REPO]` `src/interview_iq/retrieval/chunk_cap.py`
- **Model:** `"BAAI/bge-m3"` (`chunk_cap.py:61`, `configs/retrieval.yaml:9`)
- **Top-k:** `configs/retrieval.yaml:15`, `k=10`, tagged PRE-CALIBRATION DEFAULT — not yet validated (enters Gate G4 calibration).

---

## NLI (mDeBERTa)

- `[REPO]` `src/interview_iq/nli/engine.py`
- **Base model:** `"MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"` (`configs/nli_finetune.yaml:9`)
- `[LOCAL-UNTRACKED]` **LoRA adapter checkpoint** — loaded via a local filesystem path passed to `PeftModel.from_pretrained(...)` (PEFT), **not** kagglehub. No `kagglehub` calls exist anywhere in this repo. The fusion colleague must have the adapter checkpoint files locally on their own machine/environment if they intend to use the adapter arm; the repo does not fetch it automatically.
- **Label mapping:** `{0: entailment, 1: neutral, 2: contradiction}` — `configs/nli_finetune.yaml:57-60`.
- **Thresholds:** `tau=0.5`, `tau_e=0.9`, `alpha=0.0` (`configs/scoring.yaml:10-12`); `k=10` (`configs/retrieval.yaml:15`).
- **Current handoff mode: zero-shot.** Zero-shot is the coded default per **D89** (`decisions.md:593`): `adapter_path` defaults to `None` throughout (`pipeline.evaluate_answer`, `cli/run_scoring.py --adapter-path`, `cli/run_nli_eval.py --adapter-path`), and `cli/run_nli_eval.py`'s `--zero-shot` flag force-overrides even if an adapter path is supplied. This is not a new decision made for this handoff — it reflects D89's already-registered runtime default (adapter demoted to a documented negative result; see Known Issues below for why).

---

## Scoring

- `[REPO]` `src/interview_iq/scoring/metrics.py` — `precision_channel()` (`metrics.py:114`), `coverage_channel()` (`metrics.py:132`), `harmonic_f()` (`metrics.py:142`)
- `[REPO]` `src/interview_iq/scoring/aggregation.py` — `score_claim()` (`aggregation.py:50`), and `compute_scoring_result()` (in `metrics.py`, final `.score` field = `harmonic_f * score_scale`)

---

## Orchestrator

- `[REPO]` `src/interview_iq/pipeline.py` — `evaluate_answer(audio_path, question, reference_chunks, key_points, ...optional kwargs...) -> dict[str, Any]`.
  Confirmed: this is a **superset** of the 4-arg target contract `evaluate_answer(audio_path, question, reference_chunks, key_points) -> dict`. The four required positional params match exactly in name, order, and type-shape; the real signature adds 11 further optional keyword params (`config`, `device_override`, `compute_type_override`, `question_id`, `nli_model`, `nli_tokenizer`, `adapter_path`, `chunk_embedder`, `transcribe_fn`, `decompose_fn`, `batch_size`, `max_length`), all defaulted, so calling it with just the 4-arg contract works unchanged.

---

## ASR

- `[REPO]` `src/interview_iq/asr/engine.py` — `transcribe_audio(audio_path, ...optional kwargs...) -> dict[str, Any]`. The return dict is **Format Spec v1.1 shaped** (fixed field list from `configs/asr.yaml`'s `output.fields`), not a generic dict.
- `[REPO]` `configs/asr.yaml` — checkpoint `large-v3`, language `ar`, device `cpu`, compute_type `int8`.
- **Model:** faster-whisper `large-v3` — downloads to local cache on first use, not a repo file.

---

## Data artifacts

- `[REPO]` `data/refdocs/reference_docs_250_FINAL_v1.json`
- `[REPO]` `data/nli/gold_set_48.json`
- `[REPO]` `results/o9_decomposition_exercises.md`

---

## KNOWN ISSUES (do not omit or soften)

### 1. Pilot audio files are NOT confirmed to match the real-run output artifacts

`data/audio_pilot/` (untracked on disk — `git status` shows `?? data/audio_pilot/`) contains exactly two files: `answer_correct.mp3` and `answer_wrong.mp3`. The real end-to-end `evaluate_answer()` run artifacts that exist in the repo — `results/pipeline_demo/SE-028.json`, `GN-040.json`, and their `_v2` reruns — are for **different question IDs** (`SE-028`, `GN-040`), and there is no filesystem or artifact evidence that these two specific pilot `.mp3` files were the audio inputs behind those runs (their filenames don't correspond, and no manifest/mapping file ties them together). **Do not present the pilot mp3s and the SE-028/GN-040 outputs as a matched sample+expected-output pair** — they are not confirmed to correspond to each other.

### 2. D88's three failure modes — current status per decisions.md (reporting exactly what's recorded, not inferring)

D88 (`decisions.md:574`) recorded three verified failure modes from the first real end-to-end run (SE-028, GN-040): **F1** (LLM silently corrected a deliberately-wrong numeric fact, violating the error-preservation constraint), **F2** (the LoRA adapter degrades the Precision channel on real claims), **F3** (base-model NLI failures independent of the adapter, including a false-entailment VERIFIED against the wrong chunk).

Per the decision log, these have **not** all been closed:

- **F1 — still open, and has resurfaced as a moving target across three distinct violation classes.** D90/D92 hardened the prompt and gate-tested it (9/9 PASS) for the original *numeric* silent-correction case (`decisions.md:645-651`). But D93's field revalidation on real audio (`SE-028_v2.json`, `GN-040_v2.json`) found a **new** violation class in D94 (`decisions.md:691-710`): an *editorialized correction with embedded meta-commentary* ("... وليس 16 بت كما ذكر، ولكن في النص الأصلي ذكر 16 بيت"), explicitly called out as "a NEW violation class distinct from D88's silent correction." A further prompt hardening (D95, `decisions.md:714`) was gate-tested (D96, `decisions.md:745`) and again **FAILed**: SG-10 exposed a **third** silent-correction class — *ordering/logical facts* (an inverted TDD step order was silently corrected back to the right order). D96's own diagnosis (`decisions.md:763`): *"Error preservation fails by category, not by instance: numeric (D88) → editorial (D94) → ordering (D96). Remedy must be a generalized anti-knowledge-injection constraint, not another per-class patch."* As of the latest logged entry (D97, `decisions.md:838`, status **PRE-REGISTERED**, git log shows component (a) — the deterministic transliteration layer — implemented but "not closed"), a generalized fix plus gate rerun (to be registered as **D98**) is still pending. **F1 is open.**

- **F2 — resolved, but by policy change, not by a fix to the adapter itself.** D89 (`decisions.md:593`) made zero-shot the runtime default for both channels specifically *because of* F2 (plus the earlier D82/D83 Coverage finding). The adapter itself was never repaired; it was removed from the runtime path and reclassified as "a documented negative result / ablation." Section 4's Open Items table marks the related item **RESOLVED (D88+D89)** (`decisions.md:792`). Treat F2 as closed-by-avoidance, not closed-by-correction.

- **F3 — explicitly still open.** D93 states outright: *"F3 remains an open follow-up item, out of scope for this session"* (`decisions.md:673`). D94's title itself reads "...F3 field-confirmed" (`decisions.md:691`) — the D93 rerun produced a concrete new field case (SE-028 claim 0 vs. chunk SE028-C01, false CONTRADICTED at `max_c=0.994`, `decisions.md:697`). D95 explicitly reconfirms scope: *"F3 (NLI false contradiction, D93/D94) is untouched by this decision and remains open"* (`decisions.md:739`). No later entry through D97 records F3 as closed. **F3 is open.**

**Net: of D88's three failure modes, only F2 is closed (via a design/policy decision, not a bugfix); F1 and F3 remain open as of the latest decisions.md entry (D97, PRE-REGISTERED).** G4 threshold calibration is explicitly blocked pending resolution of these items (`decisions.md:710`).
