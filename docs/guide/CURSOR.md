# Guide cursor

Resume after: `69ac3ea181025a591ee21d7a0e3735b65e5a51e6` · [2026-11-02T140048Z-69ac3ea](2026-11-02T140048Z-69ac3ea.md) · 2026-11-02T14:14:18Z
Covered beyond the boundary: none

## Next

GUIDE-1 is filed as #176; the manager owns its review, repair and merge. GUIDE-2's exact bug-issue draft awaits the manager's signoff in project chat. Review coverage remains at 69ac3ea; filing is not resolution.

## Open findings

- 2026-11-02T140048Z-69ac3ea/GUIDE-2 — Cubic decoder reads past a declared buffer view — proposal pending (exact issue draft in the report).

## Pending handoff

- All code after a462962 through #175 / 69ac3ea reviewed. The preceding guide landing a3c791c is documentation-only and excluded.
- #43 is closed by #175; the owner instruction to solve it superseded the prior deferral. Its approved 2026-11-01/02 range and exact rotation arithmetic were checked against the implementation. No open tracker issues or PRs at the snapshot; the two guide findings are not filed yet.
- GUIDE-1 filed as [#176](https://github.com/coghex/moskophoros/issues/176) from the manager-signed exact draft, label bug. Owner relay: “File, solve both, park”. The manager owns reviews, solves and merges; GUIDE-2 draft still needs signoff.
- GUIDE-2 draft SHA-256 9db93867f7605a5e220aa2c733394625699f0c91fa258713d64ff032dff4595e; payload issue-v1:sha256:4534b9aabe6cae500bc3b3ce62e31cb1a15e60b1e15c97099e33f2ea21c42daf, label bug.
- Signoff belongs to verified mosk-manager under the owner's standing issue-draft authority (direct owner routing correction 2026-11-02). Exact GUIDE-2 request posted in #moskophoros as question 2w2r3bjzxbft29hygse85xyhsw, --re moskophoros-20261031-1; accept an in-scope manager answer to that request, then file/report without asking the owner again.
- #176 reported as mosk-guide in #moskophoros with --re moskophoros-20261031-1. After GUIDE-2 signoff and creation, report its number there with the same request ID; the manager owns readiness review, solve and merge.
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
