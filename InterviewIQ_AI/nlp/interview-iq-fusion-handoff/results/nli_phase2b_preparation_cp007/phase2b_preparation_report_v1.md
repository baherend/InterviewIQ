# CP-007 Phase 2B LoRA Preparation

- Checkpoint: `CP-007 — Phase 2B Preparation Complete`
- Scope: corpus/training/evaluation design and leakage controls only.
- Result: `PASS` for preparation; corpus authoring, model loading, training, checkpoint creation, evaluation, and promotion were not performed.
- Official evaluation baseline remains CP-005; CP-006 remains a checkpoint-control result with no remediation winner.

## Why LoRA remains selected

CP-006 improved aggregate accuracy and contradiction F1 but did not reduce the critical false-contradiction rate, did not improve DA-017 beyond `2/5`, and introduced an entailment-to-neutral regression. A targeted adapter keeps the pinned current base model and existing serving shape while concentrating capacity on InterviewIQ Arabic/domain failure families. The repository already has an optional `adapter_path` injection point and a fail-loud PEFT loader, so experiment and rollback blast radius are lower than checkpoint replacement or a semantic cascade.

## Corpus contract

- Target: 600 reviewed examples from at least 40 non-CP-005 source question IDs.
- Target split: approximately 480 train / 120 internal dev, strictly by complete question ID; at least eight dev question IDs.
- Labels: 200 entailment, 200 contradiction, 200 neutral.
- Language styles: 150 MSA, 150 Egyptian, 180 Arabic/English code-switch, 60 transliteration variants, 60 English diagnostics.
- At least 360 examples must contain technical terminology; at least 120 must be code-switched technical cases.
- Difficulties: 180 paraphrase entailments, 20 domain-entailment preservation cases, 110 near-neighbor contradictions, 90 direct contradictions, 120 technical neutrals, and 80 semantically adjacent neutrals.
- Every label requires two independent reviewers and adjudication on disagreement; AI-only labels are rejected.
- No training example has been authored in CP-007.

## Leakage boundary

The future corpus must load the frozen 45-case CP-005 dataset only as an exclusion source after verifying SHA-256 `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18` and `do_not_train=true`.

Hard rejection covers all evaluation case IDs, the ten source question IDs, all DA-017 anchors, conservative-normalized premises, hypotheses, and pairs, duplicate training IDs/pairs, train/dev question overlap, paired-group splitting, mutable/unresolved sources, and any attempt to pass the evaluation dataset as training input. A separate manual semantic-family gate rejects translations, dialect conversions, paraphrases, term substitutions, or other derivatives of an evaluation case that exact normalization cannot detect.

## Existing adapter path and readiness

- Production injection: `src/interview_iq/pipeline.py:evaluate_answer(..., adapter_path=...)`.
- Attachment: `src/interview_iq/evaluation/gold_eval.py:load_adapter`, using `PeftModel.from_pretrained` and verifying non-empty `peft_config`.
- Training orchestration: `src/interview_iq/nli/finetune.py:run_finetune`.
- CLI: `src/interview_iq/cli/run_nli_finetune.py`.
- Evaluation hook: `src/interview_iq/cli/run_nli_eval.py --adapter-path`.
- Existing supported LoRA shape: `r=16`, alpha 32, `query_proj` + `value_proj`, dropout 0.1, no bias, `SEQ_CLS`.

Training is not ready to run unchanged. The configured legacy pilot files are absent; only `DS-014` is excluded; loaders do not enforce the new schema or semantic-family review; base loading is not pinned by immutable revision/hash; training tokenization defaults to 128; and no focused training/preflight tests exist. These are explicit next-phase preparation gates, not silent assumptions.

## Predeclared evaluation gates

- CP-005 accuracy at least `39/45`, macro F1 at least `0.85`, and every class F1 at least `0.80`.
- False contradiction must become `0/15`; false entailment must remain at most `1/15`.
- Neutral must remain at least `14/15` correct with F1 at least `0.80`.
- DA-017 must pass `5/5`; no CP-005 case that the base model got right may newly regress.
- Every supported slice must remain at least 70%; code-switch at least `10/12`, natural-paraphrase entailment at least `6/7`, near-neighbor contradiction at least `4/5`, and direct contradiction at least `3/5`.
- Fresh-process CPU/fp32 latency must be no more than 1.15x the CP-006 baseline (`92.613351 ms/case`), and peak working set no more than 1.10x (`2,301,884,006 bytes`).
- A separate Coverage/scoring regression gate must pass without changing formulas or thresholds.
- Every gate is conjunctive. Passing creates an engineering recommendation only, never automatic promotion.

## Future command flow

1. Author and independently review the 600-case corpus from non-protected source families.
2. Validate/freeze corpus, split, source, policy, model, tokenizer, and one-config hashes.
3. Run focused schema/leakage tests and a tiny synthetic smoke test before real model initialization.
4. After separate training authorization, execute exactly one hardened LoRA run on baseline revision `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c` with max length 256.
5. Select the best epoch using internal dev macro F1 only. CP-005 is never used for training, early stopping, configuration selection, or threshold tuning.
6. Freeze the adapter, then run one CP-005 A/B plus a separate Coverage/scoring regression.
7. Stop and request independent production-promotion authorization.

## Rollback

The adapter remains optional. Experiment rollback is to omit `adapter_path` and reload the pinned base revision; no checkpoint must be deleted. If a future deployment is separately authorized, rollback additionally requires restarting the NLI process and reproducing exact CP-005 baseline parity.

## Exact next step

Await explicit authorization for **Phase 2B Data Authoring only**: create and review the specified 600-case train/dev corpus from at least 40 non-protected question IDs, run the exclusion and quality preflight, freeze its manifests/hashes, then stop before model loading or training.
