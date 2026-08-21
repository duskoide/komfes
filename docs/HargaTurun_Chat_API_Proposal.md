# `POST /api/chat` — proposed wire contract

> **Status:** PROPOSAL from the frontend side, awaiting backend confirmation.
> **Purpose:** unblock parallel work on issue #4. The Agentic Workflow Plan
> specifies state, action policy and the tool contract, but not the HTTP
> request/response shape. This document proposes one so the chat UI and the
> orchestrator can be built at the same time instead of in sequence.
> **Authority:** `docs/HargaTurun_Agentic_Workflow_Plan.md` remains the
> authority on behaviour. Nothing here may widen the action allowlist or move
> numerical authority away from the pricing tool.

Anything in this file may be changed by the backend owner. The frontend keeps
all mapping in `frontend/lib/services/chat_repository.dart`, so a change costs
one file rather than the whole screen.

## Endpoint

`POST /api/chat` — synchronous, one turn per request. No streaming.

## Request

```json
{
  "session_id": "b3f1c8e2-...",
  "action": "message",
  "text": "roti tawar 10 biji exp 2 hari harga 15rb modal 10rb",
  "patch": null
}
```

| Field | Type | Notes |
|---|---|---|
| `session_id` | string, nullable | Omit or `null` on the first turn; the server returns one to reuse. |
| `action` | enum | `message`, `confirm`, `calculate`, `explain`, `revise_promo`, `reset`. |
| `text` | string, nullable | Required for `message` and `revise_promo`. |
| `patch` | object, nullable | Only for `confirm`: the fields the vendor edited on the confirmation card. Keys are a subset of the state fields below. |

`confirm` carries `patch` because the confirmation card is editable: the vendor
may correct a value and confirm in a single step. The server still validates and
merges; the client never sends a whole state object back.

## Response

`200` for every handled turn, including recoverable problems. Transport and
server faults keep their own status codes.

```json
{
  "session_id": "b3f1c8e2-...",
  "action": "ASK_FOR_MISSING_FIELDS",
  "assistant_message": "Sudah kucatat rotinya. Rata-rata terjual berapa per hari?",
  "state": {
    "item_name": "Roti Tawar",
    "category": "Bakery",
    "original_price": 15000,
    "cost": 10000,
    "stock": 10,
    "days_remaining": 2,
    "daily_sales": null,
    "total_shelf_life": 4,
    "shop_name": null,
    "confirmed": false,
    "revision": 1,
    "result_revision": null
  },
  "missing_fields": ["daily_sales"],
  "ambiguous_fields": [],
  "result": null
}
```

| Field | Type | Notes |
|---|---|---|
| `session_id` | string | Echoed, or newly minted on the first turn. |
| `action` | enum | The action the orchestrator actually took, from the §3.1 allowlist. The client renders from this, never from parsing prose. |
| `assistant_message` | string | Indonesian, already validated by the language validator. |
| `state` | object | Full current state, exactly the §3.2 shape. |
| `missing_fields` | string[] | Field names still required. Drives the grouped question and the "perlu diisi" markers. |
| `ambiguous_fields` | string[] | Read but not trusted; needs vendor confirmation. |
| `result` | object, nullable | Present only when a valid result exists for `state.revision`. |

### `action` values

Mirrors §3.1 so the client can switch exhaustively:

`ASK_FOR_MISSING_FIELDS`, `SHOW_CONFIRMATION`, `CALL_PRICING_TOOL`,
`EXPLAIN_RESULT`, `REVISE_PROMO_COPY`, `OUT_OF_SCOPE`, `SAFE_FAILURE`.

### `result`

Reuses the existing `/api/recommend` payload so no new rendering is needed —
the recommendation, no-action and warning cards already handle these shapes.

```json
{
  "status": "recommendation",
  "revision": 2,
  "recommendation": { "...": "as in /api/recommend" },
  "explanation": "...",
  "promo_copy": "...",
  "preview": { "...": "as in /api/recommend" }
}
```

`status` is one of `recommendation`, `no_action`, `invalid_input`.
`result.revision` must equal `state.result_revision`; the client refuses to
render a result whose revision does not match `state.revision`, which is how
stale results stay invisible after a correction.

## Errors

| Case | Shape |
|---|---|
| Model or tool failure | `200` with `action: "SAFE_FAILURE"` and a recoverable `assistant_message`. State is preserved. |
| Unknown or expired `session_id` | `404` with `{ "detail": "..." }`. The client starts a new session and says so. |
| Malformed request | `422` with `{ "detail": "..." }`. |

`SAFE_FAILURE` is deliberately `200`: the turn was handled and the vendor's
state survived, so the client must not treat it as a transport error and must
not discard the conversation.

## Out of scope here

Image input (issue #4 section 3) is not covered. When it lands it should extend
this request with a multipart variant rather than change the JSON shape, so the
text path stays untouched.
