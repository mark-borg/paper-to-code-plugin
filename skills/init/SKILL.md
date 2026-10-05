---
name: init
description: Scaffold a new paper-to-code project around a paper PDF. Sets up the uv package, test/lint/jupytext config, the notebook consistency test, and a CLAUDE.md whose method, expected-results and fidelity sections are drafted from the paper for the user to confirm.
argument-hint: <paper.pdf> [package_name]
disable-model-invocation: true
---

# Scaffold a paper-to-code project

Arguments: $ARGUMENTS (the paper PDF path, plus an optional package name)

Templates are in `${CLAUDE_PLUGIN_ROOT}/skills/init/templates/`. Work in the current directory.
**Never overwrite an existing file without asking.** If a file already exists, merge into it (for
example, append missing `pyproject.toml` tables) or ask.

## 1. Pre-flight
- Check that the PDF exists. If no path was given, look for a single `*.pdf` in the current directory,
  or ask.
- Check that `uv` and `git` are installed (`uv --version`, `git --version`). If the directory is not a
  git repo, ask before running `git init`.
- Choose the package name: use the argument if given; otherwise propose a short snake_case name from
  the paper's topic and confirm it with the user.

## 2. Package and tooling
1. If there is no `pyproject.toml`, run `uv init --package --name <package> --python 3.12`. The
   package must end up under `src/<package>/`.
2. Add the dependencies:
   - `uv add numpy scipy matplotlib`. Add others only if the method clearly needs them, e.g.
     scikit-image or pandas.
   - `uv add --dev pytest ruff jupytext nbconvert nbmake ipykernel jupyterlab`. `jupytext --execute`
     needs `nbconvert`.
3. Append the tables from `templates/pyproject-tools.toml` that are missing from `pyproject.toml`. Set
   ruff's `target-version` to match the Python version.
4. Copy `templates/test_notebooks.py` to `tests/test_notebooks.py`. Create `notebooks/`, adding
   `notebooks/.gitkeep` if it is empty.
5. Merge `templates/gitignore` into `.gitignore`.
6. Run `uv sync` and then `uv run pytest -q`. With no notebooks, the two notebook tests are reported
   as skipped (empty parameter set); check that nothing errors.

## 3. Draft CLAUDE.md from the paper
Read the paper with the Read tool, in page ranges. Then fill in `templates/CLAUDE.md.template` and
write it to `CLAUDE.md`. If a `CLAUDE.md` already exists, show the new sections and ask before merging.
- `{{PDF_FILENAME}}`, `{{CITATION}}`: from the PDF: authors, title, venue, year and DOI.
- `{{AVAILABILITY}}`: whether the paper's data or code are available, with links if any. If you cannot
  verify availability, say so and default to "validate on synthetic data".
- `{{PYTHON_VERSION}}`, `{{PACKAGE}}`: from step 2.
- `{{NOTEBOOK_PLAN}}`: one numbered notebook per major part of the paper, e.g.
  "method → experiment 1 analogue of Figs. 2–3 → experiment 2 analogue of Figs. 4–5".
- `{{METHOD}}`: the equations to implement, section by section, citing the equation numbers. Cover:
  - data layout and array conventions (shapes, and which axis is which);
  - the core algorithm;
  - numerical requirements.

  Be concrete: the developer implements from this section.
- `{{EXPECTED_RESULTS}}`: what the paper reports (numbers from tables and figures), how synthetic data
  should be built to reproduce each result, and what tests should check.
- `{{FIDELITY_CHECKLIST}}`: 5–15 one-line, checkable items for the reviewer, each citing an Eq./Sec.

Remove the HTML guidance comments once each section is filled. Wherever the paper is ambiguous, write
`TODO(confirm): <question>` instead of guessing.

## 4. Hand back
Report:
- the files created or changed;
- the drafted CLAUDE.md sections, with every `TODO(confirm)` listed;
- a suggested first task for `/paper-to-code:dev-review`, usually the core method from the first
  notebook in the plan.

Ask the user to review CLAUDE.md, especially "The method", "Expected results" and "Fidelity
checklist", before the first `/paper-to-code:dev-review`.

Then offer to commit the scaffold (including the reviewed CLAUDE.md and the paper PDF), but only
commit if the user says so. `/paper-to-code:dev-review` needs a clean working tree with at least one
commit: otherwise it stops at its pre-flight check, and the reviewer would see the whole scaffold as
part of the first task's diff.
