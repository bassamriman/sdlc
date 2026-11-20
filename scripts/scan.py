#!/usr/bin/env python3
"""PostToolUse(Edit|Write): standards scan of the edited file plus slice-size and plan-drift warnings. Findings to stderr, exit 2."""
from __future__ import annotations

import ast
import json
import os
import re
import sys

import record
import state as st

MAX_LINES, MAX_PARAMS, MAX_FINDINGS = 15, 3, 8
SLICE_LINES, SLICE_FILES = 120, 6
SLICE_SKIP = re.compile(r"^(docs/|tests?/|__tests__/)")
DENSITY_MIN_LINES, DENSITY = 40, 0.3
SOURCE = {".py", ".ts", ".tsx", ".js", ".jsx", ".scala", ".java", ".kt", ".go", ".rs"}
HISTORY = re.compile(
    r"\b(changed\b.+\bto\b|renamed from\b|moved from\b|was (changed|moved|renamed|removed|replaced)\b"
    r"|old (code|version|implementation|behaviou?r)\b|\b(previously|used to|no longer|now (uses|returns|calls|does))\b)", re.I)
NEGATIVE = re.compile(r"\b(could(n't| not)|can't|cannot|tried|didn't work|doesn't work|hack(y)?|for now|temporar(y|ily)|don'?t touch|do not touch|not sure|I think)\b", re.I)
WHY = re.compile(r"\b(because|since(?!\s+(v?\d|\w+\s+\d{4}))|so that|to avoid|otherwise|on purpose|intentionally|workaround)\b", re.I)
TODO = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
TICKET = re.compile(r"[A-Z][A-Z0-9]+-\d+|#\d+|https?://")
PRAGMA = re.compile(r"noqa|type:\s*ignore|pragma|eslint-|pylint:|prettier-|@ts-|nolint|clippy::|SPDX|Copyright|Licen[sc]e", re.I)
DOC_TAG = r"(?!(param|return|returns|throws|see|since|author|deprecated|inheritDoc|link|code|version)\b)"
CODE_SHAPES = (
    r"^(import|from)\s+[\w.]+(\s+import\s+[\w.*, ]+)?$",
    r"^(def|fn|func|function|fun)\s+\w+\s*\(",
    r"^class\s+\w+\s*[(:{]",
    r"^(if|elif|while)\s+(?!(the|a|an|this|that|we|it|you)\b)[^,]*?(==|!=|<=|>=|<|>|\(|\w\.\w|\bnot\b|\bis\b|\band\b|\bor\b)[^,]*[:{]$",
    r"^(if|elif|while)\s+\(.*\)\s*\{$",
    r"^else\s*[:{]$",
    r"^for\s+(\(.*\)\s*\{$|\w+(\s*,\s*\w+)*\s+in\s+[\w.()\[\]'\"]+\s*:$|\w+\s*:=)",
    r"^return\b.*;$|^return\s+\S+$",
    r"^[\w.\[\]]+\s*(=|\+=|-=)\s*\S.*(\(|\[|\{|;$|\d$|['\"]$)",
    r"^[\w.]+\(.*\)\s*;?$",
    r"[;{}]$",
    r"^(raise|await)\s+[\w.]+(\(|$)",
    r"^with\s+.+\bas\b.+:$",
    r"^(try|finally|else):$",
    r"^except\b.*:$",
    r"^(break|continue|pass)$",
    r"^yield(\s+[\w.\[\]()]+)?$",
    r"^@" + DOC_TAG + r"\w+(\.\w+)*(\(.*\))?$",
    r"^(const|let|var)\s+\w+\s*=",
    r"^export\s+(default|const|function|class|async)\b",
)
CODEISH = re.compile("|".join(f"(?:{s})" for s in CODE_SHAPES))
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__)/|(^|/)test_|_test\.|\.test\.|\.spec\.")
DOC_COMMENT = re.compile(r"^\s*(///|//!|/\*\*)")  # doc comments on contracts are wanted (rule 16): judged, never counted toward density
SECRET = re.compile(r"""(?i)\b\w*(secret|password|passwd|api[_-]?key|access[_-]?key|token)\w*\s*[:=]\s*["'][^"'\s]{8,}["']""")
MUTABLE_CALLS = {"list", "dict", "set"}


