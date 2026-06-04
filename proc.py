#!/usr/bin/env python3
"""
Poor man's literate programming preprocessor.

Input file list can be a mix of Markdown and Python files. These will be
processed in order and emitted as raw Markdown.

When processing a Python file:
- Top-level string literals are rendered as Markdown (pass-through verbatim).
- All other top-level statements are collected into fenced code blocks
  (```python ... ```) with leading and trailing blank lines stripped.

Example usage:

$ python3 proc.py --title 'Example usage' \
    preface.md example.py foo.py bar.py baz.py > example.md
"""

import ast
import textwrap
from pathlib import Path


def process_md(source: str, path: str | None = None) -> str:
    """Returns a Markdown document for one Python source file."""
    tree = ast.parse(source)
    source_lines = source.splitlines(keepends=True)
    parts: list[str] = []

    if path is not None:
        parts.append(f"# `{path}`")

    # Track line span of the current run of non-prose nodes.
    code_start: int | None = None
    code_end: int | None = None

    def flush_code() -> None:
        nonlocal code_start, code_end
        if code_start is None:
            return
        block = "".join(source_lines[code_start:code_end]).strip("\n")
        if block:
            parts.append("```python\n" + block + "\n```")
        code_start = code_end = None

    for node in tree.body:
        match node:
            case ast.Expr(value=ast.Constant(value=str() as s)):
                flush_code()
                parts.append(textwrap.dedent(s).strip())
            case _:
                if code_start is None:
                    code_start = node.lineno - 1  # type: ignore[attr-defined]
                code_end = node.end_lineno         # type: ignore[attr-defined]

    flush_code()
    return "\n\n".join(parts)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Poor man's literate programming preprocessor.",
        epilog="Example: %(prog)s --title 'My Docs' intro.md src/foo.py src/bar.py",
    )
    parser.add_argument(
        "-t",
        "--title",
        metavar="TITLE",
        default=None,
        help="document title",
    )
    parser.add_argument(
        "files", nargs="+", metavar="FILE", help="Markdown or Python source files to process"
    )
    args = parser.parse_args()

    chunks: list[str] = []
    if args.title:
        chunks.append(f"# {args.title}")
    for path in args.files:
        p = Path(path)
        if p.suffix == ".md":
            chunks.append(p.read_text().strip())
        else:
            chunks.append(process_md(p.read_text(), path))
    print("\n\n---\n\n".join(chunks) + "\n")  # noqa: T201
