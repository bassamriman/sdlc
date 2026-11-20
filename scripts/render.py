#!/usr/bin/env python3
"""Render a markdown file's Mermaid blocks to a local HTML page and open it, for screen-sharing a diagram. Nothing is published.
CLI: render.py <file.md> [--print]. Writes <file>.html next to the source; opens it in Chrome, else the default browser."""
from __future__ import annotations

import html
import subprocess
import sys
from pathlib import Path

MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"
MARKED = "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"
PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>body{{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;background:#fff;color:#111}}
table{{border-collapse:collapse;margin:12px 0;width:100%}} th,td{{border:1px solid #ccc;padding:6px 10px;text-align:left;vertical-align:top}}
th{{background:#f4f4f4}} code{{background:#f4f4f4;padding:1px 4px;border-radius:3px}} .mermaid{{margin:24px 0}}</style></head>
<body><main id="doc"></main><script type="text/markdown" id="md">{markdown}</script>
<script src="{marked}"></script><script src="{mermaid}"></script><script>
const doc = document.getElementById("doc");
doc.innerHTML = marked.parse(document.getElementById("md").textContent);
doc.querySelectorAll("code.language-mermaid").forEach(c => {{
  const d = document.createElement("div"); d.className = "mermaid"; d.textContent = c.textContent; c.parentElement.replaceWith(d); }});
mermaid.initialize({{startOnLoad:false,theme:"neutral"}}); mermaid.run();
</script></body></html>"""


def to_html(markdown: str, title: str) -> str:
    """The whole file rendered as Markdown (tables, headings, code), with each Mermaid block drawn as a diagram."""
    safe = markdown.replace("</script", "<\\/script")  # the source sits inside a script tag
    return PAGE.format(title=html.escape(title), markdown=safe, marked=MARKED, mermaid=MERMAID)


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