def block_body(stripped: str) -> str:
    return stripped.strip("/").strip("*").strip().lstrip("*").strip()


def comment_lines(lines: list[str], marker: str) -> list[tuple[int, str]]:
    """Line comments for the marker; for // languages also every line inside /* */ blocks."""
    line_re = re.compile(rf"^\s*{re.escape(marker)}\s?(.*)$")
    found, in_block = [], False
    for n, line in enumerate(lines, 1):
        stripped = line.strip()
        if marker == "//" and (in_block or stripped.startswith("/*")):
            in_block = "*/" not in stripped
            body = block_body(stripped)
        else:
            m = line_re.match(line)
            body = m.group(1).strip() if m and not stripped.startswith("#!") else None
        if body and not PRAGMA.search(body):
            found.append((n, body))
    return found


def judge(body: str) -> str | None:
    if HISTORY.search(body):
        return "history comment: git holds history; state the current constraint or delete"
    if NEGATIVE.search(body):
        return "negative or tentative comment: state the constraint positively (\"the provider rejects batches over 100\") or delete"
    if TODO.search(body) and not TICKET.search(body):
        return "TODO without a ticket id"
    if CODEISH.search(body):
        return "commented-out code, delete it"
    return None


def comment_findings(lines: list[str], marker: str) -> list[str]:
    comments = comment_lines(lines, marker)
    found = [f"{n}: {msg}" for n, body in comments if (msg := judge(body))]
    code_lines = sum(1 for line in lines if line.strip())
    plain = [n for n, _ in comments if not DOC_COMMENT.match(lines[n - 1])]
    if code_lines > DENSITY_MIN_LINES and len(plain) / code_lines > DENSITY:
        found.append(f"file: comment density {len(plain)}/{code_lines} lines, keep only non-obvious WHY")
    return found


def secret_findings(lines: list[str]) -> list[str]:
    """Rule 21 (H): a literal assigned to a secret-looking name. Placeholders and env lookups do not match."""
    return [f"{n}: secret literal in source; read it from the environment or a secret store"
            for n, line in enumerate(lines, 1) if SECRET.search(line) and not re.search(r"(?i)example|placeholder|changeme|xxx|\$\{|os\.environ|getenv", line)]


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return dotted(node.func)
    if isinstance(node, ast.Attribute):
        return f"{dotted(node.value)}.{node.attr}"
    return getattr(node, "id", "")


def is_bool(annotation: ast.AST | None) -> bool:
    nodes = ast.walk(annotation) if annotation else ()
    return any((isinstance(n, ast.Name) and n.id == "bool") or (isinstance(n, ast.Constant) and n.value == "bool") for n in nodes)


def is_mutable(default: ast.AST) -> bool:
    return isinstance(default, (ast.List, ast.Dict, ast.Set)) or (isinstance(default, ast.Call) and dotted(default.func) in MUTABLE_CALLS)


