# Guide cursor

Resume after: `fe94bd6995a3f370b7b8d222ce8d7839e76225da` · [2026-09-30T043336Z-fe94bd6](2026-09-30T043336Z-fe94bd6.md) · 2026-09-30T05:30Z
Covered beyond the boundary: none

## Next

Solve #12 (GUIDE-1's Blender smoke test) before slice 1's first package pull
request, then process GUIDE-2, the next merge-safety finding.

## Open findings

- 2026-09-30T043336Z-fe94bd6/GUIDE-2 — a body edit leaves the previous `build-test` pass standing for minutes — unprocessed
- 2026-09-30T043336Z-fe94bd6/GUIDE-3 — the descriptor check ignores the digest and versions — unprocessed
- 2026-09-30T043336Z-fe94bd6/GUIDE-4 — catalog group IDs can create checks with required names — unprocessed
- 2026-09-30T043336Z-fe94bd6/GUIDE-5 — `.gitattributes` can change the image build context unfingerprinted — unprocessed
- 2026-09-30T043336Z-fe94bd6/GUIDE-6 — planner tests miss three-dot and text reasons; text mode crashes on non-UTF-8 paths — unprocessed
- 2026-09-30T043336Z-fe94bd6/GUIDE-7 — `AGENTS.md:74` and `docs/validation.md:414` overclaim — unprocessed

## Pending handoff

- Unverified: a cancelled CI run may leave `build-test` recorded as skipped, and a base-branch edit may replan against a stale merge commit.
- Epic #3 is open with every child closed.
- History before `0eb2491` (PRs #1, #2 and bootstrap) was never reviewed by guide.

## Alignment

| Principle | Reading | Since | Note |
|---|---|---|---|
| V-1 | not exercised | — | |
| V-2 | aligned | 2026-09-30T043336Z-fe94bd6 | pinning gaps in GUIDE-3, GUIDE-5 |
| V-3 | not exercised | — | |
| V-4 | not exercised | — | |
| V-5 | not exercised | — | |
| V-6 | not exercised | — | |
| V-7 | not exercised | — | |
| V-8 | not exercised | — | |
| V-9 | not exercised | — | |
| V-10 | not exercised | — | |
| V-11 | not exercised | — | |
| V-12 | aligned | 2026-09-30T043336Z-fe94bd6 | repairs in GUIDE-1, GUIDE-6 |
