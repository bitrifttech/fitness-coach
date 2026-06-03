"""Generator must not deliver workouts that ignore failed equipment constraints."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fitness_coach.agents.generator import (  # noqa: E402
    _strip_workout_on_equipment_violation,
    _strip_workout_on_focus_violation,
    _workout_meets_focus,
)


def test_strip_workout_when_agent_ignored_rowing_machine():
    workout = {
        "title": "Upper Body — Dumbbells",
        "sections": [
            {
                "name": "main",
                "items": [{"equipment": ["Dumbbell", "Flat Bench"], "exercise_id": "x"}],
            }
        ],
    }
    trace = [
        {
            "kind": "tool_call",
            "detail": {
                "count": 0,
                "args": {"equipment": ["rowing machine"], "muscle_groups": ["lats"]},
            },
        }
    ]
    stripped, label = _strip_workout_on_equipment_violation(
        workout,
        trace,
        "Build me a back workout using a rowing machine",
    )
    assert stripped is None
    assert label == "rowing machine"


def test_strip_rowing_from_user_message_without_equipment_in_trace():
    workout = {
        "title": "Upper Body — Dumbbells",
        "sections": [{"name": "main", "items": [{"equipment": ["Dumbbell"], "exercise_id": "x"}]}],
    }
    stripped, label = _strip_workout_on_equipment_violation(
        workout, [], "Build me a back workout using a rowing machine"
    )
    assert stripped is None
    assert "rowing" in label


def test_keep_workout_when_equipment_matches():
    workout = {
        "title": "Back — Row Machine",
        "sections": [
            {
                "name": "main",
                "items": [
                    {"equipment": ["Chest Supported Row Machine"], "exercise_id": "x"}
                ],
            }
        ],
    }
    trace = [
        {
            "kind": "tool_call",
            "detail": {
                "count": 2,
                "args": {"equipment": ["Chest Supported Row Machine"], "muscle_groups": ["lats"]},
            },
        }
    ]
    kept, label = _strip_workout_on_equipment_violation(workout, trace)
    assert kept is workout
    assert label is None


def test_back_workout_must_be_mostly_back_muscles():
    from fitness_coach import exercises

    back_ex = next(
        e
        for e in exercises.all_exercises()
        if "lats" in (e.get("muscle_groups") or [])
    )
    arm_ex = next(
        e
        for e in exercises.all_exercises()
        if "biceps" in (e.get("muscle_groups") or [])
        and "lats" not in (e.get("muscle_groups") or [])
    )
    mixed = {
        "sections": [
            {
                "name": "main",
                "items": [
                    {"exercise_id": back_ex["id"]},
                    {"exercise_id": arm_ex["id"]},
                    {"exercise_id": arm_ex["id"]},
                    {"exercise_id": arm_ex["id"]},
                ],
            }
        ]
    }
    assert not _workout_meets_focus(mixed, {"lats", "upper back", "lower back", "traps"})
    stripped, label = _strip_workout_on_focus_violation(
        mixed, "Build me a back workout using a rowing machine"
    )
    assert stripped is None
    assert label == "back"
