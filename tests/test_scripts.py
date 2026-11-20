"""Pipe hook JSON into the scripts inside a scratch git repo. Run: python3 -m unittest discover -s tests (any Python 3.9+)."""
from __future__ import annotations

import ast
import json
import time
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


SCRATCH_DATA = tempfile.mkdtemp()  # every test writes telemetry here, never to the user's real log
HERMETIC = {k: v for k, v in os.environ.items() if not k.startswith("SDLC_")}  # a fleet session's env must not steer the tests


def run(script: str, *args: str, cwd: Path, stdin: dict | None = None, env: dict | None = None):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=cwd, text=True, capture_output=True,
                          input=json.dumps(stdin) if stdin is not None else None,
                          env={**HERMETIC, "SDLC_DATA_DIR": SCRATCH_DATA, **(env or {})})


def decision(out) -> str:
    return json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"]


RECORDED = "Assumptions: none. Pitfalls: none. Design: docs/design/x.md"
COMMIT = f'git commit -m "x" -m "{RECORDED}"'


class Repo(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        git = lambda *a: subprocess.run(["git", *a], cwd=self.dir, check=True, capture_output=True)
        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@t.t")
        git("config", "user.name", "t")
        (self.dir / "a.txt").write_text("a\n")
        git("add", "."), git("commit", "-qm", "init")
        (self.dir / ".sdlc").mkdir()
        self.stack({"test": "echo ok"}, ["test"])
        (self.dir / "docs" / "design").mkdir(parents=True)
        (self.dir / "docs" / "design" / "x.md").write_text("# design\n")  # the record gate wants an updated design doc with code

    def stack(self, commands: dict, check: list) -> None:
        (self.dir / ".sdlc" / "stack.json").write_text(json.dumps({"pack": "t", "commands": commands, "check": check}))

    def gate(self, command: str, cwd: Path | None = None):
        return run("guard.py", cwd=self.dir, stdin={"cwd": str(cwd or self.dir), "tool_input": {"command": command}})

    def commit_gate(self) -> int:
        return self.gate(COMMIT).returncode

    def scan(self, name: str, body: str) -> str:
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(body))
        return run("scan.py", cwd=self.dir, stdin={"cwd": str(self.dir), "tool_input": {"file_path": str(path)}}).stderr


class GateTests(Repo):
    def test_blocked_until_green_then_index_insensitive(self) -> None:
        (self.dir / "new.py").write_text("x = 1\n")
        self.assertEqual(self.commit_gate(), 2)
        self.assertEqual(run("check.py", cwd=self.dir).returncode, 0)
        self.assertEqual(self.commit_gate(), 0)
        subprocess.run(["git", "add", "new.py"], cwd=self.dir, check=True)
        self.assertEqual(self.commit_gate(), 0, "git add must not invalidate the green tree")
        (self.dir / "new.py").write_text("x = 2\n")
        self.assertEqual(self.commit_gate(), 2)

    def test_git_global_flags_and_gate_off(self) -> None:
        self.assertEqual(self.gate(f"git -C {self.dir} commit -m x -m '{RECORDED}'").returncode, 2)
        self.assertEqual(self.gate(f'git -c user.name="a b" commit -m x -m "{RECORDED}"').returncode, 2)
        out = run("guard.py", cwd=self.dir, stdin={"cwd": str(self.dir), "tool_input": {"command": COMMIT}}, env={"SDLC_GATE": "off"})
        self.assertEqual(out.returncode, 0)

    def test_push_asks_and_force_push_denied(self) -> None:
        for command, expected in (("git push origin main", "ask"), ("git push -f origin main", "deny"),
                                  ("git push --force-with-lease origin main", "ask"), ("git branch -D old", "ask"),
                                  ("gh pr create --fill", "ask")):
            self.assertEqual(decision(self.gate(command)), expected, command)

    def test_gates_are_granular_and_typos_tighten(self) -> None:
        env = {"SDLC_GATES": "push=auto,pr=ask,commit=check,branch_delete=bogus"}
        self.assertEqual(run("guard.py", cwd=self.dir, stdin={"cwd": str(self.dir), "tool_input": {"command": "git push origin main"}}, env=env).stdout, "")
        self.assertEqual(decision(run("guard.py", cwd=self.dir, stdin={"cwd": str(self.dir), "tool_input": {"command": "gh pr create"}}, env=env)), "ask")
        self.assertEqual(decision(run("guard.py", cwd=self.dir, stdin={"cwd": str(self.dir), "tool_input": {"command": "git branch -D x"}}, env=env)), "ask")
        (self.dir / "new.py").write_text("x = 1\n")
        off = {"SDLC_GATES": "commit=off"}
        self.assertEqual(run("guard.py", cwd=self.dir, stdin={"cwd": str(self.dir), "tool_input": {"command": COMMIT}}, env=off).returncode, 0)

    def test_autopilot_lifts_push_and_pr_gates_only(self) -> None:
        env = {"SDLC_GATES": "push=auto,pr=auto,message=auto,branch_delete=auto"}
        for command in ("git push origin main", "gh pr create --fill"):
            self.assertEqual(run("guard.py", cwd=self.dir, stdin={"cwd": str(self.dir), "tool_input": {"command": command}}, env=env).stdout, "", command)
        force = run("guard.py", cwd=self.dir, stdin={"cwd": str(self.dir), "tool_input": {"command": "git push -f origin main"}}, env=env)
        self.assertEqual(decision(force), "deny")
        (self.dir / "new.py").write_text("x = 1\n")
        self.assertEqual(run("guard.py", cwd=self.dir, stdin={"cwd": str(self.dir), "tool_input": {"command": COMMIT}}, env=env).returncode, 2)

    def test_commit_then_push_is_gated_before_the_push_asks(self) -> None:
        (self.dir / "new.py").write_text("x = 1\n")
        self.assertEqual(self.gate(COMMIT + " && git push").returncode, 2)
        run("check.py", cwd=self.dir)
        out = self.gate(COMMIT + " && git push")
        self.assertEqual((out.returncode, decision(out)), (0, "ask"))
        self.assertEqual(self.gate("git commit-tree HEAD^{tree}").stdout, "")

    def test_big_file_edit_in_place_invalidates_green(self) -> None:
        big = self.dir / "big.bin"
        big.write_bytes(b"a" * 2_100_000)
        run("check.py", cwd=self.dir)
        self.assertEqual(self.commit_gate(), 0)
        big.write_bytes(b"b" * 2_100_000)
        os.utime(big, ns=(big.stat().st_atime_ns, big.stat().st_mtime_ns + 1_000_000))
        self.assertEqual(self.commit_gate(), 2)

    def test_gate_fails_closed_when_it_cannot_run(self) -> None:
        out = self.gate(COMMIT, cwd=self.dir / "gone")
        self.assertEqual(out.returncode, 2)
        self.assertIn("could not run", out.stderr)

    def test_check_all_skip_is_red_and_malformed_stack_is_named(self) -> None:
        self.stack({"test": None}, ["test"])
        out = run("check.py", cwd=self.dir)
        self.assertEqual((out.returncode, "RED" in out.stdout), (1, True))
        (self.dir / ".sdlc" / "stack.json").write_text("{")
        out = run("check.py", cwd=self.dir)
        self.assertEqual((out.returncode, "malformed" in out.stdout), (2, True))


