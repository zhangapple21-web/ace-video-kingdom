# Video Kingdom learning loop — episode 007 lessons

## Durable lessons from the previous Wenji and virtual-data runs

1. A provider job marked COMPLETED is only transport success. It is never a
   creative-quality pass.
2. A character sheet is not an action reference. Driving a static portrait
   produced the rejected "cover wakes up" effect.
3. Every shot needs an explicit action arc: preparation -> force/acceleration ->
   follow-through or recovery. Review must inspect multiple time points.
4. User-supplied character references outrank generated approximations when the
   story requires wardrobe identity. Alang is the grey short-sleeve shirt;
   Feige is the black polo.
5. Review one action probe per failure class before batch rendering. A failed
   probe blocks the scene, not the whole project; repair only the affected shot.
6. 503 and queue delays are operational failures, not creative failures. Resume
   by existing video_id, honor Retry-After/provider cooldown, and never duplicate
   a completed request.
7. Subtitles must contain only spoken dialogue or necessary first-person inner
   monologue. Scene descriptions belong in the shot contract, not on screen.
8. A final cut requires both media integrity (ffprobe/hash) and a director
   verdict. Technical validity alone cannot promote a cut.

## Current production law

PASS requires force, inertia, temporal continuity, identity, and emotional
function. CONDITIONAL requires a named correction and cannot promote a full
cut. REJECT creates a targeted repair card keyed by shot_id and failure class.

The loop is: observe -> diagnose -> dispatch -> render/recover -> multi-frame
review -> targeted repair -> scene gate -> assembly -> subtitle/audio gate ->
full-cut review. This extends the existing ACE daemon/Video Kingdom queue; it
does not create a second scheduler or autonomous publisher.

production_integration=false

