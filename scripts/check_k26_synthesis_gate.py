#!/usr/bin/env python3
"""Record the honest synthesis/tool gate for the paper-target RTL."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERILOG = ROOT / "build" / "k26-rtl" / "K26WorkStealingTop.v"
OUT = ROOT / "results" / "synthesis"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if not VERILOG.is_file():
        raise SystemExit(
            "missing generated RTL; run `make k26-rtl` before this gate"
        )

    tools = {
        name: shutil.which(name)
        for name in ("vivado", "yosys", "nextpnr-xilinx", "verilator")
    }
    vivado_available = tools["vivado"] is not None
    payload = {
        "schema_version": 1,
        "evidence_type": "rtl-elaboration",
        "paper_target": {
            "top": "K26WorkStealingTop",
            "clusters": 4,
            "memory_channels": 4,
            "link_bundles": 4,
            "scheduler": "S3 locality-aware work stealing",
            "preferred_device_rejected": "XC7A100T-2FGG676I",
            "conditional_reference_device": "XC7K160T-2FFG676I",
        },
        "generated_verilog": {
            "path": str(VERILOG.relative_to(ROOT)),
            "sha256": sha256(VERILOG),
            "line_count": sum(1 for _ in VERILOG.open(encoding="utf-8")),
        },
        "tools": tools,
        "synthesis_status": "not_run" if not vivado_available else "available_not_run",
        "gate_status": "blocked" if not vivado_available else "requires_execution",
        "blocked_claims": [
            "post-synthesis LUT/FF/BRAM/DSP utilization",
            "post-route timing closure and maximum clock frequency",
            "MIG pin legality for one, two, and four DDR3L x16 channels",
            "GT placement and K26 carrier signal-integrity closure",
        ],
        "allowed_claims": [
            "SpinalHDL elaboration for 1/2/4 clusters, channels, and bundles",
            "Verilator functional regression of the integrated real MatVec path",
            "portable RTL generation for the conditional reference device",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    json_path = OUT / "synthesis_gate.json"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    report = f"""# K26 paper-target synthesis gate

- Gate: **{payload['gate_status']}**
- Evidence type: `{payload['evidence_type']}`
- Generated top: `{payload['paper_target']['top']}`
- Generated Verilog: `{payload['generated_verilog']['path']}`
- SHA-256: `{payload['generated_verilog']['sha256']}`
- Lines: {payload['generated_verilog']['line_count']}
- Conditional reference device: `{payload['paper_target']['conditional_reference_device']}`

Vivado is {'available, but a device/MIG implementation has not been run' if vivado_available else 'not installed in this environment'}. Therefore no utilization,
timing-closure, MIG-legality, or physical-link claim is made. Verilator is used
only for functional RTL validation and is not a substitute for AMD synthesis.
The exact machine-readable gate and tool paths are in `synthesis_gate.json`.
"""
    (OUT / "README.md").write_text(report, encoding="utf-8")
    print(f"synthesis gate: {payload['gate_status']}")


if __name__ == "__main__":
    main()