class ScanTests(Repo):
    LEGIT = """
        # Fixed-size ring: the producer never blocks, old entries are dropped on purpose.
        # If upstream was down, we retry; see https://example.com/runbook for details.
        # removed rows are soft-deleted so audit can replay them
        # for details see: ADR-12
        # TODO(ABC-123): tighten once the provider confirms the limit
        # noqa: E501
        def ok(x):
            return x
    """
    BAD = """
        # changed from list to dict
        # TODO fix this
        # result = compute(x);
        # import os
        def process(a, b, c, d, flag: bool, items=[]):
            try:
                pass
            except:
                pass
            return a
    """
    SIGNATURES = '''
        from typing import overload
        @overload
        def f(a: bool, b: bool, c: bool, d: bool): ...
        def g(a, b, c, d, /):
            return a
        def h(*, verbose: bool = False):
            return verbose
        def k(x: bool | None):
            return x
        def m(x=list()):
            return x
        def documented():
            """
            one
            two
            three
            four
            five
            six
            seven
            eight
            nine
            ten
            eleven
            twelve
            """
            return 1
    '''

    def test_legitimate_why_comments_pass(self) -> None:
        self.assertEqual(self.scan("ok.py", self.LEGIT), "")

    def test_violations_flagged(self) -> None:
        err = self.scan("bad.py", self.BAD)
        for needle in ("history comment", "TODO without", "commented-out code", "6 params", "bool parameter", "mutable default", "bare except"):
            self.assertIn(needle, err)

    def test_commented_code_shapes_including_blocks(self) -> None:
        err = self.scan("code.py", '# raise ValueError("x")\n# with open(p) as fh:\n# @lru_cache\n# pass\nx = 1\n')
        self.assertEqual(err.count("commented-out code"), 4)
        ts = "/* const y = 1 */\n/**\n * @param x the value\n */\n// let z = foo()\nexport const a = 1;\n"
        self.assertEqual(self.scan("a.ts", ts).count("commented-out code"), 2)

    def test_python_signature_rules(self) -> None:
        err = self.scan("sig.py", self.SIGNATURES)
        self.assertNotIn(": f ", err, "overloads are skipped")
        self.assertIn("g takes 4 params", err)
        self.assertNotIn(": h ", err, "keyword-only bool is allowed")
        self.assertIn("k has a positional bool", err)
        self.assertIn("m has a mutable default", err)
        self.assertNotIn("documented", err, "docstring lines do not count")
        self.assertEqual(self.scan("tests/test_fx.py", "def test_x(client, db, user, settings):\n    return 1\n"), "")

    def test_prose_comments_are_not_code_and_since_needs_a_reason(self) -> None:
        prose = "# if the cache is cold, rebuild as follows:\n# for x in this loop we skip blanks\n# while waiting, see below:\n# retry since the API rate-limits\nx = 1\n"
        self.assertEqual(self.scan("prose.py", prose), "")
        self.assertIn("history comment", self.scan("hist.py", "# renamed from fetch_all since 2.0\nx = 1\n"))
        self.assertEqual(self.scan("code.py", "# if x == 1:\n# for i in range(3):\n# else:\nx = 1\n").count("commented-out code"), 3)

    def test_secret_literals_and_doc_comment_density(self) -> None:
        err = self.scan("cfg.py", 'API_KEY = "sk_live_abcdef1234567890"\npassword = os.environ["PW"]\nTOKEN = "changeme-placeholder"\n')
        self.assertEqual(err.count("secret literal"), 1)
        rust = "\n".join(["/// doc line for the public contract"] * 30 + ["pub fn f() {}"] * 20)
        self.assertEqual(self.scan("doc.rs", rust), "", "doc comments never count toward density")

    def test_rust_attributes_are_not_comments(self) -> None:
        self.assertEqual(self.scan("lib.rs", "#[derive(Debug)]\nstruct A;\n// why: keeps the enum closed\n"), "")

    def test_test_files_skip_length_and_latest_dir_is_not_a_test(self) -> None:
        body = "def test_x():\n" + "    y = 1\n" * 20
        self.assertEqual(self.scan("tests/test_a.py", body), "")
        self.assertIn("lines, limit", self.scan("latest_builds/a.py", body.replace("test_x", "x")))

    def test_slice_and_plan_warnings(self) -> None:
        (self.dir / ".sdlc" / "plan.md").write_text("- Slice 1: thing | test: t | files: app/a.py | verify: make test\n")
        err = self.scan("app/b.py", "x = 1\n")
        self.assertIn("not in .sdlc/plan.md", err)
        self.assertEqual(self.scan("app/a.py", "x = 1\n"), "")


class StateTests(Repo):
    def test_timebox_expires_and_stop_clears(self) -> None:
        run("state.py", "start", "10", cwd=self.dir)
        self.assertIn("[timebox]", run("state.py", "tick", cwd=self.dir).stdout)
        state = json.loads((self.dir / ".sdlc" / "state.json").read_text())
        state["started"] -= 60 * 25
        (self.dir / ".sdlc" / "state.json").write_text(json.dumps(state))
        self.assertEqual(run("state.py", "tick", cwd=self.dir).stdout, "")
        run("state.py", "stop", cwd=self.dir)
        self.assertNotIn("budget_min", json.loads((self.dir / ".sdlc" / "state.json").read_text()))

    def test_init_records_base_pack_and_exclude(self) -> None:
        (self.dir / ".sdlc" / "stack.json").unlink()
        (self.dir / "manage.py").write_text("")
        (self.dir / "frontend").mkdir()
        (self.dir / "frontend" / "tsconfig.json").write_text("{}")
        out = json.loads(run("init.py", "30", cwd=self.dir).stdout)
        self.assertEqual(out["pack"], "python-django-react")
        self.assertEqual(out["timebox_min"], 30)
        self.assertIn(".sdlc/", (self.dir / ".git" / "info" / "exclude").read_text())
        self.assertIn("main", out["base"])

    def test_init_without_minutes_keeps_timebox_and_any_save_excludes(self) -> None:
        run("state.py", "start", "10", cwd=self.dir)
        self.assertIn(".sdlc/", (self.dir / ".git" / "info" / "exclude").read_text())
        run("init.py", cwd=self.dir)
        self.assertEqual(json.loads((self.dir / ".sdlc" / "state.json").read_text())["budget_min"], 10)

    def test_detect_prefers_root_markers_and_knows_kotlin(self) -> None:
        (self.dir / "tsconfig.json").write_text("{}")
        (self.dir / "vendor" / "foo").mkdir(parents=True)
        (self.dir / "vendor" / "foo" / "go.mod").write_text("")
        self.assertEqual(json.loads(run("detect.py", cwd=self.dir).stdout)["pack"], "typescript")
        (self.dir / "build.gradle.kts").write_text("")
        (self.dir / "src").mkdir()
        (self.dir / "src" / "A.kt").write_text("")
        self.assertEqual(json.loads(run("detect.py", cwd=self.dir).stdout)["pack"], "kotlin-gradle")

    def test_session_reports_plan(self) -> None:
        (self.dir / ".sdlc" / "plan.md").write_text("- Slice 1: a\n- Slice 2: b\n")
        self.assertIn("2 slices", run("session.py", cwd=self.dir, stdin={"cwd": str(self.dir)}).stdout)


