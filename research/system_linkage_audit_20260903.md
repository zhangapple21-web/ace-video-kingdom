# ACE / Free Zone / Video Kingdom linkage audit

Audit time: 2026-09-03 (Asia/Shanghai)

## Verified live links

- Cross-base handshake: `HANDSHAKE_OK`.
- Reachable bases: ACE Core, R1, R1 archaeology, mine-seed, and Video Kingdom.
- Local ports: OneAPI `127.0.0.1:3000` reachable; ACE proxy `127.0.0.1:3001` reachable during the handshake.
- World Atlas bidirectional-flow validator: valid.
- World Atlas fixture validation: valid (`entries=7`, `production_integration=false`).
- World Atlas source-path validation: valid (`references=8`, `content_retained=false`).
- ACE focused tests: 17 passed when run with the ACE repository on `PYTHONPATH`.
- Video Kingdom tests: 20 passed.

## Linkage gaps (not failures of reachability)

1. **ACE -> Video Kingdom dispatch is only a research-card handoff.**
   The current `dispatch_queue.v1.json` contains one completed `CONTINUITY_REPAIR` card with `provider_calls=0`. This proves queue consumption and evidence writeback, not automatic video production.
2. **Video Kingdom -> ACE is evidence-level, not a delivery callback.**
   `cross_base_handshake.py` checks paths, hashes and ports; it does not transfer a selected take, Decision Record, or delivery result into ACE.
3. **The model directory and model usability are separate.**
   `/v1/models` is discovery only. Fresh model probes remain the authority; a transient 403 must be recorded but cannot permanently quarantine a model.
4. **Free Zone and controlled production are correctly separated.**
   Free Zone artifacts require explicit hash-bound admission before a formal production `PASS`; no implicit promotion is allowed.
5. **There is repository drift during parallel work.**
   ACE Core and Video Kingdom both have unrelated dirty files. This audit did not stage, reset, merge, or overwrite them.

## Overall classification

`CONNECTED_WITH_GAPS`

The foundations are linked and validated, but the full chain is not autonomous end-to-end: research dispatch, formal production admission, media execution, decision record, and ACE writeback are still separate evidence steps. This is intentional fail-closed behavior, not a claim of completed production.

## Required next boundary (no second runtime)

Extend the existing single handoff/evidence path with a hash-bound result receipt that references the Video Kingdom Decision Record and selected media integrity receipt. Do not create a second scheduler/router, and do not let a research card or model response itself authorize delivery.
