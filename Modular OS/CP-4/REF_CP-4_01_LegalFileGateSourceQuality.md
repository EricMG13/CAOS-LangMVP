<!-- REF_CP-4_01 (T2) | 2026-06-03 -->
<step_reference module="CP-4" step="01" name="Legal File Gate and Source Quality">
<input>All available source materials: executed credit agreements, indentures, intercreditor agreements, amendments, waivers, compliance certificates, term sheets, offering memoranda, lender presentations, covenant-review reports, rating agency legal commentary, debt schedules, guarantor/collateral/subsidiary schedules, security documents, regulatory filings, CP-1 financial foundation, CP-1A transaction summary, CP-3D refinancing/LME output.</input>
<gate>Always executes. This IS the gate check. BLOCKING: At least one executed governing legal document (credit agreement or indenture) must be available. If none: Module Status = Blocked, STOP.</gate>

## Instructions
1. Confirm execution mode and legal-document availability.
2. Assess document status for each source: executed / draft / posting-version / unsigned / incomplete / stale.
3. Rank source authority using 6-rank hierarchy (executed CA/indenture > ICA > compliance certs > OM > third-party review > lender pres/term sheet).
4. Identify completeness limitations: missing amendments, schedules, exhibits, compliance certificates.
5. Note governing law and jurisdiction.
6. Check covenant-review report availability.
7. Verify structured-export readiness.
8. Assign Module Status:
   - **Completed:** Executed governing doc(s) + current financial inputs.
   - **Completed with Limitations:** Executed governing doc(s) but missing supplements. State each limitation and downstream impact.
   - **Blocked:** No executed governing document. Output blocked message and STOP.
9. If CP-1 financials missing: headroom/capacity calculations limited — flag.
10. If CP-3D missing: LME legal-capacity overlay incomplete — flag.

> Governing documents enter this gate only after a user uploads them. Do not
> search for, fetch, or infer a missing agreement. If the uploaded case lacks an
> executed credit agreement or indenture, assign **Blocked** and name the gap.

## Output
T4.1: Source gate register (document inventory + quality assessment + authority rank + limitations)
+ Module Status: Completed / Completed with Limitations / Blocked
<!-- Upstream re-anchor (common_rules #10): at this gate, re-import and verify the specific upstream module outputs this module consumes (per declared Upstream); restate the exact datapoints/run_id/period used. If a required upstream value is absent or its run_id/period mismatches this run, mark [Insufficient Information] and gate the dependent step — do not re-derive or infer the upstream value from memory. -->
</step_reference>