class TelemetryTests(Repo):
    def setUp(self) -> None:
        super().setUp()
        self.data = tempfile.mkdtemp()
        self.env = {"SDLC_DATA_DIR": self.data}

    def test_off_by_default_and_signatures(self) -> None:
        run("record.py", cwd=self.dir, stdin={"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "uv run pytest -x"}}, env=self.env)
        self.assertFalse((Path(self.data) / "usage.jsonl").exists())
        run("record.py", "on", cwd=self.dir, env=self.env)
        events = [
            {"hook_event_name": "UserPromptSubmit", "prompt": "add a POST endpoint", "session_id": "s1"},
            {"hook_event_name": "UserPromptSubmit", "prompt": "<task-notification>x</task-notification>"},
            {"hook_event_name": "PostToolUse", "tool_name": "Skill", "tool_input": {"skill": "sdlc:red", "args": "slice 1"}, "tool_response": {"is_error": False}},
            {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "FOO=1 uv run pytest -x tests/ && echo done"}, "tool_response": {"exitCode": 1}},
            {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "ls -la"}},
        ]
        for event in events:
            run("record.py", cwd=self.dir, stdin=event, env=self.env)
        rows = [json.loads(l) for l in (Path(self.data) / "usage.jsonl").read_text().splitlines()]
        self.assertEqual([r["kind"] for r in rows], ["intent", "skill", "cmd"])
        self.assertEqual(rows[2]["sig"], "uv run")
        self.assertIs(rows[2]["ok"], False)
        run("record.py", "feedback", "red is slow", "red", cwd=self.dir, env=self.env)
        out = json.loads(run("reflect.py", cwd=self.dir, env=self.env).stdout)
        self.assertEqual(out["skills"], [["sdlc:red", 1]])
        self.assertEqual(out["feedback"][0]["about"], "red")
        self.assertEqual(out["intents_without_skill"], [])

    def test_scan_records_rules_when_on(self) -> None:
        run("record.py", "on", cwd=self.dir, env=self.env)
        path = self.dir / "b.py"
        path.write_text("# TODO later\nx = 1\n")
        run("scan.py", cwd=self.dir, stdin={"cwd": str(self.dir), "tool_input": {"file_path": str(path)}}, env=self.env)
        rows = [json.loads(l) for l in (Path(self.data) / "usage.jsonl").read_text().splitlines()]
        self.assertEqual(rows[-1]["rules"], ["TODO without a ticket id"])


class FleetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp()).resolve()
        (self.root / ".sdlc").mkdir()
        fleet = {"name": "epic", "base": "main", "agents": [
            {"name": "contracts", "repo": "git@github.com:o/contracts.git", "branch": "f"},
            {"name": "api", "repo": "git@github.com:o/api.git", "branch": "f", "depends": [{"on": "contracts", "phase": "start"}]},
            {"name": "web", "repo": "git@github.com:o/web.git", "branch": "f", "depends": [{"on": "api", "phase": "merge"}]}]}
        (self.root / ".sdlc" / "fleet.json").write_text(json.dumps(fleet))
        for name in ("contracts", "api", "web"):
            (self.root / name / name / ".sdlc").mkdir(parents=True)

    def status(self, agent: str, value: str) -> None:
        (self.root / agent / agent / ".sdlc" / "context.md").write_text(f"# Saved context\n**Status**: {value}\n")

    def test_waves_follow_start_and_merge_edges(self) -> None:
        waves = json.loads(run("fleet.py", "waves", cwd=self.root).stdout)
        self.assertEqual(waves["ready"], ["contracts", "web"])
        self.assertEqual(waves["blocked"], {"api": ["contracts"]})
        self.status("contracts", "pr-open")
        self.status("web", "in-progress")
        waves = json.loads(run("fleet.py", "waves", cwd=self.root).stdout)
        self.assertEqual(waves["ready"], ["api"])
        self.assertEqual(next(r for r in waves["running"] if r["name"] == "web")["cannot_land_until"], ["api"])

    def test_launch_command_sets_workspace_and_name(self) -> None:
        command = run("fleet.py", "launch", "api", cwd=self.root).stdout
        self.assertIn(f"SDLC_AGENT_WORKSPACE={self.root / 'api'}", command)
        self.assertIn("--name sdlc/epic/api", command)
        self.assertIn("rebase this branch onto origin/main", command)
        self.assertIn("push and open the draft PR", command)
        self.assertNotIn("--plugin-dir", command)
        self.assertIn("--model sonnet --effort low --permission-mode auto", command, "speed by default")
        self.assertEqual(run("fleet.py", "view", cwd=self.root).stdout.strip(), f"claude agents --cwd {self.root}")
        self.assertEqual(run("fleet.py", "ide", "nobody", cwd=self.root).returncode, 2)
        self.assertEqual(run("fleet.py", "retire", "nobody", cwd=self.root).returncode, 2)
        self.assertIn("not done", run("fleet.py", "retire", "contracts", cwd=self.root).stdout)
        fleet = json.loads((self.root / ".sdlc" / "fleet.json").read_text())
        (self.root / ".sdlc" / "fleet.json").write_text(json.dumps({**fleet, "plugin_dir": "/p/sdlc"}))
        self.assertIn("--plugin-dir /p/sdlc", run("fleet.py", "launch", "api", cwd=self.root).stdout)

    def test_isolation_denies_outside_and_asks_on_message(self) -> None:
        env = {"SDLC_AGENT_WORKSPACE": str(self.root / "api")}
        edit = {"tool_name": "Edit", "tool_input": {"file_path": str(self.root / "api/api/x.py")}}
        self.assertIn("/sdlc:init", run("isolate.py", cwd=self.root, stdin=edit, env=env).stderr, "no source edit before init")
        clone = self.root / "api" / "api"  # the real layout: workspace/<repo>/.git, with .sdlc beside .git
        (clone / ".git").mkdir(parents=True, exist_ok=True)
        (clone / ".sdlc").mkdir(parents=True, exist_ok=True)
        (clone / ".sdlc" / "stack.json").write_text("{}")
        self.assertIn("/sdlc:plan", run("isolate.py", cwd=self.root, stdin=edit, env=env).stderr, "no source edit before a plan")
        (clone / ".sdlc" / "plan.md").write_text("1. slice")
        inside = run("isolate.py", cwd=self.root, stdin=edit, env=env)
        outside = run("isolate.py", cwd=self.root, stdin={"tool_name": "Edit", "tool_input": {"file_path": str(self.root / "web/web/x.py")}}, env=env)
        message = run("isolate.py", cwd=self.root, stdin={"tool_name": "SendMessage", "tool_input": {"to": "sdlc/epic/web"}}, env=env)
        inert = run("isolate.py", cwd=self.root, stdin={"tool_name": "Edit", "tool_input": {"file_path": "/etc/hosts"}}, env={"SDLC_AGENT_WORKSPACE": ""})
        self.assertEqual((inside.returncode, outside.returncode, inert.returncode), (0, 2, 0))
        self.assertEqual(decision(message), "ask")

    def test_autopilot_messages_flow_within_the_epic_only(self) -> None:
        env = {"SDLC_AGENT_WORKSPACE": str(self.root / "api"), "SDLC_EPIC": "epic", "SDLC_GATES": "message=auto"}
        same = run("isolate.py", cwd=self.root, stdin={"tool_name": "SendMessage", "tool_input": {"to": "sdlc/epic/web"}}, env=env)
        other = run("isolate.py", cwd=self.root, stdin={"tool_name": "SendMessage", "tool_input": {"to": "sdlc/other/web"}}, env=env)
        self.assertEqual(same.stdout, "")
        self.assertEqual(decision(other), "ask")
        fleet = json.loads((self.root / ".sdlc" / "fleet.json").read_text())
        (self.root / ".sdlc" / "fleet.json").write_text(json.dumps({**fleet, "autopilot": True}))
        self.assertIn("SDLC_GATES=commit=check,push=auto,pr=auto,message=auto,branch_delete=auto", run("fleet.py", "launch", "api", cwd=self.root).stdout)
        (self.root / ".sdlc" / "fleet.json").write_text(json.dumps({**fleet, "gates": {"push": "auto"}, "env": {"GIT_CONSENT_GROUPS": "none"}}))
        self.assertIn("GIT_CONSENT_GROUPS=none", run("fleet.py", "launch", "api", cwd=self.root).stdout)
        self.assertIn("SDLC_GATES=commit=check,push=auto,pr=ask,message=ask,branch_delete=ask", run("fleet.py", "launch", "api", cwd=self.root).stdout)

    def test_isolation_asks_on_bash_writes_outside_only(self) -> None:
        env = {"SDLC_AGENT_WORKSPACE": str(self.root / "api")}
        bash = lambda c: run("isolate.py", cwd=self.root, stdin={"tool_name": "Bash", "tool_input": {"command": c}}, env=env)
        self.assertEqual(decision(bash(f"echo x > {self.root}/api/api/out.txt")), "deny", "shell writes face the process gate too")
        (self.root / "api" / "api").mkdir(parents=True, exist_ok=True)
        for git_op in (f"cd {self.root}/api/api && git rebase origin/main", f"git -C {self.root}/api/api merge origin/main"):
            self.assertEqual(bash(git_op).stdout, "", "git operations are not source edits")
        ready_clone(self.root / "api" / "api")
        for command in (f"echo x > {self.root}/web/web/README.md", f"git -C {self.root}/web/web merge f",
                        f"cd {self.root}/web/web && git checkout f", f"cp -r skills {self.root}/web/"):
            self.assertEqual(decision(bash(command)), "ask", command)
        for command in (f"python3 /Users/x/plugin/scripts/state.py phase build", f"echo x > {self.root}/api/api/out.txt",
                        f'python3 "{SCRIPTS}/init.py" >/dev/null; git status -s',
                        "cat > .sdlc/context.md <<'E'\n**Next**: /sdlc:pr open\nE", "echo done > /nonexistent-root-dir/x.txt",
                        "git status", f"cat {self.root}/web/web/README.md", "ls /usr/bin"):
            self.assertEqual(bash(command).stdout, "", command)


