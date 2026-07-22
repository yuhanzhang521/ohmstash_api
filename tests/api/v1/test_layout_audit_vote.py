from collections import Counter

from app.api.v1.endpoints import ai as ai_endpoint


def _grid_candidate(rows: int, cols: int) -> dict:
    cells = [
        {"position_identifier": f"R{row}C{col}", "is_empty": True}
        for row in range(1, rows + 1)
        for col in range(1, cols + 1)
    ]
    return {
        "template_name": f"{cols}x{rows}格",
        "layout_type": "grid",
        "layout_definition": {"rows": rows, "cols": cols},
        "cells": cells,
    }


def test_vote_majority_prefer_smaller_breaks_tie() -> None:
    counter = Counter({7: 1, 8: 1})
    assert ai_endpoint._vote_majority_prefer_smaller(counter) == 7


def test_pick_grid_keeps_initial_over_single_overcount_audit() -> None:
    initial = _grid_candidate(7, 4)
    audited = _grid_candidate(8, 4)

    chosen = ai_endpoint._pick_grid_audit_candidate(
        [audited],
        rotated_dimensions=(8, 4),
        initial_result=initial,
    )

    assert chosen is not None
    assert chosen["layout_definition"] == {"rows": 7, "cols": 4}
    assert len(chosen["cells"]) == 28


def test_pick_grid_prefers_audit_when_majority_agrees() -> None:
    initial = _grid_candidate(12, 3)
    audit_a = _grid_candidate(13, 3)
    audit_b = _grid_candidate(13, 3)

    chosen = ai_endpoint._pick_grid_audit_candidate(
        [audit_a, audit_b],
        rotated_dimensions=(13, 3),
        initial_result=initial,
    )

    assert chosen is not None
    assert chosen["layout_definition"] == {"rows": 13, "cols": 3}
    assert len(chosen["cells"]) == 39


def test_pick_grid_ignores_rotated_overcount_without_majority() -> None:
    initial = _grid_candidate(7, 4)
    audited = _grid_candidate(7, 4)

    chosen = ai_endpoint._pick_grid_audit_candidate(
        [audited],
        rotated_dimensions=(8, 4),
        initial_result=initial,
    )

    assert chosen is not None
    assert chosen["layout_definition"] == {"rows": 7, "cols": 4}


def test_pick_grid_keeps_initial_cols_over_single_overcount() -> None:
    initial = _grid_candidate(13, 3)
    audited = _grid_candidate(13, 4)

    chosen = ai_endpoint._pick_grid_audit_candidate(
        [audited],
        initial_result=initial,
    )

    assert chosen is not None
    assert chosen["layout_definition"] == {"rows": 13, "cols": 3}
    assert len(chosen["cells"]) == 39

