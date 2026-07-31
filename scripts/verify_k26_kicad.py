#!/usr/bin/env python3
"""Run native KiCad checks without rewriting committed exports."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COUPON = (
    ROOT
    / "hardware/kicad/k26_memory_coupon/k26_memory_coupon.kicad_sch"
)
PCB = (
    ROOT
    / "hardware/kicad/k26_memory_coupon/k26_memory_coupon.kicad_pcb"
)
REFERENCE = (
    ROOT
    / "hardware/kicad/k26_memory_reference/k26_memory_reference.kicad_sch"
)


def run(*arguments: str) -> None:
    completed = subprocess.run(
        ["kicad-cli", *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )
    if completed.returncode:
        raise SystemExit(
            f"KiCad command failed ({completed.returncode}): "
            + " ".join(arguments)
            + "\n"
            + completed.stdout
            + completed.stderr
        )


def violations(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return len(payload.get("violations", []))


def main() -> None:
    if shutil.which("kicad-cli") is None:
        raise SystemExit("kicad-cli is required for the native gate")
    with tempfile.TemporaryDirectory(prefix="varp-k26-kicad-") as temporary:
        out = Path(temporary)
        coupon_erc = out / "coupon_erc.json"
        reference_erc = out / "reference_erc.json"
        coupon_drc = out / "coupon_drc.json"
        run(
            "sch",
            "erc",
            "--exit-code-violations",
            "--format",
            "json",
            "--output",
            str(coupon_erc),
            str(COUPON),
        )
        run(
            "sch",
            "erc",
            "--exit-code-violations",
            "--format",
            "json",
            "--output",
            str(reference_erc),
            str(REFERENCE),
        )
        run(
            "pcb",
            "drc",
            "--exit-code-violations",
            "--schematic-parity",
            "--format",
            "json",
            "--output",
            str(coupon_drc),
            str(PCB),
        )
        counts = {
            "coupon_erc": violations(coupon_erc),
            "reference_erc": violations(reference_erc),
            "coupon_drc": violations(coupon_drc),
        }
        if any(counts.values()):
            raise SystemExit(f"KiCad native gate failed: {counts}")
        print(
            "KiCad native gate: PASS "
            "(coupon ERC=0, reference ERC=0, coupon DRC/parity=0)"
        )


if __name__ == "__main__":
    main()
