# paper-to-code

A Claude Code plugin for reimplementing a research paper's method in Python. Implementation goes through
a **developer → reviewer agent loop**:
- the developer works test-first on synthetic data;
- results are presented in jupytext-paired notebooks;
- each round is checked against the paper by a fresh, read-only reviewer.

## What's in it

| Component | Name when invoked | Purpose |
|---|---|---|
| Skill | `/paper-to-code:init <paper.pdf> [package]` | Scaffold a project: uv package, ruff/pytest/jupytext config, notebook consistency test, and a `CLAUDE.md` drafted from the paper |
| Skill | `/paper-to-code:dev-review <task>` | Orchestrate developer → reviewer rounds (max 3) for one task, or a sequence of tasks |
| Agent | `paper-to-code:developer` | Tests first, implements in `src/<package>/`, presents results in a notebook, verifies, and hands back a structured report. Never commits |
| Agent | `paper-to-code:reviewer` | Reviews the uncommitted diff against the paper and returns `VERDICT: APPROVE \| CHANGES_REQUESTED` with evidence-backed findings |
| Hook | `PreToolUse` on Bash | Blocks any reviewer Bash command that is not on a read-only allowlist. Other agents and the main session are unaffected |
| Script | `scripts/nb_figures.py` | Extracts a notebook's figures to a temp dir so agents can view them with Read |
| Tests | `tests/test_reviewer_readonly.py` | Allowlist cases for the hook (stdlib `unittest`) |

## How the work is split

The plugin holds the **workflow**. Everything paper-specific lives in the project's `CLAUDE.md`, which
both agents read first. They rely on these sections:
- `Purpose`
- `Commands`
- `Code layout`
- `The method`
- `Expected results`
- `Fidelity checklist`

`/paper-to-code:init` writes them from a template and drafts the last three from the paper.

**Review those three sections before the first task.** They are the spec that the developer
implements and that the reviewer checks against.

## Requirements

- Claude Code with plugin support.
- `uv`, `git` and `python3` on PATH. The hook and the figure script use only the standard library.
- A project layout of `src/<package>/`, `tests/` and `notebooks/`, using pytest, ruff, jupytext and
  nbmake. `init` sets this up.

## Install

To try it for a single session:
```bash
claude --plugin-dir /path/to/paper-to-code-plugin
```

To install it permanently: the repo is also its own single-plugin marketplace
(`.claude-plugin/marketplace.json`), so run:
```
/plugin marketplace add /path/to/paper-to-code-plugin
/plugin install paper-to-code@paper-to-code
```

## Typical use

```
/paper-to-code:init "Smith 2024.pdf" smith_method
# review CLAUDE.md: The method, Expected results, Fidelity checklist; then commit the scaffold
/paper-to-code:dev-review core method of Sec. 2 (Eqs. 1-3) with a method notebook
```

To work through several tasks, ask the orchestrator to take them one by one. It asks once whether to
commit after each approval, then collects the leftover non-blocking findings into a final cleanup task.

## Notes

- Agents run on the session's model (`model: inherit`).
- The reviewer's read-only guard is a plugin-wide hook. It looks at `agent_type` in the hook input and
  acts only for `paper-to-code:reviewer`. To debug it, set
  `PAPER_TO_CODE_HOOK_DEBUG=/tmp/hook.log` before starting Claude Code; each Bash call's `agent_type`
  and verdict are appended to that file.
- The guard fails closed. If the hook errors on a reviewer command, the command is blocked, because
  Claude Code only blocks on exit code 2 and treats any other failure as "allow".
- The allowlist assumes the uv/pytest/ruff toolchain. If a project's `CLAUDE.md` defines other
  checks, the reviewer reports them as "not run (blocked by hook)" and the orchestrator runs them. To
  let the reviewer run them itself, extend `segment_allowed` in `hooks/reviewer_readonly.py`.
  `REVIEWER_AGENT_TYPES` only selects which agents the guard applies to.
- The hook's tests use only the standard library: `python3 -m unittest discover tests`. Run them
  after any change to the allowlist.

## License

MIT. See [LICENSE](LICENSE).
