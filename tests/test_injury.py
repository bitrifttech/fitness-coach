"""Injury avoidance via joints_loaded filtering."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-used")

from fitness_coach import exercises  # noqa: E402
from fitness_coach.tools import build_workout, search_exercises  # noqa: E402


def test_search_excludes_avoided_joints():
    all_chest = search_exercises.invoke({"muscle_groups": ["chest"]})
    filtered = search_exercises.invoke({"muscle_groups": ["chest"], "avoid_joints": ["shoulder"]})
    assert filtered["count"] < all_chest["count"]
    for ex in filtered["results"]:
        assert "shoulder" not in [j.lower() for j in ex.get("joints_loaded", [])]


def test_build_workout_rejects_joint_conflict():
    shoulder_ex = next(
        e for e in exercises.all_exercises() if "shoulder" in (e.get("joints_loaded") or [])
    )
    out = build_workout.invoke(
        {
            "title": "Bad",
            "duration_minutes": 20,
            "avoid_joints": ["shoulder"],
            "main": [
                {
                    "exercise_id": shoulder_ex["id"],
                    "sets": 3,
                    "reps": 10,
                    "rest_seconds": 60,
                }
            ],
        }
    )
    assert out.get("error") == "joint_conflict"


def test_joints_for_exercise_ids():
    ex = exercises.all_exercises()[0]
    joints = exercises.joints_for_exercise_ids([ex["id"]])
    assert joints == set(ex.get("joints_loaded") or [])
