#!/usr/bin/env python3
"""Exercise the GitHub auto-ZIP fallback using a manifest-free git archive."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="varp-github-archive-") as temporary:
        target = Path(temporary)
        archive_path = target / "source.tar"
        with archive_path.open("wb") as stream:
            subprocess.run(
                ["git", "archive", "HEAD"], cwd=ROOT, check=True, stdout=stream
            )
        extract_root = target / "tree"
        extract_root.mkdir()
        with tarfile.open(archive_path) as archive:
            archive.extractall(extract_root, filter="data")
        if (extract_root / ".git").exists() or (
            extract_root / "source_manifest.txt"
        ).exists():
            raise SystemExit("fallback smoke must have neither .git nor manifest")
        subprocess.run(["make", "test"], cwd=extract_root, check=True)
        subprocess.run(
            ["make", "publication-index"], cwd=extract_root, check=True
        )
    print("github_archive_test=PASS mode=fallback-tree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
