#!/usr/bin/env python3
"""Mermaid architecture diagram of a diff: changed files as highlighted nodes, their import neighbours as plain nodes, edges from
imports. Written to docs/arch/<branch>.md so it travels with the commit and renders in the PR. CLI: archdiff.py [base] [--print].
--repo [path]: the current state instead of a diff, every module under path grouped into packages at --depth N (default 2),
edges weighted by import count, written to docs/arch/repo.md."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import state as st

SOURCE = {".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".scala", ".kt", ".go", ".rs"}
IMPORT = re.compile(r"^\s*(?:import\s+(?:[\w.{}, *]+\s+from\s+)?['\"]([\w./@-]+)|from\s+([\w.]+)\s+import\s+([\w., ]+)|import\s+([\w.]+))", re.M)
MAX_NEIGHBOURS = 12


def changed_files(root: Path, base: str) -> dict[str, tuple[int, int]]:
    """path -> (added, removed) for source files, base..working tree."""
    rows = st.git(root, "diff", "--numstat", base, "--").splitlines()
    out = {}
    for row in rows:
        parts = row.split("\t")
        if len(parts) == 3 and Path(parts[2]).suffix in SOURCE and parts[0].isdigit():
            out[parts[2]] = (int(parts[0]), int(parts[1]))
    return out


def module_of(path: str) -> str:
    return os.path.splitext(path)[0].replace("/", ".")


def imports_of(root: Path, path: str) -> set[str]:
    try:
        text = (root / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    found = set()
    for quoted, package, names, plain in IMPORT.findall(text):
        found.update([quoted, plain, package] if not names else [package, *(f"{package}.{n.strip()}" for n in names.split(",") if n.strip())])
    return {f.lstrip("./").replace("/", ".") for f in found if f}


def resolve(target: str, known: dict[str, str]) -> str | None:
    """Map an import string to a known module name by suffix match, so 'app.models' finds 'src.app.models'."""
    return next((m for m in known if m == target or m.endswith("." + target) or target.endswith("." + m.rsplit(".", 1)[-1]) and m.endswith(target)), None)


class Graph(NamedTuple):
    changed: dict  # path -> (added, removed)
    nodes: dict  # module -> path
    edges: set  # (module, module)


def graph(root: Path, changed: dict[str, tuple[int, int]]) -> Graph:
    """Nodes (module -> path) and edges among changed files and the files they import, bounded."""
    tracked = [p for p in st.git(root, "ls-files").splitlines() if Path(p).suffix in SOURCE]
    known = {module_of(p): p for p in tracked}
    nodes, edges = {module_of(p): p for p in changed}, set()
    for path in changed:
        for target in imports_of(root, path):
            hit = resolve(target, known)
            if hit and hit != module_of(path):
                edges.add((module_of(path), hit))
                if hit not in nodes and len(nodes) < len(changed) + MAX_NEIGHBOURS:
                    nodes[hit] = known[hit]
    return Graph(changed, nodes, edges)


def render(title: tuple[str, str], g: Graph) -> str:
    (branch, base), changed, nodes, edges = title, g.changed, g.nodes, g.edges
    ident = {m: f"n{i}" for i, m in enumerate(sorted(nodes))}
    lines = [f"# Architecture of the change on `{branch}`", "", f"Base `{base}`. Highlighted nodes changed; plain nodes are the modules they import.", "", "```mermaid", "flowchart LR"]
    for m in sorted(nodes):
        label = m.rsplit(".", 1)[-1] + (f" (+{changed[nodes[m]][0]}/-{changed[nodes[m]][1]})" if nodes[m] in changed else "")
        lines.append(f'  {ident[m]}["{label}"]')
    lines += [f"  {ident[a]} --> {ident[b]}" for a, b in sorted(edges) if a in ident and b in ident]
    lines += [f"  style {ident[m]} fill:#ffe08a,stroke:#b8860b" for m in sorted(nodes) if nodes[m] in changed]
    lines += ["```", "", "| File | +/- |", "|---|---|"] + [f"| `{p}` | +{a}/-{r} |" for p, (a, r) in sorted(changed.items())]
    return "\n".join(lines) + "\n"


def write(root: Path, branch: str, text: str) -> Path:
    target = root / "docs" / "arch" / f"{branch.replace('/', '-')}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return target.relative_to(root)


def package_of(path: str, depth: int) -> str:
    """Depth 0 is file level (one node per module); otherwise the directory prefix at that depth."""
    if depth == 0:
        return os.path.splitext(path)[0]
    return "/".join(Path(path).parent.parts[:depth]) or "."


def repo_graph(root: Path, scope: str, depth: int) -> tuple[dict[str, int], dict[tuple[str, str], int]]:
    """Packages (path prefix at depth) with file counts, and import edges between packages with counts; self-edges dropped."""
    tracked = [p for p in st.git(root, "ls-files", "--", scope).splitlines() if Path(p).suffix in SOURCE]
    known = {module_of(p): p for p in st.git(root, "ls-files").splitlines() if Path(p).suffix in SOURCE}
    sizes: dict[str, int] = {}
    edges: dict[tuple[str, str], int] = {}
    for path in tracked:
        src = package_of(path, depth)
        sizes[src] = sizes.get(src, 0) + 1
        for target in imports_of(root, path):
            hit = resolve(target, known)
            dst = package_of(known[hit], depth) if hit else None
            if dst and dst != src and known[hit].startswith(scope.rstrip("/") if scope != "." else ""):
                edges[(src, dst)] = edges.get((src, dst), 0) + 1
    return sizes, edges


def render_repo(title: tuple[str, int], sizes: dict[str, int], edges: dict[tuple[str, str], int]) -> str:
    scope, depth = title
    ident = {p: f"p{i}" for i, p in enumerate(sorted(sizes))}
    lines = [f"# Module map of `{scope}`", "", ("One node per module" if depth == 0 else f"Packages at depth {depth} with their file counts") + "; an edge is an import, labelled with how many.", "", "```mermaid", "flowchart LR"]
    lines += [f'  {ident[p]}["{p} ({n})"]' for p, n in sorted(sizes.items())]
    lines += [f"  {ident[a]} -->|{n}| {ident[b]}" for (a, b), n in sorted(edges.items()) if a in ident and b in ident]
    lines += ["```"]
    if len(sizes) > 30:
        lines += ["", f"{len(sizes)} packages: rerun with a smaller --depth or a narrower path for a readable picture."]
    return "\n".join(lines) + "\n"


def repo_main(argv: list[str]) -> int:
    root = st.root()
    rest = argv[argv.index("--repo") + 1:]
    scope = next((a for a in rest if not a.startswith("--") and not a.isdigit()), ".")
    depth = int(argv[argv.index("--depth") + 1]) if "--depth" in argv else 2
    sizes, edges = repo_graph(root, scope, depth)
    text = render_repo((scope, depth), sizes, edges)
    if "--print" in argv:
        print(text)
    else:
        print(f"archdiff: wrote {write(root, 'repo', text)} ({len(sizes)} packages, {len(edges)} edges)")
    return 0


def main(argv: list[str]) -> int:
    return repo_main(argv) if "--repo" in argv else diff_main(argv)


def diff_main(argv: list[str]) -> int:
    root, state = st.root(), st.load()
    base = next((a for a in argv if not a.startswith("--")), None) or state.get("base_sha") or "HEAD"
    branch = st.git(root, "rev-parse", "--abbrev-ref", "HEAD").strip() or "work"
    changed = changed_files(root, base)
    if not changed:
        print("archdiff: no source changes against the base")
        return 0
    g = graph(root, changed)
    text = render((branch, base[:12]), g)
    if "--print" in argv:
        print(text)
    else:
        print(f"archdiff: wrote {write(root, branch, text)} ({len(g.changed)} changed files, {len(g.nodes)} nodes, {len(g.edges)} edges); git add it with the commit")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
