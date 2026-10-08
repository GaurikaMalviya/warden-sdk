# tasks/plan.md

## Overview
Implement `examples/demo.py` and `examples/rules.yaml` with 3 deterministic scenarios:
1. Normal loan approval under threshold -> ALLOW
2. Loan approval over threshold -> BLOCK
3. Stated reasoning mismatch -> ESCALATE via Drift Agent (Tier 1 deterministic pass)

## Tasks
- [x] Task 1: Create `demo_spec.md`.
- [x] Task 2: Enhance `Guard` in `src/warden/guard.py` to support `drift_action` (`"BLOCK"` or `"ESCALATE"`).
- [x] Task 3: Create `examples/rules.yaml`.
- [x] Task 4: Create `examples/demo.py`.
- [x] Task 5: Run demo multiple times, verify deterministic output.
- [x] Task 6: Run existing test suite to ensure no regressions.
- [x] Task 7: Run `/ponytail-review` on `examples/demo.py`.
