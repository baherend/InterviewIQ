"""
decomposition/ — Claim Decomposition (Knowledge Distillation) module.

⛔ Phase 8 — Gate G2 is closed (decisions.md D51/D52) and Q6 (AraT5 vs
mT5-base) is now resolved: AraT5-base was selected on
linguistic-specialization grounds (decisions.md D54;
`configs/decomposition.yaml`'s `model.selected` now reads
"UBC-NLP/AraT5-base"). See decisions.md and PROJECT_EXECUTION_PLAN.md
§Phase 8. This package still currently ships interface stubs only —
Q6 being resolved is not the start of the real Phase 8 implementation:

  - types.py            data containers (model-agnostic)
  - dataset_builder.py  KD corpus builder — raises NotImplementedError
  - trainer.py          model trainer — raises NotImplementedError
  - inference.py        decomposition inference — raises NotImplementedError

No function in this package loads a tokenizer, checkpoint, or model name
yet — that is deferred to the actual Phase 8 implementation session.
"""

from __future__ import annotations
