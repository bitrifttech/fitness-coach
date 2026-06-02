"""LangChain tools with Pydantic input schemas (requirement #3).

These are bound to the generator's tool-calling agent. Each tool validates its
input via a Pydantic model with field descriptions, and each returns a plain
dict/JSON-serialisable payload so the agent (and the UI trace) can reason about
the result — including the *empty* result, which is a first-class outcome.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from . import exercises


class SearchExercisesInput(BaseModel):
    muscle_groups: Optional[list[str]] = Field(
        None, description="Target muscles, e.g. ['chest', 'triceps', 'quads', 'glutes']."
    )
    equipment: Optional[list[str]] = Field(
        None,
        description="Available equipment, e.g. ['Dumbbell', 'Barbell', 'Yoga Mat']. "
        "Matching is case-insensitive and tolerant of plurals.",
    )
    movement_patterns: Optional[list[str]] = Field(
        None,
        description="Movement patterns, e.g. ['upper push - horizontal', 'lower push - squat'].",
    )
    limit: int = Field(25, ge=1, le=50, description="Maximum number of exercises to return.")


class BuildWorkoutItemInput(BaseModel):
    exercise_id: str = Field(description="Canonical exercise id returned by search_exercises.")
    sets: int = Field(ge=1, le=10, description="Number of sets.")
    reps: Optional[int] = Field(None, ge=1, le=50, description="Reps per set (rep-based moves).")
    duration_seconds: Optional[int] = Field(
        None, ge=5, le=600, description="Work duration per set (time-based moves)."
    )
    rest_seconds: int = Field(60, ge=0, le=600, description="Rest between sets, in seconds.")


class BuildWorkoutInput(BaseModel):
    title: str = Field(description="Short title for the session, e.g. 'Upper Body — Dumbbells'.")
    duration_minutes: int = Field(ge=5, le=180, description="Target total session length.")
    warmup: list[BuildWorkoutItemInput] = Field(
        default_factory=list, description="Warmup items (mobility/activation)."
    )
    main: list[BuildWorkoutItemInput] = Field(
        description="Main working sets — the core of the session."
    )
    cooldown: list[BuildWorkoutItemInput] = Field(
        default_factory=list, description="Cooldown items (stretch/regen)."
    )
    notes: Optional[str] = Field(None, description="Optional coaching notes.")


@tool(args_schema=SearchExercisesInput)
def search_exercises(
    muscle_groups: Optional[list[str]] = None,
    equipment: Optional[list[str]] = None,
    movement_patterns: Optional[list[str]] = None,
    limit: int = 25,
) -> dict:
    """Search the exercise library by muscle groups, equipment, and/or movement patterns.

    Returns a dict with ``count`` and ``results``. When ``count`` is 0 the
    request matched nothing in the dataset — do NOT invent exercises; either
    relax the filters or tell the user what is unavailable.
    """
    results = exercises.search_exercises(
        muscle_groups=muscle_groups,
        equipment=equipment,
        movement_patterns=movement_patterns,
        limit=limit,
    )
    return {
        "count": len(results),
        "results": [
            {
                "id": e["id"],
                "name": e["name"],
                "muscle_groups": e.get("muscle_groups", []),
                "equipment_required": e.get("equipment_required", []),
                "movement_patterns": e.get("movement_patterns", []),
                "is_bilateral": e.get("is_bilateral", False),
                "bilateral_pair_id": e.get("bilateral_pair_id"),
                "supports_weight": e.get("supports_weight", False),
            }
            for e in results
        ],
    }


@tool(args_schema=BuildWorkoutInput)
def build_workout(
    title: str,
    duration_minutes: int,
    main: list,
    warmup: Optional[list] = None,
    cooldown: Optional[list] = None,
    notes: Optional[str] = None,
) -> dict:
    """Assemble a structured workout (warmup / main / cooldown) from selected exercises.

    Every ``exercise_id`` must come from search_exercises results. Unknown ids
    are rejected with an error so the caller can correct the tool call instead of
    fabricating a workout.
    """

    def _resolve(items: list) -> tuple[list[dict], list[str]]:
        built: list[dict] = []
        bad: list[str] = []
        for raw in items or []:
            item = raw if isinstance(raw, dict) else raw.model_dump()
            ex = exercises.get_by_id(item["exercise_id"])
            if ex is None:
                bad.append(item["exercise_id"])
                continue
            built.append(
                {
                    "exercise_id": ex["id"],
                    "name": ex["name"],
                    "sets": item["sets"],
                    "reps": item.get("reps"),
                    "duration_seconds": item.get("duration_seconds"),
                    "rest_seconds": item.get("rest_seconds", 60),
                    "equipment": ex.get("equipment_required", []),
                }
            )
        return built, bad

    sections = []
    invalid: list[str] = []
    for name, items in (("warmup", warmup), ("main", main), ("cooldown", cooldown)):
        built, bad = _resolve(items)
        invalid.extend(bad)
        if built:
            sections.append({"name": name, "items": built})

    if invalid:
        return {
            "error": "invalid_exercise_id",
            "message": f"Unknown exercise id(s): {invalid}. Use ids from search_exercises.",
            "invalid_ids": invalid,
        }

    return {
        "title": title,
        "duration_minutes": duration_minutes,
        "sections": sections,
        "notes": notes,
    }


GENERATOR_TOOLS = [search_exercises, build_workout]
