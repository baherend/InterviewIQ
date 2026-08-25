# CP-009 Baseline vs LoRA Evaluation

- Acceptance: `FAIL`.
- Decision scope: evaluation recommendation only; adapter is not promoted.

| Metric | CP-005 baseline | LoRA adapter |
|---|---:|---:|
| Accuracy | 0.8222222222222222 | 0.8222222222222222 |
| Macro F1 | 0.8186307519640854 | 0.8206391309839584 |
| Entailment F1 | 0.8666666666666667 | 0.846153846153846 |
| Neutral F1 | 0.8484848484848485 | 0.8571428571428571 |
| Contradiction F1 | 0.7407407407407408 | 0.7586206896551724 |
| False contradictions | 2 | 3 |
| False entailments | 1 | 0 |

## Acceptance gates

- FAIL `overall_correct`: `37`; target `>=39/45`.
- FAIL `accuracy`: `0.8222222222222222`; target `>=0.85`.
- FAIL `macro_f1`: `0.8206391309839584`; target `>=0.85`.
- FAIL `minimum_class_f1`: `0.7586206896551724`; target `>=0.8`.
- FAIL `false_contradiction_count`: `3`; target `<=0`.
- PASS `false_entailment_count`: `0`; target `<=1`.
- PASS `neutral_correct`: `15`; target `>=14/15`.
- PASS `neutral_f1`: `0.8571428571428571`; target `>=0.8`.
- FAIL `DA017_anchors`: `1`; target `=5/5`.
- FAIL `baseline_correct_regressions`: `['NLI-EVAL-037', 'NLI-EVAL-041']`; target `<=0`.
- FAIL `minimum_supported_slice_accuracy`: `0.4`; target `>=0.7`.
- PASS `latency_ms_per_case`: `82.38579777777777`; target `<=92.613351`.
- PASS `peak_working_set_bytes`: `2221363200`; target `<=2301884006`.
- PASS `adapter_attachment`: `True`; target `true`.

## Recommendation

Do not promote the adapter because one or more predeclared gates failed. Preserve it as experiment evidence only.
