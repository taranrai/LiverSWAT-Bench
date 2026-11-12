"""Regenerate the JSON Schema files in ``schemas/`` from the Pydantic models.

Usage: python scripts/export_schemas.py
"""

from pathlib import Path

from liverswat_bench.schemas import export_schemas

if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "schemas"
    for path in export_schemas(out):
        print(f"wrote {path}")