def ready_clone(clone: Path) -> None:
    """An agent clone after /sdlc:init and /sdlc:plan, so the process gate lets source writes through."""
    for part in (".git", ".sdlc"):
        (clone / part).mkdir(parents=True, exist_ok=True)
    (clone / ".sdlc" / "stack.json").write_text("{}")
    (clone / ".sdlc" / "plan.md").write_text("1. slice")


def old_python() -> str | None:
    """An interpreter below 3.12, whose stricter f-string grammar catches what ast.parse(feature_version) misses."""
    for candidate in (shutil.which("python3.9"), shutil.which("python3.10"), shutil.which("python3.11"), "/usr/bin/python3"):
        if candidate and Path(candidate).exists():
            out = subprocess.run([candidate, "-c", "import sys; print(sys.version_info < (3, 12))"], capture_output=True, text=True)
            if out.stdout.strip() == "True":
                return candidate
    return None


class OrchestratorTests(FleetTests):
    def test_bus_is_outbox_only_and_inbox_advances(self) -> None:
        api = {"SDLC_FLEET_ROOT": str(self.root), "SDLC_AGENT_WORKSPACE": str(self.root / "api")}
        orch = {"SDLC_FLEET_ROOT": str(self.root)}
        sent = json.loads(run("bus.py", "send", "orchestrator", "contract v1 published", cwd=self.root, env={**api, "SDLC_EPIC": "epic"}).stdout)
        self.assertEqual(sent["notify_with_SendMessage"][0]["to"], "sdlc/epic/orchestrator")
        self.assertIn("outbox.jsonl", sent["notify_with_SendMessage"][0]["message"])
        run("bus.py", "send", "all", "freeze at 17:00", cwd=self.root, env=orch)
        self.assertTrue((self.root / "api" / "outbox.jsonl").exists())
        self.assertEqual(run("bus.py", "peek", cwd=self.root, env=orch).stdout.strip(), "1")
        first = run("bus.py", "inbox", cwd=self.root, env=orch).stdout
        self.assertIn("api -> orchestrator: contract v1 published", first)
        self.assertEqual(run("bus.py", "inbox", cwd=self.root, env=orch).stdout, "", "read once, then the cursor moves")
        self.assertIn("orchestrator -> all: freeze", run("bus.py", "nudge", cwd=self.root, env=api).stdout, "the nudge shows the message itself")
        self.assertEqual(run("bus.py", "inbox", cwd=self.root, env=api).stdout, "", "and marks it read")
        self.assertEqual(run("bus.py", "nudge", cwd=self.root, env=api).stdout, "")
        self.assertEqual(run("bus.py", "nudge", cwd=self.root).stdout, "", "silent outside a fleet session")

    def test_orchestrate_launches_ready_once_and_reports_done(self) -> None:
        step = json.loads(run("fleet.py", "orchestrate", cwd=self.root).stdout)
        self.assertEqual(step["launched_now"], ["contracts", "web"])
        again = json.loads(run("fleet.py", "orchestrate", cwd=self.root).stdout)
        self.assertEqual(again["launched_now"], [])
        for name in ("contracts", "api", "web"):
            self.status(name, "done")
        self.assertTrue(json.loads(run("fleet.py", "orchestrate", cwd=self.root).stdout)["epic_done"])
        command = run("fleet.py", "launch", "orchestrator", cwd=self.root).stdout
        self.assertIn("--name sdlc/epic/orchestrator", command)
        pinned = json.loads((self.root / "orchestrator" / ".claude" / "settings.local.json").read_text())
        self.assertEqual(pinned["env"]["SDLC_AGENT_NAME"], "orchestrator")
        (self.root / "orchestrator" / "sessions.json").write_text(json.dumps({"contracts": "abc-123"}))  # as if looked up by name after launch
        wake = run("fleet.py", "wake", "contracts", "look at your inbox", cwd=self.root).stdout
        self.assertTrue(wake.startswith(f"cd {self.root / 'contracts' / 'contracts'} && "))
        self.assertIn("SDLC_AGENT_NAME=contracts", wake)
        self.assertTrue(wake.rstrip().endswith("claude --resume abc-123 --bg 'look at your inbox'"), "no flags on resume: any flag forks a copy")
        fleet = json.loads((self.root / ".sdlc" / "fleet.json").read_text())
        (self.root / ".sdlc" / "fleet.json").write_text(json.dumps({**fleet, "plugin_dir": "/p/sdlc"}))
        self.assertNotIn("--plugin-dir", run("fleet.py", "wake", "contracts", "look at your inbox", cwd=self.root).stdout)
        fleet["model"], fleet["agents"][0]["effort"] = "sonnet", "low"
        (self.root / ".sdlc" / "fleet.json").write_text(json.dumps(fleet))
        self.assertIn("--model sonnet --effort low --permission-mode auto", run("fleet.py", "launch", "contracts", cwd=self.root).stdout)
        self.assertNotIn("--model", run("fleet.py", "wake", "contracts", "look at your inbox", cwd=self.root).stdout)
        fleet["permission_mode"] = "bypassPermissions"
        (self.root / ".sdlc" / "fleet.json").write_text(json.dumps(fleet))
        self.assertIn("--permission-mode auto", run("fleet.py", "launch", "contracts", cwd=self.root).stdout, "bypass is never passed through")
        self.assertIn("would_prune", run("fleet.py", "prune", cwd=self.root, env={"PATH": "/usr/bin:/bin"}).stdout)
        missing = run("fleet.py", "wake", "web", cwd=self.root, env={"PATH": "/usr/bin:/bin"})
        self.assertEqual(missing.returncode, 1)
        self.assertIn("no session found named sdlc/epic/web", missing.stdout)
        self.assertIn(f"SDLC_AGENT_WORKSPACE={self.root / 'orchestrator'}", command)


