<!-- REF_CP-4D_01 (T2) | PROPOSED | 2026-06-22 -->
<step_reference module="CP-4D" step="01" name="Source Gate and Entity Evidence">
<input>All entity-structural sources: organizational charts, guarantor schedules, collateral/security agreements, subsidiary lists (SEC Ex-21), credit-agreement and indenture definitions of Restricted Subsidiary / Unrestricted Subsidiary / Guarantor / Collateral, intercreditor agreements, security release provisions, offering-memorandum structure diagrams; plus CP-1 debt schedule (debt by entity), CP-1A ownership/entity facts, CP-4 covenant findings.</input>
<gate>Always executes. This IS the gate check. BLOCKING: at least one source establishing the entity perimeter AND guarantee/security status must be available (an executed credit agreement with guarantor/collateral schedules, OR an org chart plus guarantor schedule). If none: Module Status = Blocked, STOP.</gate>

## Instructions
1. Confirm execution mode and entity-evidence availability.
2. Inventory each source; assess status: executed / draft / posting-version / stale / incomplete.
3. Rank source authority: executed security documents & credit-agreement schedules > org chart from a filing > offering-memorandum structure diagram > investor/lender presentation.
4. Identify completeness limitations: missing guarantor schedule, missing security/collateral schedule, missing subsidiary designations, missing ICA, missing entity-level debt or EBITDA.
5. Note governing law / jurisdiction per material entity (drives perfection and guarantee-limitation analysis).
6. Assign Module Status:
   - **Completed:** entity perimeter + guarantee + security evidence available.
   - **Completed with Limitations:** partial perimeter (e.g., guarantor schedule present, security docs missing). State each limitation and downstream impact.
   - **Blocked:** no entity/guarantee evidence. Output blocked message and STOP. Do not infer the perimeter.
7. If CP-1 entity-level debt missing: structural-subordination analysis limited — flag. If CP-4 findings missing: leakage routes carry [Insufficient Information] for enabling provisions — flag.

> Entity evidence enters this gate only after a user uploads it. Do not search
> for, fetch, or infer missing entity, guarantor, collateral, or security
> documents; assign **Blocked** and name the missing evidence.

## Output
T4D.1: Source gate register (entity-evidence inventory + status + authority rank + limitations) + Module Status: Completed / Completed with Limitations / Blocked
<!-- Upstream re-anchor (common_rules #10): re-import and verify the specific upstream outputs this module consumes (CP-1 debt-by-entity, CP-1A entity/ownership facts, CP-4 covenant findings); restate the exact datapoints/run_id/period used. If a required upstream value is absent or its run_id/period mismatches, mark [Insufficient Information] and gate the dependent step — do not infer it. -->
</step_reference>
