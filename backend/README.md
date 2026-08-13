# HargaTurun backend

FastAPI recommendation API + the deterministic pricing oracle.

| Module | Responsibility |
|---|---|
| `hargaturun/pricing.py` | **The oracle.** Every number: discount %, price, timing, projections, bounds, margin floor. Pure functions, no I/O — same input always yields the same output. Implements `docs/HargaTurun_Project_Spec.md` §9.5. |

The oracle is the single source of truth for numbers, used in two places (write once,
use twice): the production pricing authority behind `POST /api/recommend`, and the
ground-truth generator for the fine-tuning dataset.

## Running the tests

The oracle is pure-stdlib, so its tests run with no dependencies installed:

```bash
cd backend
python -m unittest discover -s tests -v
```

(They are also collected by `pytest` if you have it.)
