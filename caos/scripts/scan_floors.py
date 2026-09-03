#!/usr/bin/env python3
"""Non-vacuity floors for the CI security scanners (ENTERPRISE_TESTING_READINESS
SEC-001, SEC-002; Phase 6 items 5 and 6).

A scanner that scanned nothing exits 0 exactly like a clean one: bandit skips
files it cannot parse, gitleaks reports "no leaks found" over a directory that
is not a git checkout, Trivy scans an image with no packages, pip-audit and
npm audit audit an empty dependency set. Each subcommand reads the scanner's
own machine-readable report and refuses when it covered less than the declared
floor, and `manifest` binds every retained report to the commit and the image
identities it was produced from, so the retained evidence is non-empty and
addressed. Standard library only.

    scan_floors.py bandit <report.json>
    scan_floors.py pip-audit <report.json>
    scan_floors.py npm-audit <report.json>
    scan_floors.py gitleaks <report.json-or-absent> --log <stderr.log>
    scan_floors.py trivy <report.json> --image-id <docker image id>
    scan_floors.py sbom <bom.cdx.json> --image <image ref>
    scan_floors.py manifest <out.json> --commit <sha> --image name=id … --report name=path …
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Floors are deliberately far below the real figures (the server is ~10k
# lines, the image carries several hundred packages) so a routine change never
# trips them and losing the target always does.
FLOORS = {
    "bandit": 5_000,      # lines of Python scanned
    "pip-audit": 40,      # dependencies audited
    "npm-audit": 100,     # dependencies audited
    "gitleaks": 1,        # commits scanned
    "trivy": 100,         # packages inventoried
    "sbom": 100,          # components
}


class Floor(Exception):
    pass


def _load(path: str) -> dict | list:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def bandit(path: str, floor: int) -> str:
    report = _load(path)
    errors = report.get("errors", [])
    if errors:
        raise Floor(f"bandit could not parse {len(errors)} file(s) and still exited 0: "
                    f"{[e.get('filename') for e in errors][:5]}")
    loc = report["metrics"]["_totals"]["loc"]
    if loc < floor:
        raise Floor(f"bandit scanned only {loc} lines (floor {floor}) - the gate lost its target")
    return f"bandit scanned {loc} lines with no parse errors"


def pip_audit(path: str, floor: int) -> str:
    report = _load(path)
    dependencies = report["dependencies"] if isinstance(report, dict) else report
    vulnerable = [d["name"] for d in dependencies if d.get("vulns")]
    if vulnerable:
        raise Floor(f"pip-audit reports vulnerabilities in {vulnerable}")
    if len(dependencies) < floor:
        raise Floor(f"pip-audit audited only {len(dependencies)} dependencies (floor {floor})")
    return f"pip-audit audited {len(dependencies)} dependencies, none vulnerable"


def npm_audit(path: str, floor: int) -> str:
    report = _load(path)
    total = report["metadata"]["dependencies"]["total"]
    if total < floor:
        raise Floor(f"npm audit covered only {total} dependencies (floor {floor})")
    counts = report["metadata"].get("vulnerabilities", {})
    return f"npm audit covered {total} dependencies (high {counts.get('high', 0)}, critical {counts.get('critical', 0)})"


def gitleaks(path: str, floor: int, log: str) -> str:
    text = Path(log).read_text(encoding="utf-8", errors="replace")
    if re.search(r"\bERR\b", text):
        raise Floor("gitleaks logged an error and its exit code hid it: " + text.strip().splitlines()[-1][:200])
    match = re.search(r"(\d+) commits scanned", text)
    if not match or int(match.group(1)) < floor:
        raise Floor("gitleaks did not report the commits it scanned - it was not looking at a git history")
    if Path(path).exists():
        findings = _load(path)
        if not isinstance(findings, list):
            raise Floor("gitleaks report is not a JSON list")
        if findings:
            raise Floor(f"gitleaks reported {len(findings)} finding(s)")
    return f"gitleaks scanned {match.group(1)} commits with no findings"


def trivy(path: str, floor: int, image_id: str) -> str:
    report = _load(path)
    observed = report.get("Metadata", {}).get("ImageID")
    if observed != image_id:
        raise Floor(f"trivy scanned image {observed}, not the built image {image_id}")
    packages = sum(len(result.get("Packages", [])) for result in report.get("Results", []))
    if packages < floor:
        raise Floor(f"trivy inventoried only {packages} packages (floor {floor}) - pass --list-all-pkgs")
    return f"trivy inventoried {packages} packages of image {image_id[:19]}…"


def sbom(path: str, floor: int, image: str) -> str:
    bom = _load(path)
    if bom.get("bomFormat") != "CycloneDX":
        raise Floor("the SBOM is not CycloneDX")
    subject = bom.get("metadata", {}).get("component", {}).get("name", "")
    if image not in subject:
        raise Floor(f"the SBOM describes {subject!r}, not {image!r}")
    components = len(bom.get("components", []))
    if components < floor:
        raise Floor(f"the SBOM lists only {components} components (floor {floor})")
    return f"SBOM for {subject} lists {components} components"


def manifest(out: str, commit: str, images: list[str], reports: list[str]) -> str:
    def digest(file: Path) -> dict[str, object]:
        data = file.read_bytes()
        if not data:
            raise Floor(f"retained report {file} is empty")
        return {"file": file.name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

    payload = {
        "schema_version": "caos.scan-manifest.v1",
        "commit": commit,
        "images": dict(pair.split("=", 1) for pair in images),
        "reports": {name: digest(Path(file)) for name, file in (pair.split("=", 1) for pair in reports)},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if not payload["images"] or not payload["reports"]:
        raise Floor("a scan manifest binds at least one image and one report")
    Path(out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return f"scan manifest binds {len(payload['reports'])} reports to {len(payload['images'])} image(s) at {commit[:12]}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("scanner", choices=[*FLOORS, "manifest"])
    parser.add_argument("path")
    parser.add_argument("--floor", type=int)
    parser.add_argument("--log")
    parser.add_argument("--image-id")
    parser.add_argument("--image", action="append", default=[])
    parser.add_argument("--commit")
    parser.add_argument("--report", action="append", default=[])
    args = parser.parse_args(argv)
    floor = args.floor if args.floor is not None else FLOORS.get(args.scanner, 0)
    try:
        if args.scanner == "bandit":
            message = bandit(args.path, floor)
        elif args.scanner == "pip-audit":
            message = pip_audit(args.path, floor)
        elif args.scanner == "npm-audit":
            message = npm_audit(args.path, floor)
        elif args.scanner == "gitleaks":
            if not args.log:
                parser.error("gitleaks needs --log")
            message = gitleaks(args.path, floor, args.log)
        elif args.scanner == "trivy":
            if not args.image_id:
                parser.error("trivy needs --image-id")
            message = trivy(args.path, floor, args.image_id)
        elif args.scanner == "sbom":
            if len(args.image) != 1:
                parser.error("sbom needs exactly one --image")
            message = sbom(args.path, floor, args.image[0])
        else:
            if not args.commit:
                parser.error("manifest needs --commit")
            message = manifest(args.path, args.commit, args.image, args.report)
    except (Floor, KeyError, ValueError, OSError) as exc:
        print(f"FAIL {args.scanner}: {exc}", file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
