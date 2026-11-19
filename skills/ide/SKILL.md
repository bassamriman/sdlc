---
name: ide
description: Open the project, or a file:line from a review finding, in the IDE that matches the stack - PyCharm for Python, IntelliJ IDEA for Java, Kotlin and Scala, GoLand, RustRover, WebStorm, or VS Code and Cursor when configured. Use when asked to open the project or jump to a file in the IDE.
argument-hint: "[file[:line]] [--print]"
allowed-tools: Bash(python3:*)
model: sonnet
effort: low
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ide.py" $ARGUMENTS` and relay its one line.

Resolution: `ide` key in `.sdlc/stack.json`, else the first entry of `languages` (backend before frontend in every pack), else repo markers. Launchers: JetBrains Toolbox shell script, then `open -a` on macOS. `file:line` opens at the line with `--line` (JetBrains) or `-g` (VS Code, Cursor); `open -a` cannot, so it opens the file. `--print` shows the command without launching.

If the script reports no launcher, repeat its install hint; do not try other applications.
In a fleet, to open another agent's clone: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fleet.py" ide <agent> [file[:line]]` from the fleet root.
