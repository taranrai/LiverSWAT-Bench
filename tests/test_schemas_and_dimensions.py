from __future__ import annotations

import math

from liverswat_bench.evaluation import DEFAULT_ANCHORS, PROVISIONAL_WEIGHTS, Dimension
from liverswat_bench.schemas import SCHEMA_MODELS, render_schema
from tests.conftest import REPO_ROOT


def test_committed_json_schemas_are_up_to_date():
    for filename, model in SCHEMA_MODELS.items():
        committed = (REPO_ROOT / "schemas" / filename).read_text()
        assert committed == render_schema(model), (
            f"schemas/{filename} is stale; run: python scripts/export_schemas.py"
        )


def test_weights_cover_all_dimensions_and_sum_to_one():
    assert set(PROVISIONAL_WEIGHTS) == set(Dimension)
    assert math.isclose(sum(PROVISIONAL_WEIGHTS.values()), 1.0)


def test_default_anchors_cover_0_to_4():
    for dim in Dimension:
        assert set(DEFAULT_ANCHORS[dim]) == {0, 1, 2, 3, 4}
