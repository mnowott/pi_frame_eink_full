#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

DEFAULT_EXTS = {".py", ".sh", ".bash", ".toml"}
DEFAULT_EXCLUDE_DIRS = {
    ".git", ".hg", ".svn",
    ".venv", "venv", "env", "test",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "node_modules", "dist", "build", ".tox",
}

TEXT_BANNER = "=" * 88


def is_probably_text(path: Path, sample_bytes: int = 4096) -> bool:
    """
    Quick heuristic: treat files with NUL bytes as binary.
    """
    try:
        with path.open("rb") as f:
            chunk = f.read(sample_bytes)
        return b"\x00" not in chunk
    except OSError:
        return False


def iter_script_files(
    root: Path,
    exts: set[str],
    exclude_dirs: set[str],
    include_no_ext_shebang: bool = True,
) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # prune excluded directories in-place
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

        for name in filenames:
            p = Path(dirpath) / name

            # Skip if not readable or likely binary
            if not is_probably_text(p):
                continue

            if "tests/" in str(p):
                continue

            if p.suffix in exts:
                yield p
                continue

            if include_no_ext_shebang and p.suffix == "":
                # Check for bash/python shebang
                try:
                    with p.open("r", encoding="utf-8", errors="replace") as f:
                        first = f.readline().strip()
                    if first.startswith("#!"):
                        if "python" in first or "bash" in first or "sh" in first:
                            yield p
                except OSError:
                    continue


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Collect all Python/Bash scripts under root into a single document with paths + content."
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Root directory to scan (default: current directory).",
    )
    ap.add_argument(
        "-o",
        "--output",
        default="ALL_SCRIPTS.txt",
        help="Output file (default: ALL_SCRIPTS.txt).",
    )
    ap.add_argument(
        "--ext",
        action="append",
        default=[],
        help="Additional extension(s) to include (repeatable), e.g. --ext .zsh",
    )
    ap.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name(s) to exclude (repeatable), e.g. --exclude-dir .terraform",
    )
    ap.add_argument(
        "--no-shebang",
        action="store_true",
        help="Do NOT include executable scripts with no extension based on shebang.",
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.output).resolve()

    exts = set(DEFAULT_EXTS)
    for e in args.ext:
        exts.add(e if e.startswith(".") else f".{e}")

    exclude_dirs = set(DEFAULT_EXCLUDE_DIRS)
    exclude_dirs.update(args.exclude_dir)

    files = sorted(
        iter_script_files(
            root=root,
            exts=exts,
            exclude_dirs=exclude_dirs,
            include_no_ext_shebang=not args.no_shebang,
        ),
        key=lambda p: str(p).lower(),
    )

    with out.open("w", encoding="utf-8", errors="replace", newline="\n") as w:
        w.write(f"{TEXT_BANNER}\n")
        w.write(f"Collected scripts under: {root}\n")
        w.write(f"Extensions: {sorted(exts)}\n")
        w.write(f"Excluded dirs: {sorted(exclude_dirs)}\n")
        w.write(f"Files found: {len(files)}\n")
        w.write(f"{TEXT_BANNER}\n\n")

        for p in files:
            rel = p.relative_to(root)
            try:
                content = read_text(p)
            except Exception as ex:
                content = f"<<ERROR reading file: {ex}>>"

            w.write(f"{TEXT_BANNER}\n")
            w.write(f"FILE: {rel}\n")
            w.write(f"{TEXT_BANNER}\n")
            w.write(content)
            if not content.endswith("\n"):
                w.write("\n")
            w.write("\n")

    print(f"Wrote {len(files)} files to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
