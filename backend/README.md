# HargaTurun conversational-agent core

Pure-Python pricing oracle and model I/O contracts. The main-branch product target is a bounded conversational orchestrator that maintains validated state, requires confirmation, and exposes this oracle through a typed pricing tool.

| Module | Responsibility |
|---|---|
| `hargaturun/pricing.py` | **The oracle.** Every number: discount %, price, timing, projections, bounds, margin floor. Pure functions, no I/O — same input always yields the same output. Implements `docs/HargaTurun_Project_Spec.md` §9.5. |
| `hargaturun/schemas.py` | Existing strict parse/write contracts and validators. These are the baseline for the planned conversational patch/write contracts; they must be revised without weakening numerical-faithfulness checks. |

The oracle is the single source of truth for numbers behind the planned `PricingTool`. The conversational model must never calculate, override, or silently alter these values.

## Running the tests

The oracle is pure-stdlib, so its tests run with no dependencies installed:

```bash
cd backend
python3 -m unittest discover -s tests -v
```

(They are also collected by `pytest` if you have it.)
