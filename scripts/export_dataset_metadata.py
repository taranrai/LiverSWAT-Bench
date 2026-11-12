"""Regenerate data/dataset_metadata.json from the data files.

Usage: python scripts/export_dataset_metadata.py
"""

from pathlib import Path

from liverswat_bench.datasets.metadata import render

if __name__ == "__main__":
    data = Path(__file__).resolve().parent.parent / "data"
    (data / "dataset_metadata.json").write_text(render(data))
    print(f"wrote {data / 'dataset_metadata.json'}")
