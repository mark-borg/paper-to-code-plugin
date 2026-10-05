"""Tests for hooks/reviewer_readonly.py. Run with: python3 -m unittest discover tests"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "reviewer_readonly.py"
sys.path.insert(0, str(HOOK.parent))

import reviewer_readonly as hook  # noqa: E402

ALLOWED = [
    "git status --short",
    "git diff HEAD",
    "git ls-files --others --exclude-standard",
    "git log --oneline -5 | head -3",
    "uv run pytest -q",
    "uv run pytest -q 2>&1 | tail -5",
    "uv run pytest --nbmake notebooks/ -q",
    "MYPKG_TEST_SEEDS=28 uv run pytest -q tests/test_x.py",
    "uv run --frozen pytest -q",
    "uv run ruff check .",
    "uv run ruff format --check .",
    "uv run python -m pytest -q",
    'uv run python -c "import numpy as np\nprint(np.zeros(3))"',
    f"python3 {hook.NB_FIGURES} notebooks/01_method.ipynb",
    "git status && git diff\nls -la",
    "grep -n foo src/pkg/core.py | wc -l",
    'uv run pytest -x -q -k "solo or robust" tests/',
    "uv run ruff check . --no-fix --statistics",
    "uv run pytest -q | tail -n 20",
]

BLOCKED = [
    # newline and comment tricks
    "git status\nrm -rf src",
    "ls\ntouch pwned",
    "ls # comment\nrm x",
    "git log;\nrm x",
    # env prefixes that change tool behaviour
    "PYTEST_ADDOPTS=--overwrite uv run pytest --nbmake notebooks/",
    "GIT_EXTERNAL_DIFF=/tmp/x.sh git diff --ext-diff",
    "GIT_PAGER='touch pwned' git log",
    "RUFF_OUTPUT_FILE=src/x.py uv run ruff check .",
    "PATH=/tmp uv run pytest",
    "FOO=1 git status",
    # flags that write files
    "uv run pytest --nbmake --overwrite notebooks/",
    "uv run python -m pytest --nbmake --overwrite notebooks/",
    "uv run pytest --junitxml=src/pkg/__init__.py",
    "uv run pytest --basetemp src",
    "uv run ruff check . --fix",
    "uv run ruff check . --output-file src/pkg/__init__.py",
    "uv run ruff check . -o out.txt",
    "uv run ruff format .",
    # inline config overrides that re-enable writes
    "uv run pytest -o addopts=--overwrite --nbmake notebooks/",
    "uv run pytest -oaddopts=--junitxml=x.xml",
    "uv run pytest -qo addopts=--overwrite",
    "uv run pytest --override-ini=cache_dir=src",
    "uv run python -m pytest -o addopts=--overwrite",
    "uv run ruff check . --config 'fix = true'",
    "uv run ruff check . --config=fix=true",
    "uv run ruff check -oout.txt .",
    "git diff --output=patch.txt",
    # never returns
    "tail -f log.txt",
    "uv run pytest | tail -F",
    # operators and substitution
    "git log --oneline 2>/dev/null",
    "ls > out.txt",
    "ls &",
    "(rm x)",
    "echo $(rm x)",
    "echo `rm x`",
    # not on the list
    "rm -rf src",
    "uv run jupytext --sync notebooks/01.py",
    "uv run --with evil pytest",
    "python3 /tmp/nb_figures.py notebooks/01.ipynb",
    "git checkout .",
    "git -c core.pager=sh diff",
]


def run_hook(stdin):
    return subprocess.run(
        [sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True
    )


class TestCheck(unittest.TestCase):
    def test_allowed(self):
        for cmd in ALLOWED:
            with self.subTest(cmd=cmd):
                self.assertIsNone(hook.check(cmd))

    def test_blocked(self):
        for cmd in BLOCKED:
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(hook.check(cmd))


class TestMain(unittest.TestCase):
    def payload(self, agent_type, command):
        data = {"tool_name": "Bash", "tool_input": {"command": command}}
        if agent_type:
            data["agent_type"] = agent_type
        return json.dumps(data)

    def test_reviewer_blocked_with_exit_2(self):
        result = run_hook(self.payload("paper-to-code:reviewer", "rm -rf src"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("read-only", result.stderr)

    def test_reviewer_allowed(self):
        result = run_hook(self.payload("paper-to-code:reviewer", "git status"))
        self.assertEqual(result.returncode, 0)

    def test_other_agents_unaffected(self):
        for agent_type in (None, "paper-to-code:developer", "reviewer"):
            with self.subTest(agent_type=agent_type):
                result = run_hook(self.payload(agent_type, "rm -rf src"))
                self.assertEqual(result.returncode, 0)

    def test_malformed_payload_fails_closed_only_for_reviewer(self):
        self.assertEqual(run_hook('{"agent_type": "paper-to-code:reviewer"').returncode, 2)
        self.assertEqual(run_hook("not json").returncode, 0)

    def test_non_string_command_fails_closed(self):
        payload = {"agent_type": "paper-to-code:reviewer", "tool_input": {"command": 1}}
        result = run_hook(json.dumps(payload))
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
