# Video Kingdom Provider Admission inventory (2026-09-06, closure pass)

This is an entry-point inventory, not a provider capability claim.  A path is
listed only when it is in the current repository's executable tooling or is a
direct wrapper used by that tooling.  Vendored `research/external_repos/**`
drivers remain research material and are not a production entry until an
explicit adapter is added.

## Canonical boundary

`runtime/provider_admission.py` is the only admission implementation.  It
builds `video_kingdom.canonical_generation_request.v1`, runs the same
model-free preflight, writes `video_kingdom.provider_admission_receipt.v1`,
embeds the exact provider-facing payload, and exposes `assert_admission()` for
the line immediately before POST.  The assertion re-hashes both the
canonical request and (when supplied by the adapter) the provider payload.

## Current entries

| Entry | Actual provider action | State | Boundary evidence |
|---|---|---|---|
| `runtime/shot_core.py::run_take` | Agnes video POST | UNIFIED | `preflight_shot` -> canonical request (exact payload embedded) -> request hash -> receipt -> assert(payload) -> POST |
| `tools/run_shot_core_pilot.py` | Indirect Agnes video POST | UNIFIED | Calls `runtime.shot_core.run_take`; inherits the same admission receipt and hash boundary |
| `tools/run_shot_core_provider_reality_probe.py` | Indirect Agnes video POST | UNIFIED | Calls `run_take` for bounded samples; each generation is admitted before POST |
| `tools/resume_shot_core.py` | Agnes poll/recovery GET only | NO_GENERATION_POST | Calls `resume_take`; it can poll an existing `video_id` but cannot create a new generation |
| `tools/run_shot_core_cross_process_recovery.py` | Agnes poll/recovery GET only | NO_GENERATION_POST | Recovery path delegates to `resume_take`; no independent generation POST |
| `tools/run_short_clip.py` | Agnes video POST | UNIFIED / legacy fail-closed | Requires `--episode-contract` or `--shot-contract`; missing contract rejects before POST; payload drift is asserted immediately before POST |
| `tools/run_comedy_episode.py` | Indirect Agnes video POST | UNIFIED | Passes episode contract to `run_short_clip`; delivery gate also fails closed |
| `tools/run_controlled_shift.py` | Indirect Agnes video POST | UNIFIED | Delegates to `run_comedy_episode` with the episode contract |
| `tools/consume_dispatch_provider_card.py` | Indirect Agnes video POST | FAIL-CLOSED WITHOUT CONTRACT | Forwards an explicit contract when supplied; otherwise downstream admission rejects |
| `tools/run_idea_pipeline.py::_generate_assets` | OpenAI-compatible image POST | UNIFIED (research scope) | Asset request uses the same admission module and a persisted receipt |
| `tools/build_longmen_strict_plan.py::_generate_assets` | OpenAI-compatible image POST | UNIFIED (research scope) | Same asset admission and receipt |
| `tools/generate_episode007_anchors.py` | Shenwen image POST | UNIFIED (research scope) | Canonical asset request and receipt bind the exact JSON body; `assert_admission()` is immediately before `urlopen()` |
| `tools/generate_episode007_scene_action_anchors.py` | Shenwen image POST | UNIFIED (research scope) | Canonical asset request and receipt bind the exact JSON body; `assert_admission()` is immediately before `urlopen()` |
| `tools/semantic_slice_novel.py::_model_slice` | OpenAI/OneAPI/Zhipu chat POST | UNIFIED (research scope) | Canonical research request and receipt precede POST; output remains `RESEARCH_ONLY` |
| `tools/run_zhipu_chore.py` | Zhipu/OneAPI chat POST | UNIFIED (research scope; legacy form fail-closed) | Canonical research request and receipt precede each retry round; historical string-form calls reject before `urlopen()` |
| `tools/multi_model_script_battle.py::call` | OneAPI chat POST | UNIFIED (research scope) | Canonical research request and receipt precede POST |
| `tools/run_image_edit_retry.py` | Wrapped external CLI | FAIL-CLOSED / NO ADAPTER | Arbitrary child commands are rejected even with a receipt because payload binding is not provable |
| `tools/run_episode007_*` legacy shell runners (including `run_episode007_production.py`, probes, and targeted repairs) | Indirect Agnes video POST | FAIL-CLOSED WITHOUT CONTRACT | They call `run_short_clip` without a contract, propagate the child non-zero result, and are rejected before POST until migrated |

## Explicitly out of current production scope

`research/external_repos/ZJT/**` contains upstream/vendor drivers and tests,
but no current Video Kingdom command invokes them as a production runner.  They
are therefore `NOT_CURRENT_ENTRY`, not silently counted as unified.  Promotion
would require a new bounded adapter and a fresh admission review.

The only first-party `POST` call site that does not itself spell
`assert_admission()` is `tools/run_shot_core_provider_reality_probe.py::RecordingSession.post`.
It is a recording transport wrapper used only as the `session` passed into
`runtime.shot_core.run_take`; the caller performs the hash-bound assertion
immediately before invoking `session.post`.  It is not an independent
generation entry.

## Proof chain exercised by tests

`tests/test_provider_admission.py` proves canonical request hashing, receipt
creation, conflict rejection, receipt tamper rejection, provider-payload drift
rejection, delivery fail-closed behavior, and that Zhipu retries reuse the same
hash-bound request body. Existing Shot Core runtime tests exercise the real
`run_take` path with a fake session; no live Provider call is required for the
local admission proof. A direct legacy-runner probe returned
`RC=1` with `provider admission blocked: --episode-contract or --shot-contract
is required; no provider request submitted`.

## Closure boundary

Local runtime admission is implemented and verified.  This does not prove that
Agnes/Shenwen/Zhipu servers independently inspect or enforce the local receipt,
nor does it prove provider compliance with camera/action/identity semantics.
Those remain `NOT_PROVEN` until an explicitly authorized real-provider sample
is run.  No real Provider was called in this closure pass.
