#!/usr/bin/env python3
"""Generate the Phase-A toolchain audit without installing or mutating tools."""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "build" / "doctor"
ACCESS_DATE = date(2026, 7, 31).isoformat()


def run(*cmd: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
        return proc.returncode, proc.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def first_line(text: str) -> str:
    return text.splitlines()[0] if text else ""


def binary(tool: str, args: tuple[str, ...], *, version_pattern: str | None = None) -> dict:
    path = shutil.which(tool)
    if path is None:
        return {
            "status": "missing",
            "version": None,
            "path": None,
            "evidence_type": "host_command_probe",
            "evidence": f"command -v {tool}: not found",
        }
    rc, output = run(path, *args)
    version = first_line(output)
    if version_pattern:
        match = re.search(version_pattern, output)
        version = match.group(1) if match else version
    return {
        "status": "available" if rc == 0 else "available_probe_limited",
        "version": version,
        "path": path,
        "evidence_type": "host_command_probe",
        "evidence": first_line(output),
    }


def python_package(dist: str, module_label: str) -> dict:
    try:
        version = importlib.metadata.version(dist)
        return {
            "status": "available",
            "version": version,
            "path": shutil.which("python3"),
            "evidence_type": "python_distribution_metadata",
            "evidence": f"{module_label} distribution={dist} version={version}",
        }
    except importlib.metadata.PackageNotFoundError:
        return {
            "status": "missing",
            "version": None,
            "path": shutil.which("python3"),
            "evidence_type": "python_distribution_metadata",
            "evidence": f"{module_label} distribution={dist}: not installed",
        }


def configured(name: str, version: str, source: str) -> dict:
    return {
        "status": "configured",
        "version": version,
        "path": source,
        "evidence_type": "repository_configuration",
        "evidence": f"{name} locked in {source}",
    }


def debian_package(tool: str, package: str) -> dict:
    path = shutil.which(tool)
    rc, output = run("dpkg-query", "-W", "-f=${Version}", package)
    if path is None:
        return {
            "status": "missing",
            "version": None,
            "path": None,
            "evidence_type": "debian_package_probe",
            "evidence": f"command -v {tool}: not found",
        }
    return {
        "status": "available" if rc == 0 else "available_version_unresolved",
        "version": output if rc == 0 else None,
        "path": path,
        "evidence_type": "debian_package_probe",
        "evidence": f"dpkg package {package}={output}" if rc == 0 else output,
    }


def dramsim3() -> dict:
    candidates = [
        Path(os.environ.get("DRAMSIM3_ROOT", "")),
        ROOT / "build" / "deps" / "DRAMsim3",
    ]
    root = next(
        (
            p.resolve()
            for p in candidates
            if str(p) and (p / "src" / "memory_system.h").is_file()
        ),
        None,
    )
    if root is None:
        return {
            "status": "missing",
            "version": None,
            "path": None,
            "evidence_type": "filesystem_and_git_probe",
            "evidence": "no DRAMsim3 source tree with src/memory_system.h found",
        }
    rc, commit = run("git", "-C", str(root), "rev-parse", "HEAD")
    lib = root / "libdramsim3.so"
    return {
        "status": "available" if rc == 0 and lib.is_file() else "source_only",
        "version": commit if rc == 0 else None,
        "path": str(root),
        "evidence_type": "filesystem_and_git_probe",
        "evidence": f"commit={commit}; shared_library={lib.is_file()}",
        "note": "Tree includes the repository instrumentation patch; it is not a pristine upstream checkout.",
    }


def main() -> int:
    lock = json.loads((ROOT / "configs" / "toolchains" / "versions.json").read_text())
    build = (ROOT / "build.sbt").read_text()
    scala = re.search(r'scalaVersion := "([^"]+)"', build).group(1)
    spinal = re.search(r'lazy val spinalVersion = "([^"]+)"', build).group(1)

    tools = {
        "Java": binary("java", ("-version",), version_pattern=r'version "([^"]+)"'),
        "Scala": configured("Scala", scala, "build.sbt"),
        "sbt": binary("sbt", ("--version",), version_pattern=r"project: ([0-9.]+)"),
        "SpinalHDL": configured("SpinalHDL", spinal, "build.sbt"),
        "Verilator": binary("verilator", ("--version",), version_pattern=r"Verilator ([0-9.]+)"),
        "DRAMsim3": dramsim3(),
        "Python": binary("python3", ("--version",), version_pattern=r"Python ([0-9.]+)"),
        "ONNX": python_package("onnx", "onnx"),
        "ONNX Runtime": python_package("onnxruntime", "onnxruntime"),
        "Vivado": binary("vivado", ("-version",)),
        "Vivado device files": {
            "status": "blocked",
            "version": None,
            "path": None,
            "evidence_type": "dependency_gate",
            "evidence": "cannot inspect device files because Vivado is missing",
        },
        "Vivado license": {
            "status": "blocked",
            "version": None,
            "path": None,
            "evidence_type": "dependency_gate",
            "evidence": "license checkout not attempted because Vivado is missing",
        },
        "KiCad": binary("kicad-cli", ("--version",)),
        "kicad-cli": binary("kicad-cli", ("--version",)),
        "GTKWave": debian_package("gtkwave", "gtkwave"),
        "Graphviz": binary("dot", ("-V",)),
        "ffmpeg": binary("ffmpeg", ("-version",)),
        "ImageMagick": binary("convert", ("-version",)),
        "Pandoc": binary("pandoc", ("--version",)),
        "LibreOffice": binary("libreoffice", ("--version",)),
        "python-pptx": python_package("python-pptx", "pptx"),
        "PptxGenJS": {
            "status": "missing",
            "version": None,
            "path": shutil.which("node"),
            "evidence_type": "npm_global_inventory",
            "evidence": "PptxGenJS absent from npm list -g --depth=0",
        },
        "gh CLI": binary("gh", ("--version",)),
        "Git LFS": binary("git-lfs", ("version",)),
    }
    required = list(tools)
    unavailable = [
        name
        for name in required
        if tools[name]["status"] in {"missing", "blocked"}
        and not (name == "PptxGenJS" and tools["python-pptx"]["status"] == "available")
    ]
    payload = {
        "schema_version": "varp.phase-a-doctor.v1",
        "audit_date": ACCESS_DATE,
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python_executable": shutil.which("python3"),
        },
        "lock_reference": {
            "path": "configs/toolchains/versions.json",
            "platform": lock["platform"],
        },
        "tools": tools,
        "summary": {
            "required_or_requested_count": len(required),
            "unavailable_or_blocked": unavailable,
            "full_phase_a_toolchain_ready": not unavailable,
            "presentation_generator_ready": (
                tools["python-pptx"]["status"] == "available"
                or tools["PptxGenJS"]["status"] == "available"
            ),
            "power_evidence_ceiling": (
                "analytical_range_only; Vivado synthesis/place-route/report_power blocked"
            ),
        },
        "claim_boundary": (
            "Availability proves only that a command/package was observed or configured. "
            "It does not prove design compatibility, successful model execution, FPGA "
            "implementation, timing closure, or measured power."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "DOCTOR.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )

    rows = []
    for name, item in tools.items():
        rows.append(
            f"| {name} | {item['status']} | {item.get('version') or '—'} | "
            f"`{item.get('path') or '—'}` | {item['evidence_type']} | "
            f"{item['evidence'].replace('|', '/')} |"
        )
    matrix = f"""# Phase-A toolchain compatibility matrix

Audit date: {ACCESS_DATE}

This is a host-observation matrix, not a compatibility certification. `available`
means the executable or Python distribution was observed. `configured` means the
repository locks the dependency but this audit did not independently execute it.
`blocked` means a prerequisite was absent. Evidence types are explicit so the
paper cannot silently promote a configuration string into executed evidence.

| Tool | Status | Version | Path | Evidence type | Evidence |
|---|---|---:|---|---|---|
{chr(10).join(rows)}

## Power and implementation consequence

Vivado, its device database, and a license checkout are unavailable. Consequently,
MIG generation, synthesis, placement/routing, SAIF-based analysis, timing closure,
and `report_power` remain **blocked**. The bounded model in
`results/power_cost/` is therefore labeled `analytical-range`; it is not board
measurement or post-route power.

## Notable non-blocking alternatives

- `python-pptx` is available, while PptxGenJS is not.
- ImageMagick 6 is available through `convert`; the ImageMagick 7 `magick`
  wrapper is not required by this audit.
- DRAMsim3 is probed only at `DRAMSIM3_ROOT` or `build/deps/DRAMsim3`.
  This public repository does not contain or silently depend on a sibling checkout.

## Evidence interpretation

The generated machine-readable record is `build/doctor/DOCTOR.json`. Missing Graphviz,
LibreOffice, Git LFS, Vivado, and Vivado licensing must not be described as
successful. KiCad availability does not by itself prove ERC/DRC, and ONNX package
availability does not prove that the requested Gemma model artifact exists.
"""
    (OUT_DIR / "COMPATIBILITY_MATRIX.md").write_text(matrix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