def body_length(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Lines of the function minus its docstring."""
    first = node.body[0]
    is_doc = isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str)
    doc_lines = (first.end_lineno or first.lineno) - first.lineno + 1 if is_doc else 0
    return (node.end_lineno or node.lineno) - node.lineno + 1 - doc_lines


def decorated(node: ast.FunctionDef | ast.AsyncFunctionDef, suffix: str) -> bool:
    return any(dotted(d).endswith(suffix) for d in node.decorator_list)


def function_findings(node: ast.FunctionDef | ast.AsyncFunctionDef, *, is_test: bool) -> list[str]:
    positional = [a for a in node.args.posonlyargs + node.args.args if a.arg not in ("self", "cls")]
    params = positional + node.args.kwonlyargs
    defaults = node.args.defaults + [d for d in node.args.kw_defaults if d]
    length, where = body_length(node), f"{node.lineno}: {node.name}"
    rules = (
        (length > MAX_LINES and not is_test, f"{where} is {length} lines, limit {MAX_LINES}; extract named steps"),
        (len(params) > MAX_PARAMS and not is_test, f"{where} takes {len(params)} params, limit {MAX_PARAMS}; group into a value type"),
        (any(is_bool(a.annotation) for a in positional) and not decorated(node, ".setter"),
         f"{where} has a positional bool parameter; use two functions, an enum, or keyword-only"),
        (any(is_mutable(d) for d in defaults), f"{where} has a mutable default"),
    )
    return [message for hit, message in rules if hit]


def python_findings(source: str, *, is_test: bool) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not decorated(node, "overload"):
            found += function_findings(node, is_test=is_test)
        elif isinstance(node, ast.ExceptHandler) and node.type is None:
            found.append(f"{node.lineno}: bare except")
    return found


def plan_files(root) -> set[str]:
    try:
        text = (root / ".sdlc" / "plan.md").read_text()
    except OSError:
        return set()
    return {f.strip() for group in re.findall(r"files:\s*([^|\n]+)", text) for f in group.split(",") if f.strip()}


def slice_warn_due(root, lines: int) -> bool:
    """Warn once per commit, and again only each time the diff grows by another full limit; never on every edit."""
    head = st.git(root, "rev-parse", "HEAD").strip()
    state = st.load(str(root))
    step = lines // SLICE_LINES
    last = state.get("slice_warned", "")
    if last.startswith(head + ":") and int(last.split(":")[1] or 0) >= step:
        return False
    st.save({**state, "slice_warned": f"{head}:{step}"}, str(root))
    return True


def slice_findings(file: str, root) -> list[str]:
    rows = [line.split("\t") for line in st.git(root, "diff", "--numstat", "HEAD", "--", *st.EXCLUDE).splitlines()]
    rows = [r for r in rows if len(r) == 3 and not SLICE_SKIP.search(r[2])]
    lines = sum(int(a) + int(b) for a, b, _ in rows if a.isdigit() and b.isdigit())
    untracked = [p for p in st.git(root, "ls-files", "--others", "--exclude-standard", "--", *st.EXCLUDE).splitlines() if not SLICE_SKIP.search(p)]
    files = len(rows) + len(untracked)
    found = []
    if (lines > SLICE_LINES or files > SLICE_FILES) and slice_warn_due(root, lines):
        found.append(f"slice: {lines} uncommitted lines in {files} files; run /sdlc:why and /sdlc:check, then commit, or split")
    rel = os.path.relpath(os.path.realpath(file), os.path.realpath(root))
    planned = plan_files(root)
    if planned and rel not in planned and not TEST_PATH.search(rel):
        found.append(f"plan: {rel} is not in .sdlc/plan.md files; say why or update the plan")
    return found


def report(found: list[str], file: str, cwd: str) -> None:
    record.append({"kind": "scan", "cwd": os.path.basename(cwd), "file": os.path.basename(file),
                   "rules": [item.split(": ", 1)[-1].split(",")[0].split(";")[0] for item in found]})
    print(f"sdlc standards scan, {os.path.basename(file)}:", file=sys.stderr)
    for item in found[:MAX_FINDINGS]:
        print(f"  {item}", file=sys.stderr)


def findings(file: str, cwd: str | None) -> list[str]:
    ext = os.path.splitext(file)[1]
    source = open(file, encoding="utf-8", errors="replace").read()
    found = comment_findings(source.splitlines(), "#" if ext == ".py" else "//") + secret_findings(source.splitlines())
    if ext == ".py":
        found += python_findings(source, is_test=bool(TEST_PATH.search(file)))
    return found + slice_findings(file, st.root(os.path.dirname(os.path.abspath(file)) or cwd))


def main() -> int:
    if os.environ.get("SDLC_SCAN") == "off":
        return 0
    event = json.load(sys.stdin)
    file = event.get("tool_input", {}).get("file_path", "")
    if os.path.splitext(file)[1] not in SOURCE or not os.path.isfile(file):
        return 0
    found = findings(file, event.get("cwd"))
    if found:
        report(found, file, event.get("cwd", ""))
    return 2 if found else 0


if __name__ == "__main__":
    sys.exit(main())