class NotifyTests(FleetTests):
    def test_context_write_and_pr_create_report_to_the_orchestrator(self) -> None:
        env = {"SDLC_FLEET_ROOT": str(self.root), "SDLC_AGENT_WORKSPACE": str(self.root / "api"), "PATH": "/usr/bin:/bin"}  # git yes, claude no: wake is a no-op
        ctx = self.root / "api" / "api" / ".sdlc" / "context.md"
        ctx.write_text("# Saved context\n**Status**: pr-open\n**Branch**: f at abc   **Base**: main   **PR**: https://github.com/o/api/pull/7\n")
        out = run("notify.py", cwd=self.root, stdin={"tool_name": "Write", "tool_input": {"file_path": str(ctx)}}, env=env)
        self.assertIn("reported to the orchestrator", out.stdout)
        response = {"stdout": "https://github.com/o/api/pull/7\n"}
        run("prlink.py", cwd=self.root / "api" / "api", stdin={"tool_name": "Bash", "tool_input": {"command": "gh pr create --fill"}, "tool_response": response}, env=env)
        inbox = run("bus.py", "inbox", cwd=self.root, env={"SDLC_FLEET_ROOT": str(self.root), "PATH": "/usr/bin:/bin"}).stdout
        self.assertIn("api -> orchestrator: status pr-open; pr https://github.com/o/api/pull/7", inbox)
        self.assertIn("api -> orchestrator: pr opened https://github.com/o/api/pull/7", inbox)
        self.assertEqual(run("notify.py", cwd=self.root, stdin={"tool_name": "Write", "tool_input": {"file_path": str(ctx)}}).stdout, "", "inert outside a fleet")
        self.assertIn("fanout", run("fleet.py", "fanout", "freeze now", cwd=self.root, env=env).stdout.replace("sent_to", "fanout"))


class SharedContextTests(FleetTests):
    def test_shared_is_seeded_read_by_all_and_written_only_by_the_orchestrator(self) -> None:
        (self.root / "design.md").write_text("# design\n")
        fleet = json.loads((self.root / ".sdlc" / "fleet.json").read_text())
        (self.root / "fleet.json").write_text(json.dumps({**fleet, "resources": ["design.md"]}))
        out = json.loads(run("fleet.py", "init", str(self.root / "fleet.json"), cwd=self.root, env={"PATH": "/usr/bin:/bin"}).stdout)
        self.assertEqual(out["resources"]["seeded"], ["design.md"])
        self.assertIn("!/resources/", (self.root / ".gitignore").read_text())
        self.assertTrue((self.root / "resources" / "README.md").exists())
        launch = run("fleet.py", "launch", "api", cwd=self.root).stdout
        self.assertIn(f"--add-dir {self.root / 'resources'}", launch)
        pinned = json.loads((self.root / "api" / "api" / ".claude" / "settings.local.json").read_text()) if (self.root / "api" / "api" / ".claude" / "settings.local.json").exists() else None
        run("fleet.py", "launch", "orchestrator", cwd=self.root)
        orch = json.loads((self.root / "orchestrator" / ".claude" / "settings.local.json").read_text())
        self.assertIn(str(self.root / "resources"), orch["permissions"]["additionalDirectories"], "a hand-opened orchestrator session reads resources/ too")
        (self.root / "fleet.json").write_text(json.dumps({**fleet, "resources": ["design.md"], "name": "renamed"}))
        run("fleet.py", "init", str(self.root / "fleet.json"), cwd=self.root, env={"PATH": "/usr/bin:/bin"})
        self.assertTrue(list((self.root / ".sdlc").glob("fleet.*.json")), "a re-run keeps the previous definition")
        target = {"tool_name": "Write", "tool_input": {"file_path": str(self.root / "resources" / "decisions.md")}}
        agent = {"SDLC_AGENT_WORKSPACE": str(self.root / "api"), "SDLC_FLEET_ROOT": str(self.root), "SDLC_AGENT_NAME": "api"}
        orch = {"SDLC_AGENT_WORKSPACE": str(self.root / "orchestrator"), "SDLC_FLEET_ROOT": str(self.root), "SDLC_AGENT_NAME": "orchestrator"}
        self.assertEqual(run("isolate.py", cwd=self.root, stdin=target, env=agent).returncode, 2, "agents are read-only in resources/")
        self.assertEqual(run("isolate.py", cwd=self.root, stdin=target, env=orch).returncode, 0, "the orchestrator owns resources/")


