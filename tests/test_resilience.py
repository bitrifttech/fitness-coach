"""Critical path #2: resilience (graceful failure, no hallucination).

Why this path: the assessment explicitly calls out two failure modes — empty
search results and invalid tool calls. These are where a naive agent crashes or
fabricates data. We assert the tool layer returns structured, recoverable
signals instead, and that fuzzy matching maps colloquial names to canonical
exercises (the logger's core behavior).
"""

from fitness_coach import exercises
from fitness_coach.tools import build_workout, search_exercises


def test_search_with_absent_equipment_returns_empty_not_crash():
    out = search_exercises.invoke(
        {"equipment": ["barbell snatch machine on mars"], "muscle_groups": ["quads"]}
    )
    assert out["count"] == 0
    assert out["results"] == []  # recoverable signal, not an exception
    assert out["unmatched_equipment"] == ["barbell snatch machine on mars"]


def test_rowing_machine_not_in_library():
    out = search_exercises.invoke(
        {"equipment": ["rowing machine"], "muscle_groups": ["lats", "upper back"]}
    )
    assert out["count"] == 0
    assert "rowing machine" in out["unmatched_equipment"]


def test_check_equipment_terms_accepts_dumbbell_plural():
    from fitness_coach.exercises import check_equipment_terms

    out = check_equipment_terms(["dumbbells"])
    assert not out["unmatched"]
    assert out["matched_vocab"]


def test_search_finds_dumbbell_chest_despite_plural_phrasing():
    out = search_exercises.invoke({"muscle_groups": ["chest"], "equipment": ["dumbbells"]})
    assert out["count"] > 0
    assert all("chest" in e["muscle_groups"] for e in out["results"])


def test_build_workout_rejects_invalid_exercise_id():
    out = build_workout.invoke(
        {
            "title": "Bad",
            "duration_minutes": 20,
            "main": [{"exercise_id": "does-not-exist", "sets": 3, "reps": 10, "rest_seconds": 60}],
        }
    )
    assert out.get("error") == "invalid_exercise_id"
    assert "does-not-exist" in out["invalid_ids"]


def test_build_workout_succeeds_with_valid_id():
    valid_id = exercises.all_exercises()[0]["id"]
    out = build_workout.invoke(
        {
            "title": "Good",
            "duration_minutes": 20,
            "main": [{"exercise_id": valid_id, "sets": 3, "reps": 10, "rest_seconds": 60}],
        }
    )
    assert "error" not in out
    assert out["sections"][0]["items"][0]["exercise_id"] == valid_id


def test_fuzzy_match_maps_colloquial_to_canonical():
    result = exercises.fuzzy_match("bench press")
    assert result is not None
    matched, score = result
    assert "Bench Press" in matched["name"]
    assert score >= 60


def test_fuzzy_match_gibberish_returns_none():
    assert exercises.fuzzy_match("zxqwerty nonsense") is None
