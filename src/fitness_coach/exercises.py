"""Exercise dataset loader and in-memory index.

Loads ``data/exercises.json`` once and offers filtered search plus fuzzy
name-matching. Equipment/muscle/pattern matching is case-insensitive and
substring-tolerant because user phrasing ("dumbbells") rarely matches the
canonical vocabulary ("Dumbbell") exactly.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from rapidfuzz import fuzz, process

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "exercises.json"


@lru_cache(maxsize=1)
def _load() -> list[dict[str, Any]]:
    with _DATA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def all_exercises() -> list[dict[str, Any]]:
    return list(_load())


@lru_cache(maxsize=1)
def _by_id() -> dict[str, dict[str, Any]]:
    return {e["id"]: e for e in _load()}


def get_by_id(exercise_id: str) -> Optional[dict[str, Any]]:
    return _by_id().get(exercise_id)


def _matches_any(needles: list[str], haystack: list[str]) -> bool:
    """True if ANY requested needle matches some value in haystack (substring, ci).

    Within a single facet (e.g. several muscle groups) we OR the needles: an
    exercise targeting *any* requested muscle is relevant. Different facets are
    still ANDed together by the caller.
    """
    hay_lower = [h.lower() for h in haystack]
    for needle in needles:
        n = needle.lower().strip().rstrip("s")  # tolerate simple plurals: dumbbells -> dumbbell
        if n and any(n in h for h in hay_lower):
            return True
    return False


def _joints_conflict(exercise: dict[str, Any], avoid_joints: list[str]) -> bool:
    """True when the exercise loads any joint the caller wants to avoid."""
    if not avoid_joints:
        return False
    avoid = {j.lower().strip() for j in avoid_joints}
    loaded = {j.lower().strip() for j in (exercise.get("joints_loaded") or [])}
    return bool(avoid & loaded)


def check_equipment_terms(terms: Optional[list[str]]) -> dict[str, list[str]]:
    """Split requested equipment into library matches vs unknown terms."""
    if not terms:
        return {"unmatched": [], "matched_vocab": []}
    vocab = vocabulary()["equipment"]
    unmatched: list[str] = []
    matched_vocab: list[str] = []
    for term in terms:
        if _matches_any([term], vocab):
            for item in vocab:
                n = term.lower().strip().rstrip("s")
                if n and n in item.lower() and item not in matched_vocab:
                    matched_vocab.append(item)
        else:
            unmatched.append(term)
    return {"unmatched": unmatched, "matched_vocab": matched_vocab}


def search_exercises(
    muscle_groups: Optional[list[str]] = None,
    equipment: Optional[list[str]] = None,
    movement_patterns: Optional[list[str]] = None,
    avoid_joints: Optional[list[str]] = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Filter the dataset by any combination of facets.

    All provided facets must match (logical AND). Empty/None facets are ignored.
    When ``avoid_joints`` is set, exercises whose ``joints_loaded`` intersects
    that list are excluded (injury avoidance).
    Returns up to ``limit`` exercises, lower ``priority_tier`` first.
    """
    results: list[dict[str, Any]] = []
    for ex in _load():
        if muscle_groups and not _matches_any(muscle_groups, ex.get("muscle_groups", [])):
            continue
        if equipment and not _matches_any(equipment, ex.get("equipment_required", [])):
            continue
        if movement_patterns and not _matches_any(
            movement_patterns, ex.get("movement_patterns", [])
        ):
            continue
        if avoid_joints and _joints_conflict(ex, avoid_joints):
            continue
        results.append(ex)
    results.sort(key=lambda e: e.get("priority_tier", 99))
    return results[:limit]


def joints_for_exercise_ids(exercise_ids: list[str]) -> set[str]:
    """Union of ``joints_loaded`` across the given exercise ids."""
    joints: set[str] = set()
    for eid in exercise_ids:
        ex = get_by_id(eid)
        if ex:
            joints.update(ex.get("joints_loaded") or [])
    return joints


_SIDE_OPPOSITE = {
    "left_arm": "right_arm",
    "right_arm": "left_arm",
    "left_side": "right_side",
    "right_side": "left_side",
    "left_leg": "right_leg",
    "right_leg": "left_leg",
}


def opposite_side(side: Optional[str]) -> Optional[str]:
    if not side:
        return None
    return _SIDE_OPPOSITE.get(side.lower(), f"other_{side}")


def is_unilateral(exercise: dict[str, Any]) -> bool:
    """True when the exercise targets one side and should be mirrored."""
    if exercise.get("bilateral_pair_id") and exercise.get("side"):
        return True
    return exercise.get("is_bilateral") is False and bool(exercise.get("side"))


def expand_bilateral(item: dict[str, Any], exercise: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one or two workout rows; unilateral exercises get a mirror row for the other side."""
    if not is_unilateral(exercise):
        return [item]
    side = exercise.get("side")
    primary = {**item, "side_label": side, "paired": False}
    mirror = {
        **item,
        "side_label": opposite_side(side),
        "paired": True,
    }
    return [primary, mirror]


@lru_cache(maxsize=1)
def vocabulary() -> dict[str, list[str]]:
    """Distinct facet values present in the dataset, for grounding the LLM."""
    muscles, equip, patterns = set(), set(), set()
    for e in _load():
        muscles.update(e.get("muscle_groups") or [])
        equip.update(e.get("equipment_required") or [])
        patterns.update(e.get("movement_patterns") or [])
    return {
        "muscle_groups": sorted(muscles),
        "equipment": sorted(equip),
        "movement_patterns": sorted(patterns),
    }


def fuzzy_match(name: str, score_cutoff: float = 60.0) -> Optional[tuple[dict[str, Any], float]]:
    """Map a free-text exercise name to the closest canonical exercise.

    Returns ``(exercise, score)`` or ``None`` when nothing clears ``score_cutoff``.
    """
    names = {e["name"]: e for e in _load()}
    match = process.extractOne(
        name, list(names.keys()), scorer=fuzz.WRatio, score_cutoff=score_cutoff
    )
    if match is None:
        return None
    matched_name, score, _ = match
    return names[matched_name], float(score)
