# LEGACY is /Users/ericguei/Claude/Projects/CAOS — not "Credit Operating System"

Two sibling repos both contain a `caos/tests/` directory and look like plausible legacy sources:

- `/Users/ericguei/Claude/Projects/CAOS` — **correct.** 18,174 test lines, flat `caos/tests/`, has the CP-DR files, lease-fencing/three-way-merge vocabulary, and this repo's seed commit (`61f0afc "Seed repo from CAOS"`) points at it. Inventory pinned it at commit `84f9705` (2026-08-26).
- `/Users/ericguei/Claude/Projects/Credit Operating System` — a different, larger era of the codebase (60k+ test lines, alerts/research-report/playwright suites). Not the rebuild's reference. Its path also contains spaces, which breaks naive `xargs`.

Why it mattered: an agent grepping for "caos/tests" finds both; classifying or porting from the wrong one silently imports guarantees the rebuild never promised. Also: briefs may quote stale line counts ("~7,000 lines") — verify with `wc -l` before scoping, and say so when the numbers disagree.