class AuditHardeningTests(FleetTests):
    def bash(self, command: str, env: dict) -> "subprocess.CompletedProcess[str]":
        return run("isolate.py", cwd=self.root, stdin={"tool_name": "Bash", "cwd": str(self.root / "api" / "api"), "tool_input": {"command": command}}, env=env)

    def test_isolation_closes_relative_env_protected_and_plugin_paths(self) -> None:
        env = {"SDLC_AGENT_WORKSPACE": str(self.root / "api"), "SDLC_FLEET_ROOT": str(self.root), "SDLC_AGENT_NAME": "api"}
        (self.root / "api" / "api" / ".claude").mkdir(exist_ok=True)
        ready_clone(self.root / "api" / "api")
        for command in ("echo x > ../../web/web/README.md", f"cd {self.root}/web/web && echo x > README.md", f"python3 -c \"open('{self.root}/web/web/x','w')\"",
                        f"dd if=/dev/zero of={self.root}/web/web/x", f"git --git-dir={self.root}/web/web commit -m x"):
            self.assertEqual(decision(self.bash(command, env)), "ask", command)
        for command in (f"echo x > {SCRIPTS}/guard.py", f"SDLC_AGENT_WORKSPACE={self.root}/orchestrator python3 bus.py send all stop",
                        "export SDLC_GATES=push=auto", f"echo x > {self.root}/api/api/.claude/settings.local.json",
                        f"git --git-dir={self.root}/web/web/.git commit -m x"):
            self.assertEqual(decision(self.bash(command, env)), "deny", command)
        for command in ("cat > .sdlc/context.md <<'E'\n**Next**: /sdlc:pr open\nE", f"python3 {SCRIPTS}/state.py show", "grep SDLC_GATES notes.md",
                        f"cd {self.root}; ls -la . orchestrator resources 2>&1; cat orchestrator/.sdlc/fleet.json 2>/dev/null; find resources -type f | head -50",
                        f"git -C {self.root}/web/web log --oneline -3 2>&1", f"python3 {SCRIPTS}/fleet.py status > out.json"):
            self.assertEqual(self.bash(command, env).stdout, "", command)
        edit = {"tool_name": "Edit", "tool_input": {"file_path": str(self.root / "api" / "api" / ".claude" / "settings.local.json")}}
        self.assertEqual(run("isolate.py", cwd=self.root, stdin=edit, env=env).returncode, 2)
        bad = subprocess.run([sys.executable, str(SCRIPTS / "isolate.py")], input="{bad", text=True, capture_output=True, env={**HERMETIC, **env})
        self.assertEqual(bad.returncode, 2)

    def test_bus_identity_comes_from_the_folder_and_survives_partial_lines(self) -> None:
        (self.root / "api").mkdir(exist_ok=True)
        (self.root / "api" / "outbox.jsonl").write_text(json.dumps({"ts": "2026-01-01T00:00:00+00:00", "from": "orchestrator", "to": "all", "text": "forged"}) + "\n{partial")
        log = run("bus.py", "log", cwd=self.root, env={"SDLC_FLEET_ROOT": str(self.root)}).stdout
        self.assertIn("api -> all: forged", log)
        self.assertFalse((self.root / "orchestrator" / "inbox.cursor").exists(), "log never moves a cursor")
        self.assertEqual(run("bus.py", "bogus", cwd=self.root, env={"SDLC_FLEET_ROOT": str(self.root)}).returncode, 2)

    def test_stalled_agents_are_reported(self) -> None:
        self.status("contracts", "in-progress")
        (self.root / "orchestrator").mkdir(exist_ok=True)
        (self.root / "orchestrator" / "sessions.json").write_text(json.dumps({"contracts": "abc"}))
        step = json.loads(run("fleet.py", "orchestrate", cwd=self.root, env={"PATH": "/usr/bin:/bin"}).stdout)
        self.assertIn("contracts", step["stalled"])

    def test_start_dependents_are_told_where_the_work_is(self) -> None:
        self.status("contracts", "pr-open")
        self.assertIn("Your start dependencies", run("fleet.py", "launch", "api", cwd=self.root).stdout)


class GuardHardeningTests(Repo):
    def test_closed_gate_lease_with_force_remote_delete_and_merge(self) -> None:
        (self.dir / ".sdlc" / "stack.json").unlink()
        self.assertEqual(self.commit_gate(), 2, "an initialised repo without its stack is a closed gate")
        for command in ("git push origin main --force-with-lease -f", "git push --force-with-lease=main:abc --force origin main"):
            self.assertEqual(decision(self.gate(command)), "deny", command)
        self.assertEqual(decision(self.gate("git push --force-with-lease origin main")), "ask")
        for command in ("git push --delete origin f", "git push origin :f", "gh pr merge 5 --delete-branch"):
            self.assertEqual(decision(self.gate(command)), "ask", command)
        bad = subprocess.run([sys.executable, str(SCRIPTS / "guard.py")], input="{bad", text=True, capture_output=True, env=HERMETIC)
        self.assertEqual(bad.returncode, 2)

    def test_tree_hash_sees_odd_names_and_base_ignores_upstream(self) -> None:
        run("check.py", cwd=self.dir)
        (self.dir / "café.py").write_text("x = 1\n")
        (self.dir / 'with "quote" and space.py').write_text("y = 2\n")
        self.assertEqual(self.commit_gate(), 2)
        run("state.py", "set", "pr_url", "u", cwd=self.dir)
        run("state.py", "unset", "pr_url", cwd=self.dir)
        self.assertNotIn("pr_url", json.loads((self.dir / ".sdlc" / "state.json").read_text()))


