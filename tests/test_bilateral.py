"""Bilateral exercise pairing in build_workout."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-used")

from fitness_coach import exercises  # noqa: E402
from fitness_coach.tools import build_workout  # noqa: E402


def _unilateral_id() -> str:
    for e in exercises.all_exercises():
        if exercises.is_unilateral(e):
            return e["id"]
    raise AssertionError("no unilateral exercise in dataset")


def _bilateral_id() -> str:
    for e in exercises.all_exercises():
        if not exercises.is_unilateral(e):
            return e["id"]
    raise AssertionError("no bilateral exercise in dataset")


def test_unilateral_expands_to_two_rows_with_side_labels():
    uid = _unilateral_id()
    out = build_workout.invoke(
        {
            "title": "Uni",
            "duration_minutes": 20,
            "main": [{"exercise_id": uid, "sets": 3, "reps": 10, "rest_seconds": 60}],
        }
    )
    items = out["sections"][0]["items"]
    assert len(items) == 2
    assert items[0].get("paired") is False
    assert items[1].get("paired") is True
    assert items[0]["sets"] == items[1]["sets"]
    assert "left" in items[0]["side_label"].lower()
    assert "right" in items[1]["side_label"].lower()


def test_bilateral_stays_one_row():
    bid = _bilateral_id()
    out = build_workout.invoke(
        {
            "title": "Bi",
            "duration_minutes": 20,
            "main": [{"exercise_id": bid, "sets": 3, "reps": 10, "rest_seconds": 60}],
        }
    )
    assert len(out["sections"][0]["items"]) == 1
    assert "side_label" not in out["sections"][0]["items"][0]
