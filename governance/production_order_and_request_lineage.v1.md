# Production Order and Request Lineage v1

This rule closes two recurring failure modes in the Video Kingdom workflow.

## 1. Materialize a run only after production preflight

For `PRODUCTION` mode, the order is mandatory:

```text
story/episode plan
→ asset and continuity preflight (read-only)
→ repair until READY
→ materialize one production Run
→ lock shots
→ admit canonical requests
→ execute externally
→ ingest receipts
→ five-layer QC
→ select takes
→ assemble and accept
```

If preflight is blocked, the control plane may write a compact
`*.preflight.json` receipt, but must not create a production Run. A blocked
preflight is evidence that inputs are not ready, not evidence of a production
attempt.

Sandbox/bootstrap experiments may retain an exploratory blocked Run, but that
Run cannot authorize production admission or delivery.

## 2. A changed request is a new revision, not a transparent retry

The request hash covers the complete canonical request and provider payload.
The following are distinct requests whenever any value changes:

- prompt or negative prompt;
- reference assets or their transport form;
- model, endpoint, duration, camera, or generation parameters;
- first/last frame or other contract-bound state.

Replaying the exact same request hash is idempotent. A changed request must
explicitly provide `revision_of=<prior request_hash>`. The ledger then records
`revision`, `supersedes_request_hash`, and marks the prior admission as
superseded. Without that explicit lineage, the control plane blocks the
operation as `GENERATION_ALREADY_ADMITTED`.

Provider rejection, transport failure, or a 413 continuation failure does not
authorize an automatic replay. Preserve `UNKNOWN`/`FAILED`, carry only compact
manifest paths, hashes, IDs, and gate state into a genuinely fresh context,
and reconcile before any new external action.

## 3. Shot progression remains serial at the creative gate

`Creative=UNKNOWN`, `NOT_PROVEN`, or `REWORK_REQUIRED` blocks selection and
does not justify bulk-generating later shots. Resolve the current shot as
`PASS`, `REWORK_REQUIRED` (with a new take/request lineage), or `NOT_PROVEN`
before advancing the production decision to the next shot.

