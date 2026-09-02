"""Document-first intake application service (Task 8; Phase 3 of
ENTERPRISE_READINESS_PLAN.md).

Orchestrates the existing domain services and nothing else: `prepare_upload`
applies every admission check (there is no second copy here), `classify` reads
the prepared evidence, `DomainStore.admit_intake` commits the whole pack in one
transaction, `import_loan_source` pins a market-marks workbook, and
`Engine.start_run` starts the route with the qualified provider identity. The
browser and the documents supply files only; every analytical field — issuer,
label, document types, periods, dispositions, pathway, depth — is derived here
and served as a labelled machine suggestion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from ..contracts import digest
from ..engine.runtime import EngineError
from ..observability import log_event
from ..sources.classify import (
    classify_document,
    consumers_for,
    coverage,
    normalize_issuer,
    select_route,
    suggest_sector,
)
from ..sources.domain import Vault, prepare_upload

MAX_INTAKE_FILES = 40
UNIDENTIFIED_ISSUER = "Unidentified issuer"

_NEXT_ACTIONS = {
    "INTAKE_NO_FILES": "Drop at least one document (PDF, XLSX, JSON, TXT, Markdown or CSV).",
    "INTAKE_TOO_MANY_FILES": f"Drop at most {MAX_INTAKE_FILES} documents per intake; add the rest to the same case afterwards.",
    "INTAKE_ADMISSION_REFUSED": "Remove or replace the refused file and drop the pack again; nothing was admitted.",
    "INTAKE_SOURCE_CONFLICT": "Two different documents share one filename; rename one and drop the pack again.",
    "INTAKE_ISSUER_AMBIGUOUS": "The pack names more than one issuer; drop one issuer's documents at a time.",
    "INTAKE_ISSUER_MISMATCH": "These documents name a different issuer from the selected case; choose that case or drop them without a case.",
    "INTAKE_EVIDENCE_INSUFFICIENT": "Add a document with extractable text — an annual report, a quarterly report or a credit agreement — to this case.",
    "RUN_ENGINE_UNAVAILABLE": "The documents are admitted; execution will start when the run engine is available.",
}


class IntakeRefused(Exception):
    """A typed refusal: the pack persisted nothing but its audit row."""

    def __init__(self, code: str, message: str, findings: list[dict[str, Any]] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.findings = findings or []

    def detail(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "next_action": _NEXT_ACTIONS.get(self.code, "Review the findings and drop the pack again."),
            "findings": self.findings,
        }


def _finding(filename: str, detail: str, *, status: int | None = None, code: str | None = None) -> dict[str, Any]:
    return {"filename": filename, "status": status, "code": code, "detail": detail}


class IntakeService:
    def __init__(self, *, store: Any, engine: Any, settings: Any) -> None:
        self.store = store
        self.engine = engine
        self.settings = settings

    # -- entry -------------------------------------------------------------------

    async def submit(self, *, actor: str, uploads: list[UploadFile], case_id: str | None) -> tuple[dict[str, Any], bool]:
        """Returns (intake row, created). Raises IntakeRefused for a pack that
        admits nothing; HTTP authorization is the route's job and happens first."""
        explicit_case = self.store.get_case(case_id) if case_id else None
        if case_id and explicit_case is None:
            raise HTTPException(status_code=404, detail="case not found")
        try:
            return await self._submit(actor=actor, uploads=uploads, explicit_case=explicit_case)
        except IntakeRefused as exc:
            self.store.refuse_intake(actor, exc.code, case_id=case_id)
            log_event("intake.refused", case_id=case_id, code=exc.code, files=len(uploads))
            raise

    async def _submit(self, *, actor: str, uploads: list[UploadFile], explicit_case: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
        if not uploads:
            raise IntakeRefused("INTAKE_NO_FILES", "No documents were supplied.")
        if len(uploads) > MAX_INTAKE_FILES:
            raise IntakeRefused("INTAKE_TOO_MANY_FILES", f"{len(uploads)} documents exceed the {MAX_INTAKE_FILES}-file intake ceiling.")

        prepared = await self._prepare(uploads)
        documents = self._classify(prepared)
        issuer, issuer_confidence = self._resolve_issuer(documents, explicit_case)
        case, new_case = self._resolve_case(actor, explicit_case, issuer, documents)
        self._apply_existing_sources(case, documents)
        self._apply_dispositions(documents)

        # Double submit converges: the key is the actor, the normalized issuer
        # and the exact document digests — never the case id, which does not
        # exist until the first submission is admitted.
        digests = sorted({document["sha256"] for document in documents})
        intake_key = digest({"actor": actor, "issuer": normalize_issuer(issuer), "digests": digests})
        existing = self.store.find_intake_by_key(actor, intake_key)
        if existing is not None and (case is None or existing["case_id"] == case["id"]):
            return existing, False

        route = select_route(documents)
        brief = next((document.pop("_brief") for document in documents if document.get("_brief")), None)
        for document in documents:
            document.pop("_brief", None)
        record = {
            "suggestions": {
                "issuer": issuer,
                "label": new_case["name"] if new_case else case["name"],
                "sector": new_case["sector"] if new_case else case["sector"],
                "issuer_confidence": issuer_confidence,
                "basis": "host_classification",
            },
            "route": route,
            "coverage": coverage(documents),
            "documents": [self._manifest_row(document) for document in documents],
        }
        admitted = [document["_prepared"] for document in documents if document["disposition"] != "duplicate" or document["_first"]]
        admitted = [item for item in admitted if item.get("id")]
        usable = any(document["disposition"] == "used" for document in documents)
        status = "clarification" if not usable else "execution_unavailable"
        refusal = None if usable else {
            "code": "INTAKE_EVIDENCE_INSUFFICIENT",
            "message": "None of the supplied documents carries usable analytical evidence.",
            "next_action": _NEXT_ACTIONS["INTAKE_EVIDENCE_INSUFFICIENT"],
            "findings": [
                _finding(document["filename"], document["reason"]) for document in documents
                if document["disposition"] != "used"
            ],
        }
        try:
            intake = self.store.admit_intake(
                actor=actor, case_id=case["id"] if case else None, new_case=new_case,
                prepared=admitted, intake_key=intake_key, status=status, record=record, refusal=refusal,
            )
        except ValueError as exc:
            if str(exc) == "source content already active":
                raise IntakeRefused("INTAKE_SOURCE_CONFLICT", "A document in the pack is already active in this case under different metadata.") from exc
            raise
        case_id = intake["case_id"]
        log_event("intake.admitted", case_id=case_id, intake_id=intake["id"], sources=len(admitted),
                  pathway=route["pathway"], status=status)
        self._import_market_marks(case_id, actor, documents)
        if not usable:
            return intake, True
        return await self._start(intake, actor=actor, route=route, brief=brief), True

    # -- steps ---------------------------------------------------------------------

    async def _prepare(self, uploads: list[UploadFile]) -> list[dict[str, Any]]:
        vault = Vault(self.settings)
        prepared: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []
        for upload in uploads:
            filename = Path(upload.filename or "source.bin").name
            try:
                source = await prepare_upload(vault, upload, self.settings.max_source_bytes)
            except HTTPException as exc:
                findings.append(_finding(filename, str(exc.detail), status=exc.status_code))
                continue
            source["content"] = Path(source["vault_path"]).read_bytes()
            prepared.append(source)
        if findings:
            raise IntakeRefused(
                "INTAKE_ADMISSION_REFUSED",
                f"{len(findings)} of {len(uploads)} documents failed admission; the pack was not admitted.",
                findings,
            )
        seen: dict[str, str] = {}
        conflicts: list[dict[str, Any]] = []
        for source in prepared:
            previous = seen.setdefault(source["filename"], source["sha256"])
            if previous != source["sha256"]:
                conflicts.extend(
                    _finding(source["filename"], "two different documents share this filename")
                    for _ in range(2)
                )
        if conflicts:
            raise IntakeRefused("INTAKE_SOURCE_CONFLICT", "Two different documents in the pack share one filename.", conflicts)
        return prepared

    def _classify(self, prepared: list[dict[str, Any]]) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        first_by_sha: dict[str, dict[str, Any]] = {}
        for source in prepared:
            content = source.pop("content")
            classification = classify_document(source["filename"], content, source["sha256"], source["blocks"])
            first = first_by_sha.get(source["sha256"])
            document = {
                "filename": source["filename"],
                "sha256": source["sha256"],
                "source_id": None,
                "_prepared": source,
                "_first": first is None,
                "_duplicate_of": first,
                "_classification": classification,
                "_brief": classification.get("brief"),
                "document_type": classification["document_type"],
                "period": classification["period"],
                "version_status": classification["version_status"],
                "disposition": "used",
                "reason": "",
                "confidence": classification["confidence"],
                "signals": list(classification["signals"]),
            }
            if first is None:
                from ..storage.store import new_id

                source["id"] = new_id("src")
                document["source_id"] = source["id"]
                first_by_sha[source["sha256"]] = document
            else:
                document["source_id"] = first["source_id"]
                document["disposition"] = "duplicate"
                document["reason"] = f"identical bytes to {first['filename']}; admitted once under that name"
            documents.append(document)
        return documents

    def _resolve_issuer(self, documents: list[dict[str, Any]], explicit_case: dict[str, Any] | None) -> tuple[str, str]:
        candidates: dict[str, list[str]] = {}
        names: dict[str, str] = {}
        for document in documents:
            issuer = document["_classification"].get("issuer")
            if issuer:
                key = normalize_issuer(issuer)
                candidates.setdefault(key, []).append(document["filename"])
                names.setdefault(key, issuer)
        if len(candidates) > 1:
            raise IntakeRefused(
                "INTAKE_ISSUER_AMBIGUOUS",
                "The pack names more than one issuer: " + "; ".join(sorted(names.values())) + ".",
                [_finding(filename, f"names {names[key]}") for key, files in candidates.items() for filename in files],
            )
        if candidates:
            key, files = next(iter(candidates.items()))
            issuer = names[key]
            confidence = "high" if len(files) >= 2 else "medium"
        else:
            issuer, confidence = (explicit_case["issuer"], "medium") if explicit_case else (UNIDENTIFIED_ISSUER, "low")
        if (
            explicit_case and candidates
            and explicit_case["issuer"] != UNIDENTIFIED_ISSUER  # a placeholder case adopts the first named pack
            and normalize_issuer(explicit_case["issuer"]) != normalize_issuer(issuer)
        ):
            raise IntakeRefused(
                "INTAKE_ISSUER_MISMATCH",
                f"The documents name {issuer} but the selected case is {explicit_case['issuer']}.",
                [_finding(filename, f"names {issuer}") for filename in next(iter(candidates.values()))],
            )
        return issuer, confidence

    def _resolve_case(self, actor: str, explicit_case: dict[str, Any] | None, issuer: str, documents: list[dict[str, Any]]):
        if explicit_case is not None:
            return explicit_case, None
        key = normalize_issuer(issuer)
        if issuer != UNIDENTIFIED_ISSUER:
            matches = [case for case in self.store.list_cases(actor) if normalize_issuer(case["issuer"]) == key]
            if len(matches) == 1:
                return matches[0], None
        texts = [
            "\n".join(str(block.get("text") or "") for block in document["_prepared"]["blocks"][:20])
            for document in documents if document["_first"]
        ]
        today = datetime.now(timezone.utc).date().isoformat()
        return None, {"name": f"{issuer} intake {today}", "issuer": issuer, "sector": suggest_sector(texts)}

    def _apply_existing_sources(self, case: dict[str, Any] | None, documents: list[dict[str, Any]]) -> None:
        if case is None:
            return
        existing = {source["sha256"]: source for source in self.store.list_sources(case["id"])}
        by_name = {source["filename"]: source for source in existing.values()}
        conflicts = [
            _finding(document["filename"], "a different document is already active in this case under this filename")
            for document in documents
            if document["filename"] in by_name and by_name[document["filename"]]["sha256"] != document["sha256"]
        ]
        if conflicts:
            raise IntakeRefused("INTAKE_SOURCE_CONFLICT", "A document in the pack conflicts with an active source of this case.", conflicts)
        for document in documents:
            match = existing.get(document["sha256"])
            if match is not None:
                document["disposition"] = "duplicate"
                document["reason"] = f"already active in this case as {match['filename']}"
                document["source_id"] = match["id"]
                document["_first"] = False
                document["_prepared"].pop("id", None)

    def _apply_dispositions(self, documents: list[dict[str, Any]]) -> None:
        for document in documents:
            classification = document["_classification"]
            if document["disposition"] == "duplicate":
                continue
            if not classification["text_layer"]:
                document["disposition"] = "insufficient"
                document["reason"] = "no text layer could be extracted; the file is stored but carries no quotable evidence"
            elif classification.get("brief_error"):
                document["disposition"] = "insufficient"
                document["reason"] = f"research brief does not satisfy the brief contract ({classification['brief_error']})"
            else:
                document["reason"] = f"{document['document_type'].replace('_', ' ')} admitted as evidence"
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for document in documents:
            period = document.get("period")
            if document["disposition"] == "used" and period and document["document_type"] in {"annual_report", "quarterly_report"}:
                groups.setdefault((document["document_type"], period["label"]), []).append(document)
        for members in groups.values():
            if len(members) > 1 and any(member["version_status"] == "restated" for member in members):
                for member in members:
                    if member["version_status"] != "restated":
                        member["disposition"] = "superseded"
                        member["reason"] = "superseded by the restated document for the same period; retained and linked"

    def _manifest_row(self, document: dict[str, Any]) -> dict[str, Any]:
        return {
            "filename": document["filename"],
            "source_id": document["source_id"],
            "sha256": document["sha256"],
            "document_type": document["document_type"],
            "period": document["period"],
            "version_status": document["version_status"],
            "disposition": document["disposition"],
            "reason": document["reason"],
            "consumers": consumers_for(document["document_type"]) if document["disposition"] in {"used", "superseded"} else [],
            "confidence": document["confidence"],
            "signals": document["signals"],
        }

    def _import_market_marks(self, case_id: str, actor: str, documents: list[dict[str, Any]]) -> None:
        from ..artifacts.loan_universe import LoanUniverseImportRejected, LoanUniverseSourceError, import_loan_source

        for document in documents:
            if document["document_type"] == "market_marks" and document["disposition"] == "used" and document["source_id"]:
                try:
                    import_loan_source(self.store, case_id, document["source_id"], actor)
                except (LoanUniverseImportRejected, LoanUniverseSourceError, ValueError) as exc:
                    log_event("intake.market_marks_not_pinned", case_id=case_id, source_id=document["source_id"],
                              code=getattr(exc, "code", type(exc).__name__))

    async def _start(self, intake: dict[str, Any], *, actor: str, route: dict[str, Any], brief: dict[str, Any] | None) -> dict[str, Any]:
        """Start the selected route over the set just admitted. An engine
        refusal (no provider, admission ceiling, brief contract) is a typed
        state on the intake; the documents stay admitted."""
        if self.engine is None:
            return self._unavailable(intake, "RUN_ENGINE_UNAVAILABLE", "No run engine is attached to this instance.")
        try:
            run = await self.engine.start_run(
                case_id=intake["case_id"], pathway=route["pathway"], depth=route["depth"],
                actor=actor, research_brief=brief,
            )
        except EngineError as exc:
            log_event("intake.execution_unavailable", case_id=intake["case_id"], intake_id=intake["id"], code=exc.code)
            return self._unavailable(intake, exc.code, "The route could not be started on this instance.")
        return self.store.record_intake_run(intake["id"], actor, run_id=run["id"], pathway=route["pathway"])

    def _unavailable(self, intake: dict[str, Any], code: str, message: str) -> dict[str, Any]:
        return self.store.update_intake(intake["id"], status="execution_unavailable", refusal={
            "code": code, "message": message,
            "next_action": _NEXT_ACTIONS.get(code, "The documents are admitted; retry execution from the run console."),
            "findings": [],
        })
