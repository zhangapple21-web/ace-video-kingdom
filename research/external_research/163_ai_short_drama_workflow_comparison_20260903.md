# Public workflow comparison: Agnes/Pavo article vs Video Kingdom

Source: https://www.163.com/dy/article/L5BM1FJ405568W0A.html (accessed 2026-09-03)

## Mechanisms worth absorbing

The article describes a layered workflow rather than a one-shot prompt:

1. Story root is expanded into episodes and causal scenes.
2. Characters, wardrobe variants, scenes, and props enter a reusable asset library.
3. Each episode is decomposed into concrete storyboard shots.
4. A canvas preserves parent/child branches so local rework does not erase prior versions.
5. Character sheets and four-view references stabilize identity.
6. A spatial/3D blocking stage makes actor positions and camera placement explicit for difficult multi-actor shots.
7. Agnes Video 2.5 Flash is used for cheap iteration; paid credits are reserved for harder shots.

## Cross-check against our actual chain

Already present: distinct scene anchors, identity contracts, action-beat preflight, subtitle/audio receipts, multi-frame review, hash-bound Decision Records, Free Zone isolation, and ACE result writeback.

Previously weak or implicit: reusable asset IDs, branch lineage for local repairs, explicit spatial blocking, and a single stage contract connecting story root to final experience memory.

## Implemented adjustment

`governance/production_workflow_profile.v1.json` makes those mechanisms explicit without creating another runtime. It is a contract for the existing controlled production path. Free Zone may use the same mechanisms for isolated Agnes experiments, but its output remains a candidate until hash-bound admission.

## What remains evidence-dependent

- Agnes audio quality and dialogue alignment still require actual returned audio plus a measured review.
- A spatial blocking record improves prompts but does not prove the provider obeyed positions.
- Asset reuse reduces drift risk but does not replace frame-level inspection.
- Cheap Flash iteration reduces cost only when retries and latency are recorded; no fixed savings claim is made here.
