# Phase 4 baseline (preserved for Phase 5)

IDEA CONTRIBUTOR: BHAVESHBHAI SOLANKI · FOUNDER & PROJECT DEVELOPER: DIVYESH BAMBHANIYA

| Item | Value |
|---|---|
| Branch | `arena/b93bc898-granth-ai` |
| Phase 4 commit | `48bf73e2346374a1a0081c0c95e6aa021bc6ab2a` (in history, equal to the remote branch head when Phase 5 started; working tree clean) |
| `main` | `554448768127672b406171a757e62a76e82b9d46`, not touched |
| Phase 4 engine | `extractive-1.3`, kept in git history at the commit above |
| Phase 4 frozen set | `benchmarks/phase4/frozen_test.json`, sha256 `1e8bd54796ba4f83ed98fafc17b7f9f44c69a7c6626849344633c5fd5ecbde4d` – not edited in Phase 5 |
| Phase 4 frozen result | `benchmarks/results/phase4_frozen_run1.json`, sha256 `9d627dae34e6b06d5d85f2cabef7861e1ff092fbad262a449eaa9c5bbfdfd408` – not edited in Phase 5 |

## Reproduction (automatically tested, 2026-11-13)

`bash benchmarks/phase5/reproduce_phase4_baseline.sh` checks out the Phase 4 commit into a separate directory, runs the unchanged
frozen set on the unchanged engine and compares with the recorded result.

| | Handled correctly | Wrong | Correct refusal | Incorrect refusal | Conflict detected |
|---|---|---|---|---|---|
| Recorded in Phase 4 | 55 / 70 | 4 | 19 | 11 | 0 / 1 |
| Re-run in Phase 5 | 55 / 70 | 4 | 19 | 11 | 0 / 1 |

Failures list, per-category table and metrics: identical. Re-run output: `benchmarks/results/phase5/phase4_baseline_rerun.json`.

Limitation: the Phase 4 result file stores only the failing rows, so passing rows are compared through the per-category counts,
not answer by answer. Phase 5 result files store every row.

All Phase 5 question sets live in `benchmarks/phase5/`; Phase 5 results in `benchmarks/results/phase5/`.
