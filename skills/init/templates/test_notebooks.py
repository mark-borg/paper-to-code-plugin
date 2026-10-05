"""Consistency checks for notebooks/.

Each .ipynb must match its jupytext .py pair, and its outputs must come from one top-to-bottom run.
These checks cannot detect outputs left stale by `jupytext --sync` without `--execute`, so always
sync with `--execute`. Executing the notebooks is a separate step:
`uv run pytest --nbmake notebooks/`.
"""

from pathlib import Path

import jupytext
import pytest

NOTEBOOK_DIR = Path(__file__).resolve().parents[1] / "notebooks"
NOTEBOOKS = sorted(NOTEBOOK_DIR.glob("*.ipynb"))
SYNC_CMD = "uv run jupytext --sync --execute notebooks/{}"


def _cells(nb):
    return [(c.cell_type, c.source.strip()) for c in nb.cells if c.source.strip()]


@pytest.mark.parametrize("ipynb", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_matches_py_pair(ipynb):
    py = ipynb.with_suffix(".py")
    assert py.exists(), f"{py.name} missing: pair it with `uv run jupytext --sync {ipynb.name}`"
    assert _cells(jupytext.read(ipynb)) == _cells(jupytext.read(py)), (
        f"{ipynb.name} is out of sync with {py.name}: run `{SYNC_CMD.format(py.name)}`"
    )


@pytest.mark.parametrize("ipynb", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_executed_top_to_bottom(ipynb):
    cells = jupytext.read(ipynb).cells
    code_cells = [c for c in cells if c.cell_type == "code" and c.source.strip()]
    counts = [c.get("execution_count") for c in code_cells]
    assert counts == list(range(1, len(code_cells) + 1)), (
        f"{ipynb.name} outputs are missing or from a partial/out-of-order run "
        f"(execution counts {counts}): run `{SYNC_CMD.format(ipynb.with_suffix('.py').name)}`"
    )
