# Guide cursor

Resume after: `69ac3ea181025a591ee21d7a0e3735b65e5a51e6` · [2026-11-02T140048Z-69ac3ea](2026-11-02T140048Z-69ac3ea.md) · 2026-11-02T14:14:18Z
Covered beyond the boundary: none

## Next

Process GUIDE-1's exact issue draft with the owner, then GUIDE-2. Both need disposition before a clean pre-park handoff; review coverage is complete, not resolution.

## Open findings

- 2026-11-02T140048Z-69ac3ea/GUIDE-1 — Pointer translation bypasses the default root-motion refusal — proposal pending (exact issue draft in the report).
- 2026-11-02T140048Z-69ac3ea/GUIDE-2 — Cubic decoder reads past a declared buffer view — unprocessed.

## Pending handoff

- All code after a462962 through #175 / 69ac3ea reviewed. The preceding guide landing a3c791c is documentation-only and excluded.
- #43 is closed by #175; the owner instruction to solve it superseded the prior deferral. Its approved 2026-11-01/02 range and exact rotation arithmetic were checked against the implementation. No open tracker issues or PRs at the snapshot; the two guide findings are not filed yet.
- GUIDE-1's exact proposed payload is issue-v1:sha256:ed6a5fe8254d77f49246eb96d52162e5d1434b15a4faf6ef82fa93571dc4a9da, label bug. Only this finding is proposed for disposition now.
- 6621 non-Blender and 358 Blender tests passed, no skips; static checks passed. Independent observational Blender probes reproduced both findings despite those suites passing.
- The merge tree equals reviewed PR head ec87635. Its separately reported default-byte comparison was not independently repeated. No new owner visual, performance, Linux/Windows or exhaustive range verdict.
- End recheck found no head, issue, PR or published-vision movement. The vision draft warning was a newline comparison artifact; published and primary bytes match.
- Repair/review/merge approved follow-ups, then make a short guide pass over that delta before parking. No new feature arc is proposed.
- Published V-4 retains the approved D-36 exception; D-18 retained-capture recolouring stays deferred. The separate kanban drainer rerun policy remains outside this repository's scope.
- History before `0eb2491` (bootstrap and PRs #1–#2) remains unreviewed.

## Alignment

| Principle | Reading | Since | Note |
|---|---|---|---|
| V-1 | aligned | 2026-10-04T175222Z-c93605c | Generic outputs and project configuration; no consumer integration. |
| V-2 | aligned | 2026-11-01T171536Z-a462962 | #173 repairs GUIDE-1; #174 makes failed-only rerun diagnostics accurate without accepting earlier results. |
| V-3 | aligned | 2026-10-04T175222Z-c93605c | GLB source identity and private importer ownership preserved. |
| V-4 | aligned | 2026-10-04T175222Z-c93605c | Addressed shading/export boundaries; accepted D-36 wording reconciled in 76075ffa51 after the audit. |
| V-5 | aligned | 2026-10-04T175222Z-c93605c | One bpy script behind validated jobs/results and owned processes. |
| V-6 | aligned | 2026-10-04T175222Z-c93605c | Camera parameters and stored subsets retain original direction identities. |
| V-7 | drifting | 2026-11-02T140048Z-69ac3ea | GUIDE-1: newly accepted cubic translation pointers bypass default root-motion validation. |
| V-8 | aligned | 2026-10-04T175222Z-c93605c | Explicit downstream responses; accepted default looks preserved. |
| V-9 | aligned | 2026-10-04T175222Z-c93605c | Shared per-clip plan and source-time addresses; mirrors add no frames. |
| V-10 | aligned | 2026-10-04T175222Z-c93605c | Shared pure alpha, lighting, quantisers, composition and encoders. |
| V-11 | drifting | 2026-11-02T140048Z-69ac3ea | GUIDE-2: cubic accessor reads cross declared buffer-view boundaries and sanitize malformed input. |
| V-12 | aligned | 2026-09-30T043336Z-fe94bd6 | Mechanical checks and recorded owner verdicts kept separate. |
