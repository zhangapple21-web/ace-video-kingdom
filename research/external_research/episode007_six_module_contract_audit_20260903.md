# Episode 007 six-module contract audit (isolated research)

## Scope

The sample contract is validated against `six_module_shot_contract.schema.json`. It is a research artifact only; no production manifest or media was changed.

## Gate results

| Module | Gate | Evidence required | Result |
|---|---|---|---|
| Script/dialogue | line locked; measured TTS duration; emotion tag present | `dialogue_text`, `line_locked`, `tts_duration_seconds`, `audio_status` | PASS on sample |
| Camera/continuity | dialogue locked; max one movement; action first frame is scene-action anchor | `shot_type`, `movement_count`, `first_frame_kind`, `axis` | PASS on sample |
| Edit/rhythm | 2.5–18s; cut only after performance; transition reason | `duration_seconds`, `cut_after_performance`, `rhythm_phase` | PASS on sample |
| Performance/sound | exactly preparation→action→recovery beats; sound cues listed | `action_beats[3]`, `sound_cues` | PASS on sample |
| Assets/continuity | identity and scene-action references are separate; costume/props/light bound | all `assets` fields | PASS on sample |
| Batch/recovery | max 2 attempts; cooldown-aware delay; explicit degradation | `max_attempts`, `retry_delay_policy`, `degrade_order` | PASS on sample |

## Known episode-007 gap

The existing episode-007 preflight records 18 shots missing `action_beats` and 18 missing a shared scene-anchor URL. Therefore the current production contract cannot be promoted to this research schema without backfilling those fields. This report does not backfill or alter production.

## Decision

`RESEARCH_GREEN / PRODUCTION_NOT_CONNECTED`. The schema catches the previously observed failure classes (portrait used as first frame, dialogue movement, missing action recovery, unmeasured audio, out-of-range duration, and missing recovery policy). A future integration must add a single-writer adapter at the existing preflight boundary; do not add a second scheduler/router.
