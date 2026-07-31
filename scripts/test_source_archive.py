#!/usr/bin/env python3
"""Extract the source release and run its archive-mode Python contracts."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "build" / "release" / "VARP_K26_Source.zip"


def main() -> int:
    if not ARCHIVE.is_file():
        raise SystemExit(f"missing source release: {ARCHIVE}")
    with tempfile.TemporaryDirectory(prefix="varp-source-archive-") as temporary:
        target = Path(temporary)
        with zipfile.ZipFile(ARCHIVE) as archive:
            for member in archive.infolist():
                destination = (target / member.filename).resolve()
                if not destination.is_relative_to(target.resolve()):
                    raise SystemExit(f"unsafe archive member: {member.filename}")
            archive.extractall(target)
        subprocess.run(["make", "test"], cwd=target, check=True)
        subprocess.run(
            ["python3", "scripts/verify_clean_source.py"],
            cwd=target,
            check=True,
        )
    print("source_archive_test=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