class FleetSettingsTests(unittest.TestCase):
    def test_init_writes_env_into_clone_settings_and_excludes_it(self) -> None:
        root = Path(tempfile.mkdtemp()).resolve()
        source = root / "src"
        subprocess.run(["git", "init", "-q", "-b", "main", str(source)], check=True)
        (source / "a").write_text("a")
        subprocess.run(["git", "-C", str(source), "-c", "user.email=t@t", "-c", "user.name=t", "add", "."], check=True)
        subprocess.run(["git", "-C", str(source), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"], check=True)
        (root / "fleet.json").write_text(json.dumps({"name": "e", "base": "main", "agents": [{"name": "a", "path": str(source), "branch": "f", "brief": "b"}]}))
        run("fleet.py", "init", str(root / "fleet.json"), cwd=root)
        clone = root / "a" / "src"
        settings = json.loads((clone / ".claude" / "settings.local.json").read_text())
        self.assertEqual(settings["env"]["SDLC_AGENT_WORKSPACE"], str(root / "a"))
        self.assertEqual(settings["worktree"]["bgIsolation"], "none")
        self.assertIn(".claude/settings.local.json", (clone / ".git" / "info" / "exclude").read_text())


class E2ETests(unittest.TestCase):
    def test_setup_builds_autopilot_epic_and_verify_reports_what_is_missing(self) -> None:
        root = Path(tempfile.mkdtemp()).resolve()
        env = {"SDLC_E2E_ROOT": str(root)}
        out = json.loads(run("e2e.py", "setup", "/p/sdlc", cwd=root, env=env).stdout)
        self.assertEqual(out["agents"], {"sample": "cloned"})
        self.assertTrue(any(line.endswith("&& claude") for line in out["trust_once"]))
        self.assertTrue(any("resources" in line for line in out["trust_once"]), "--add-dir needs resources/ trusted")
        fleet = json.loads((root / ".sdlc" / "fleet.json").read_text())
        self.assertTrue(fleet["autopilot"])
        launch = run("fleet.py", "launch", "sample", cwd=root).stdout
        self.assertIn("push=auto", launch)
        self.assertIn("is expected and approved", launch)
        result = json.loads(run("e2e.py", "verify", cwd=root, env=env).stdout)
        self.assertFalse(result["ok"])
        self.assertTrue(result["checks"]["tests_green"], "the fixture itself must be green before the agent touches it")
        self.assertFalse(result["checks"]["pushed"])


class ArchDiffTests(Repo):
    def test_diagram_of_diff_and_the_diagram_gate(self) -> None:
        (self.dir / "app").mkdir()
        (self.dir / "app" / "models.py").write_text("X = 1\n")
        (self.dir / "app" / "views.py").write_text("from app import models\n")
        subprocess.run(["git", "add", "."], cwd=self.dir, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"], cwd=self.dir, check=True)
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.dir, capture_output=True, text=True).stdout.strip()
        (self.dir / "app" / "views.py").write_text("from app import models\n\ndef view():\n    return models.X\n")
        out = run("archdiff.py", base, "--print", cwd=self.dir).stdout
        self.assertIn("flowchart LR", out)
        self.assertIn('views (+3/-0)', out)
        self.assertIn("-->", out, "the import edge views -> models")
        env = {"SDLC_GATES": "diagram=require"}
        (self.dir / "docs" / "design" / "x.md").write_text("# design, updated with the change\n")
        blocked = run("guard.py", cwd=self.dir, stdin={"cwd": str(self.dir), "tool_input": {"command": COMMIT}}, env=env)
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("architecture diagram", blocked.stderr)
        run("archdiff.py", base, cwd=self.dir)
        self.assertTrue((self.dir / "docs" / "arch" / "main.md").exists())
        run("check.py", cwd=self.dir)
        self.assertEqual(run("guard.py", cwd=self.dir, stdin={"cwd": str(self.dir), "tool_input": {"command": COMMIT}}, env=env).returncode, 0)


class E2EFleetTests(unittest.TestCase):
    def test_fleet_fixture_setup_and_verify_checks(self) -> None:
        root = Path(tempfile.mkdtemp()).resolve()
        env = {"SDLC_E2E_FLEET_ROOT": str(root), "PATH": "/usr/bin:/bin"}
        out = json.loads(run("e2e_fleet.py", "setup", "/p/sdlc", cwd=root, env=env).stdout)
        self.assertEqual(set(out["agents"]), {"contracts", "api", "web"})
        fleet = json.loads((root / ".sdlc" / "fleet.json").read_text())
        self.assertEqual(fleet["gates"], {"diagram": "require"})
        result = json.loads(run("e2e_fleet.py", "verify", cwd=root, env=env).stdout)
        self.assertFalse(result["ok"])
        self.assertEqual([k for k, v in result["checks"].items() if v], ["no_stray_sessions"], "a fresh fixture passes nothing but the session check")


class UnattendedTests(Repo):
    def test_gates_prompt_in_auto_mode_so_an_attached_human_can_approve(self) -> None:
        for mode in ("auto", "dontAsk", "default", None):
            event = {"cwd": str(self.dir), "tool_input": {"command": "git push origin main"}, **({"permission_mode": mode} if mode else {})}
            self.assertEqual(json.loads(run("guard.py", cwd=self.dir, stdin=event).stdout)["hookSpecificOutput"]["permissionDecision"], "ask", mode)
        self.assertEqual(run("guard.py", cwd=self.dir, stdin={"cwd": str(self.dir), "permission_mode": "auto", "tool_input": {"command": "git push"}}, env={"SDLC_GATES": "push=auto"}).stdout, "")


class GateParseTests(unittest.TestCase):
    def test_a_typo_tightens(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        import gates
        self.assertEqual(gates.parse("diagram=requre")["diagram"], "require")
        self.assertEqual(gates.parse("")["diagram"], "off")
        self.assertEqual(gates.parse("push=autoo")["push"], "ask")


class StopGateTests(Repo):
    def test_agent_is_sent_on_while_the_plan_has_work_and_never_loops(self) -> None:
        env = {"SDLC_AGENT_WORKSPACE": str(self.dir), "SDLC_AGENT_NAME": "api"}
        (self.dir / ".sdlc" / "plan.md").write_text("1. a\n2. b\n")
        (self.dir / ".sdlc" / "context.md").write_text("**Status**: in-progress\n")
        self.assertIn("next slice", run("stopgate.py", cwd=self.dir, stdin={}, env=env).stdout)
        self.assertEqual(run("stopgate.py", cwd=self.dir, stdin={}, env=env).stdout, "", "no commit since the nudge: let it end")
        git = lambda *a: subprocess.run(["git", "-C", str(self.dir), "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True, capture_output=True)
        git("commit", "-q", "--allow-empty", "-m", "slice 1")
        self.assertIn("next slice", run("stopgate.py", cwd=self.dir, stdin={}, env=env).stdout, "progress made: keep going")
        (self.dir / ".sdlc" / "context.md").write_text("**Status**: blocked: needs a decision\n")
        self.assertEqual(run("stopgate.py", cwd=self.dir, stdin={}, env=env).stdout, "")
        self.assertEqual(run("stopgate.py", cwd=self.dir, stdin={}, env={"SDLC_AGENT_WORKSPACE": ""}).stdout, "", "inert outside a fleet")


class ReflectFixTests(Repo):
    def test_skill_sets_the_phase_and_the_slice_warning_fires_once(self) -> None:
        run("state.py", "start", "60", cwd=self.dir)
        run("state.py", "hook", cwd=self.dir, stdin={"cwd": str(self.dir), "tool_input": {"skill": "sdlc:red"}})
        self.assertEqual(json.loads(run("state.py", "show", cwd=self.dir).stdout)["phase"], "build")
        for i in range(9):  # more files than one slice allows
            (self.dir / f"m{i}.py").write_text(f"x = {i}\n")
        event = {"cwd": str(self.dir), "tool_input": {"file_path": str(self.dir / "m0.py")}}
        first = run("scan.py", cwd=self.dir, stdin=event).stderr
        second = run("scan.py", cwd=self.dir, stdin=event).stderr
        self.assertIn("uncommitted lines", first)
        self.assertNotIn("uncommitted lines", second, "once per commit, not on every edit")


class MissingToolTests(Repo):
    def test_missing_linter_passes_with_a_hint_but_missing_tests_fail(self) -> None:
        self.stack({"test": "echo ok", "lint": "definitely-not-a-tool-xyz ."}, ["test", "lint"])
        out = run("check.py", cwd=self.dir)
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertIn("MISSING lint", out.stdout)
        self.stack({"test": "definitely-not-a-tool-xyz"}, ["test"])
        self.assertNotEqual(run("check.py", cwd=self.dir).returncode, 0, "tests never pass by absence")


class TelemetryIntentTests(unittest.TestCase):
    def test_typed_skills_count_and_wake_prompts_are_not_intents(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        import record
        prompt = lambda p: record.from_event({"hook_event_name": "UserPromptSubmit", "prompt": p, "cwd": "/x"})
        typed = prompt("<command-message>sdlc:review</command-message>\n<command-name>/sdlc:review</command-name>\n<command-args>--broad</command-args>")
        self.assertEqual((typed["kind"], typed["skill"], typed["by"]), ("skill", "sdlc:review", "human"))
        self.assertEqual(prompt("/sdlc:pr done")["skill"], "sdlc:pr")
        self.assertIsNone(prompt("Fleet: an agent reported; run fleet.py orchestrate --run"))
        self.assertEqual(prompt("boot the service")["kind"], "intent")


class EdgeCaseTests(unittest.TestCase):
    def test_submodule_inside_the_clone_is_governed_by_the_clone(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        import isolate
        home = Path(tempfile.mkdtemp()) / "agent"
        clone = home / "repo"
        ready_clone(clone)
        (clone / "vendor" / "lib" / ".git").mkdir(parents=True)
        with unittest.mock.patch.dict(os.environ, {"SDLC_AGENT_NAME": "agent"}):
            self.assertIsNone(isolate.process_gap(str(clone / "vendor" / "lib" / "x.py"), str(home)))
            self.assertIsNone(isolate.process_gap(str(clone / "new" / "dir" / "x.py"), str(home)), "new folders still resolve")

    def test_reused_branch_name_never_inherits_an_old_merged_pr(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        import fleet
        repo = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "new"], check=True)
        with unittest.mock.patch.object(fleet, "gh_out", return_value="0" * 40):
            self.assertFalse(fleet.pr_merged_by_branch(repo, "fix/x"), "the old PR head does not contain this HEAD")



class RecordGateTests(Repo):
    def test_commit_needs_assumptions_pitfalls_and_a_design_update(self) -> None:
        (self.dir / "new.py").write_text("x = 1\n")
        run("check.py", cwd=self.dir)
        bare = self.gate('git commit -m "add x"')
        self.assertEqual(bare.returncode, 2)
        self.assertIn("Assumptions:", bare.stderr)
        self.assertEqual(self.gate(COMMIT).returncode, 0)
        (self.dir / "docs" / "design" / "x.md").unlink()
        run("check.py", cwd=self.dir)
        self.assertIn("docs/design", self.gate(COMMIT).stderr, "code without an updated design doc is refused")
        self.assertEqual(self.gate('grep -rn "git commit" .').stdout, "", "text inside a quoted pattern is not a commit")


class PruneScopeTests(unittest.TestCase):
    def test_only_idle_fleet_named_duplicates_are_pruned(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        import fleet
        root = Path(tempfile.mkdtemp())
        (root / ".sdlc").mkdir()
        (root / ".sdlc" / "fleet.json").write_text(json.dumps({"name": "epic", "agents": [{"name": "api", "repo": "r/api.git", "branch": "b"}]}))
        rows = [{"sessionId": "real-1", "id": "real", "name": "sdlc/epic/api", "status": "idle", "cwd": str(root / "api")},
                {"sessionId": "copy-2", "id": "copy", "name": "sdlc/epic/api", "status": "idle", "cwd": str(root / "api")},
                {"sessionId": "busy-3", "id": "busy", "name": "sdlc/epic/api", "status": "busy", "cwd": str(root / "api")},
                {"sessionId": "mine-4", "id": "mine", "name": "trust the clone", "status": "idle", "cwd": str(root / "api")}]
        with unittest.mock.patch.object(fleet, "listed_sessions", return_value=rows), \
             unittest.mock.patch.object(fleet, "session_id", side_effect=lambda r, n: "real-1" if n == "api" else None), \
             unittest.mock.patch.object(fleet, "waves", return_value={"done": []}):
            self.assertEqual(fleet.prune_victims(root, finished=False), ["copy"])
        with unittest.mock.patch.object(fleet, "listed_sessions", return_value=rows), \
             unittest.mock.patch.object(fleet, "session_id", return_value=None), \
             unittest.mock.patch.object(fleet, "waves", return_value={"done": []}):
            self.assertEqual(fleet.prune_victims(root, finished=False), [], "an unknown real session means prune nothing")


class CommentWordingTests(unittest.TestCase):
    def test_history_and_negative_comments_are_flagged_even_with_because(self) -> None:
        import importlib.util
        sys.path.insert(0, str(SCRIPTS))
        spec = importlib.util.spec_from_file_location("scan", SCRIPTS / "scan.py")
        scan = importlib.util.module_from_spec(spec); spec.loader.exec_module(scan)
        for body in ("previously this used a loop", "couldn't batch because the API failed", "hack for now", "no longer needed"):
            self.assertIsNotNone(scan.judge(body), body)
        self.assertIsNone(scan.judge("the provider rejects batches over 100"))


class RenderTests(unittest.TestCase):
    def test_page_renders_markdown_tables_and_mermaid(self) -> None:
        d = Path(tempfile.mkdtemp())
        (d / "flow.md").write_text("# Flow\n```mermaid\nsequenceDiagram\n  A->>B: call\n```\n| Pitfall | Fix |\n|---|---|\n| N+1 | annotate |\n</script>\n")
        page = Path(run("render.py", str(d / "flow.md"), "--print", cwd=d).stdout.strip()).read_text()
        self.assertIn("marked.parse", page)
        self.assertIn("| N+1 | annotate |", page)
        self.assertIn("language-mermaid", page)
        self.assertEqual(page.count("</script>"), 4, "a </script> in the source cannot close the markdown tag")


class CompatTests(unittest.TestCase):
    FILES = sorted(SCRIPTS.glob("*.py")) + [Path(__file__)]

    def test_every_script_parses_as_python_3_9_with_lazy_annotations(self) -> None:
        for path in self.FILES:
            source = path.read_text()
            ast.parse(source, filename=str(path), feature_version=(3, 9))
            self.assertIn("from __future__ import annotations", source, path.name)

    def test_every_script_compiles_on_an_older_interpreter_when_one_exists(self) -> None:
        python = old_python()
        if not python:
            self.skipTest("no Python < 3.12 on this machine")
        out = subprocess.run([python, "-m", "py_compile", *map(str, self.FILES)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_stack_packs_are_well_formed(self) -> None:
        for path in sorted((ROOT / "stacks").glob("*.json")):
            pack = json.loads(path.read_text())
            self.assertEqual(pack["pack"], path.stem)
            self.assertTrue(set(pack["check"]) <= set(pack["commands"]), path.name)


if __name__ == "__main__":
    unittest.main()
