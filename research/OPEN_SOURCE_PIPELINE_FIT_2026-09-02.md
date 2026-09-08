# Open-source short-drama pipeline fit review — 2026-09-02

## Decision

Do not replace the current Video Kingdom/ACE control plane with a new framework.
Adopt mechanisms, not product names. The current bottleneck is not missing
orchestration software; it is weak shot-level action evidence and insufficient
critic-to-repair feedback.

## Evidence status

| Candidate | Evidence in this workspace | Decision |
|---|---|---|
| ArcReel | No checked-out repository, package, license, or reproducible local run | RESEARCH_ONLY; do not install or claim support |
| OpenDirector | No local source or reproducible run | RESEARCH_ONLY |
| FilmAgent / CrewAI / LangGraph | General orchestration patterns; no local production fit test | Mechanism reference only; do not create a second runtime |
| MagicLight / Topview / 7ART | Closed/platform claims not independently verified here | No dependency |
| Kling / Vidu / Seedance | Provider capabilities and access not verified in this workspace | No routing change |
| SEAM-like entity memory | Mechanism is applicable; no exact implementation verified | Implement a small local contract, not a new framework |

## What is adopted now

1. Entity-attribute memory (SEAM principle)
   Every shot contract records visible entities, immutable attributes, state
   transition, and forbidden drift. A shot is rejected if a required attribute
   cannot be checked from frames.

2. Critic to correction loop
   A generated shot receives the director-template review. REJECT creates
   one targeted repair card for that shot; it does not regenerate the whole
   episode.

3. Stage gates
   Script gate -> character asset gate -> scene-anchor gate -> action probe gate
   -> per-scene batch gate -> full-cut gate. Each gate is PASS/CONDITIONAL/REJECT.

4. Evidence-first promotion
   A completed provider job is not a quality pass. Promotion requires artifact
   hash, ffprobe, frame evidence, and a completed review record.

5. Bounded recovery
   Existing video IDs are resumed before new submission. Transient failures use
   provider Retry-After when present, otherwise the provider profile cooldown.
   No duplicate scheduler or task pool is introduced.

## Current gap

The production runner still records provider completion but does not yet
automatically attach the director-template review and frame evidence to every
shot. Until that is implemented, the action probes remain the only reviewed
shots and the episode cannot be promoted to a final master.

## Next implementation order

1. Add a machine-readable shot_review.v1.json record for each probe.
2. Require PASS or explicit CONDITIONAL conditions before scene batching.
3. Add a targeted repair queue keyed by shot_id and failure class.
4. Keep all experimental frameworks in RESEARCH_ONLY until a local, licensed,
   reproducible run demonstrates a material improvement over the current path.

