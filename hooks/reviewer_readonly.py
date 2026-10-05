#!/usr/bin/env python3
"""PreToolUse hook: keep the paper-to-code reviewer agent read-only.

Registered plugin-wide in hooks/hooks.json for every Bash call. The hook input carries
`agent_type` when the call comes from a subagent, so only the reviewer's calls are checked;
the main session and the developer are never affected.

Reads the hook payload (JSON) from stdin. Exit 0 allows the command; exit 2 blocks it and
the stderr message is fed back to the reviewer. Allowlist-based: anything not recognised is
blocked, and any error while checking a reviewer command blocks it too (Claude Code treats
other non-zero exits as "allow"). Stdlib only, Python 3.9+, because it runs under whatever
`python3` is on PATH.

Set PAPER_TO_CODE_HOOK_DEBUG=/path/to/log to append each call's agent_type and verdict.
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

REVIEWER_AGENT_TYPES = {"paper-to-code:reviewer"}
GIT_READ_SUBCOMMANDS = {"status", "diff", "log", "show", "ls-files", "blame", "rev-parse"}
PIPE_FILTERS = {"head", "tail", "grep", "wc"}
SEPARATORS = {"&&", "||", "|", ";"}
# Newline is an operator too: bash runs each line as a separate command.
OPERATOR_CHARS = "();<>|&\n"
# Flags allowed between `uv run` and the tool; none of them run anything else.
UV_RUN_FLAGS = {"--frozen", "--locked", "--no-sync", "--offline"}
# pytest flags that write files (or upload results), plus nbmake's --overwrite. Ini overrides
# are blocked too: `-o addopts=--overwrite` would re-enable any of them.
PYTEST_WRITE_FLAGS = (
    "--overwrite",
    "--junitxml",
    "--junit-xml",
    "--basetemp",
    "--report-log",
    "--debug",
    "--pastebin",
    "--override-ini",
)
PYTEST_WRITE_SHORT = "o"
# ruff check flags that write files or never return. Inline config is blocked too:
# `--config 'fix = true'` applies fixes.
RUFF_CHECK_WRITE_FLAGS = (
    "--fix",
    "--fix-only",
    "--unsafe-fixes",
    "--add-noqa",
    "--output-file",
    "--watch",
    "--config",
)
RUFF_CHECK_WRITE_SHORT = "ow"
# Leading VAR=value assignments, e.g. `MYPKG_TEST_SEEDS=28 uv run pytest`.
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=[^;&|<>`$()]*$")
# Variables that change which program runs, how a tool behaves, or where it writes are never
# allowed as prefixes (e.g. PYTEST_ADDOPTS=--overwrite, GIT_PAGER=..., RUFF_OUTPUT_FILE=...).
UNSAFE_ENV = re.compile(
    r"^(PATH|HOME|IFS|ENV|BASH_ENV|SHELL|PAGER|EDITOR|VISUAL|VIRTUAL_ENV"
    r"|(PYTHON|LD_|DYLD_|UV_|GIT_|PYTEST_|RUFF_|JUPYTER|XDG_|LESS)[A-Za-z0-9_]*)="
)
NB_FIGURES = os.path.realpath(Path(__file__).parent.parent / "scripts" / "nb_figures.py")


def has_flag(args, flags, short=""):
    """True if any arg is one of the long `flags` (alone or as `--flag=value`), or a short-option
    group containing one of the letters in `short` (`-o`, `-ovalue`, `-qo`)."""
    return any(
        any(a == f or a.startswith(f + "=") for f in flags)
        or (re.match(r"^-[A-Za-z]", a) and any(c in a[1:] for c in short))
        for a in args
    )


def segment_allowed(tokens):
    has_env = False
    while tokens and ENV_ASSIGNMENT.match(tokens[0]):
        if UNSAFE_ENV.match(tokens[0]):
            return False
        has_env, tokens = True, tokens[1:]
    if not tokens:
        return False
    if has_env and tokens[:2] != ["uv", "run"]:
        return False  # prefixes are only for configuring tests
    cmd, args = tokens[0], tokens[1:]
    if cmd == "tail":
        # -f/-F/--follow never return.
        return not has_flag(args, ("--follow",), short="fF")
    if cmd in PIPE_FILTERS or cmd in {"ls", "pwd"}:
        return True
    if cmd == "git":
        return (
            len(args) > 0
            and args[0] in GIT_READ_SUBCOMMANDS
            and not any(a.startswith("--output") for a in args)
        )
    if cmd == "python3" and len(args) > 0 and os.path.realpath(args[0]) == NB_FIGURES:
        return True  # extracts notebook figures to a temp dir outside the repo, for Read
    if tokens[:2] == ["uv", "run"]:
        rest = tokens[2:]
        while rest and rest[0] in UV_RUN_FLAGS:
            rest = rest[1:]
        if not rest:
            return False
        tool, args = rest[0], rest[1:]
        if tool == "pytest":
            return not has_flag(args, PYTEST_WRITE_FLAGS, PYTEST_WRITE_SHORT)
        if tool == "ruff" and args[:1] == ["check"]:
            return not has_flag(args, RUFF_CHECK_WRITE_FLAGS, RUFF_CHECK_WRITE_SHORT)
        if tool == "ruff" and args[:1] == ["format"]:
            return "--check" in args or "--diff" in args
        if tool == "python" and args[:1] in (["-c"], ["-m"]):
            # Needed for counter-examples. python -c can still write files (accepted risk).
            return args[:1] == ["-c"] or (
                args[1:2] == ["pytest"]
                and not has_flag(args[2:], PYTEST_WRITE_FLAGS, PYTEST_WRITE_SHORT)
            )
    return False


def check(command):
    """Return None if allowed, else a reason string."""
    if "`" in command or "$(" in command:
        return "command substitution is not allowed"
    lexer = shlex.shlex(command.replace("2>&1", ""), posix=True, punctuation_chars=OPERATOR_CHARS)
    lexer.whitespace = " \t\r"  # not "\n": it is a command separator (see OPERATOR_CHARS)
    lexer.whitespace_split = True
    lexer.commenters = ""  # a `# comment` would otherwise swallow the newline that ends it
    try:
        tokens = list(lexer)
    except ValueError as exc:
        return f"could not parse command ({exc})"
    segment = []
    for tok in tokens + [";"]:
        if set(tok) <= set(OPERATOR_CHARS):
            op = tok.replace("\n", "")
            if op and op not in SEPARATORS:
                return f"shell operator '{op}' (redirection/subshell/background) is not allowed"
            if segment and not segment_allowed(segment):
                return f"'{' '.join(segment)}' is not on the reviewer's read-only allowlist"
            segment = []
        else:
            segment.append(tok)
    return None


def debug(agent_type, verdict):
    path = os.environ.get("PAPER_TO_CODE_HOOK_DEBUG")
    if path:
        try:
            with open(path, "a") as f:
                f.write(f"{agent_type!r}\t{verdict}\n")
        except OSError:
            pass


def block(reason):
    print(
        f"Blocked: {reason}. The reviewer is read-only. Allowed: git status/diff/log/show/"
        "ls-files/blame/rev-parse, uv run pytest (optionally with VAR=value prefixes; no "
        "--overwrite/--junitxml/--basetemp/-o), uv run ruff check (no --fix/--output-file/"
        "--config), "
        "uv run ruff format --check, uv run python -c, "
        f"python3 {NB_FIGURES} <notebook.ipynb>, ls, pwd, and pipes into head/tail/grep/wc "
        "(no tail -f). One command per line or joined with && || ; |. "
        "Use Read/Grep/Glob to inspect files.",
        file=sys.stderr,
    )
    sys.exit(2)


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
        agent_type = payload.get("agent_type")
    except (ValueError, AttributeError) as exc:
        # The caller is unknown. Fail closed only if it may be the reviewer, so that a
        # malformed payload never blocks the main session or the developer.
        if any(t in raw for t in REVIEWER_AGENT_TYPES):
            block(f"could not parse the hook input ({exc})")
        sys.exit(0)
    if agent_type not in REVIEWER_AGENT_TYPES:
        debug(agent_type, "not-reviewer")
        sys.exit(0)
    try:
        reason = check(payload.get("tool_input", {}).get("command", ""))
    except Exception as exc:  # never fail open for the reviewer
        reason = f"the read-only hook failed ({exc!r})"
    debug(agent_type, f"blocked: {reason}" if reason else "allowed")
    if reason:
        block(reason)
    sys.exit(0)


if __name__ == "__main__":
    main()
