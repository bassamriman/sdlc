#!/usr/bin/env python3
"""Render a markdown file's Mermaid blocks to a local HTML page and open it, for screen-sharing a diagram. Nothing is published.
CLI: render.py <file.md> [--print]. Writes <file>.html next to the source; opens it in Chrome, else the default browser."""
from __future__ import annotations

import html
import re
import subprocess
import sys
from pathlib import Path

MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"
BLOCK = re.compile(r"```mermaid\n(.*?)```", re.S)
PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>body{{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;background:#fff;color:#111}}
pre{{white-space:pre-wrap}} .mermaid{{margin:24px 0}} table{{border-collapse:collapse}} td,th{{border:1px solid #ccc;padding:4px 8px}}</style></head>
<body>{body}<script src="{mermaid}"></script><script>mermaid.initialize({{startOnLoad:true,theme:"neutral"}});</script></body></html>"""


def to_html(markdown: str, title: str) -> str:
    """Mermaid blocks become live diagrams; everything else is shown as preformatted text, which keeps tables and notes readable."""
    parts, last = [], 0
    for m in BLOCK.finditer(markdown):
        parts.append(f"<pre>{html.escape(markdown[last:m.start()])}</pre>")
        parts.append(f'<div class="mermaid">{html.escape(m.group(1))}</div>')
        last = m.end()
    parts.append(f"<pre>{html.escape(markdown[last:])}</pre>")
    return PAGE.format(title=html.escape(title), body="\n".join(parts), mermaid=MERMAID)


def open_page(path: Path) -> None:
    if subprocess.run(["open", "-a", "Google Chrome", str(path)], capture_output=True).returncode != 0:
        subprocess.run(["open", str(path)], capture_output=True)


def main(argv: list[str]) -> int:
    source = Path(argv[0])
    target = source.with_suffix(".html")
    target.write_text(to_html(source.read_text(), source.stem))
    print(target)
    if "--print" not in argv:
        open_page(target)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
