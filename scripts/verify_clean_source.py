#!/usr/bin/env python3
"""Fail when reproduction changes versioned source or archive payload files."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    probe = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0 and probe.stdout.strip() == "true":
        whitespace = subprocess.run(["git", "diff", "--check"], cwd=ROOT)
        diff = subprocess.run(["git", "diff", "--exit-code"], cwd=ROOT)
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if whitespace.returncode or diff.returncode or status:
            if status:
                print(status)
            raise SystemExit("reproduction changed the Git worktree")
        print("source_clean_gate=PASS mode=git")
        return 0

    manifest = ROOT / "source_manifest.txt"
    if not manifest.is_file():
        raise SystemExit(
            "not a Git worktree and source_manifest.txt is missing"
        )
    failures: list[str] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"missing: {relative}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            failures.append(f"changed: {relative}")
    if failures:
        raise SystemExit("archive source clean gate failed:\n" + "\n".join(failures))
    print("source_clean_gate=PASS mode=archive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
