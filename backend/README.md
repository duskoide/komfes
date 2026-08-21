# HargaTurun deterministic core

Pure-Python pricing oracle and frozen model I/O contracts. The FastAPI orchestration layer will be developed on a separate backend branch.

| Module | Responsibility |
|---|---|
| `hargaturun/pricing.py` | **The oracle.** Every number: discount %, price, timing, projections, bounds, margin floor. Pure functions, no I/O — same input always yields the same output. Implements `docs/HargaTurun_Project_Spec.md` §9.5. |
| `hargaturun/schemas.py` | Strict parse/write contracts and validators shared by training-data tooling, model evaluation, and the future API layer. |

The oracle is the single source of truth for numbers, used in two places (write once,
use twice): the production pricing authority behind `POST /api/recommend`, and the
ground-truth generator for the fine-tuning dataset.

## Running the tests

The oracle is pure-stdlib, so its tests run with no dependencies installed:

```bash
cd backend
python3 -m unittest discover -s tests -v
```

(They are also collected by `pytest` if you have it.)
