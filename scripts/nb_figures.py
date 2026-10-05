#!/usr/bin/env python3
"""Extract the embedded PNG/JPEG figures of a notebook so they can be viewed with the Read tool.

Usage: python3 nb_figures.py notebooks/NN_name.ipynb

Writes one image file per figure output to a fresh temporary directory outside the repository and
prints `cell <i> (code cell <k>): <path>` per figure, followed by the first line of that
cell's source as a hint. Never writes inside the repository. Stdlib only.
"""

import base64
import json
import sys
import tempfile
from pathlib import Path

# Base64 image outputs the Read tool can display (SVG is text, so read it from the .ipynb).
IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg"}


def main():
    if len(sys.argv) != 2 or not sys.argv[1].endswith(".ipynb"):
        sys.exit("usage: nb_figures.py <notebook.ipynb>")
    nb_path = Path(sys.argv[1])
    nb = json.loads(nb_path.read_text())
    out_dir = Path(tempfile.mkdtemp(prefix=f"nbfig-{nb_path.stem}-"))
    n_fig, code_index = 0, 0
    for i, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        code_index += 1
        source = "".join(cell.get("source", "")).strip().splitlines()
        hint = source[0][:80] if source else ""
        for j, output in enumerate(cell.get("outputs", [])):
            data = output.get("data", {})
            mime = next((m for m in IMAGE_TYPES if data.get(m)), None)
            if not mime:
                continue
            image = data[mime]
            if isinstance(image, list):
                image = "".join(image)
            path = out_dir / f"cell{i:03d}_out{j}.{IMAGE_TYPES[mime]}"
            path.write_bytes(base64.b64decode(image))
            n_fig += 1
            print(f"cell {i} (code cell {code_index}): {path}    # {hint}")
    print(f"{n_fig} figure(s) written to {out_dir}")


if __name__ == "__main__":
    main()
