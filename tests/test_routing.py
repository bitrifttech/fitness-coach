"""Critical path #1: routing + low-confidence fallback.

Why this path: the router is the single highest-leverage, most failure-prone
component — every request flows through it, and a silent misroute sends the user
to the wrong agent. We verify (a) the confidence gate diverts low-confidence
turns to `clarify` instead of guessing, and (b) the router node emits a
well-formed RoutingDecision and trace from structured output (LLM mocked for
determinism).
"""

from unittest.mock import MagicMock, patch

from fitness_coach.router import (
    RoutingDecision,
    adjust_request_needs_clarify,
    log_route_is_adjust_request,
    route_gate,
    router_node,
)


def test_high_confidence_routes_to_chosen_route():
    state = {"route": "WORKOUT_GENERATE", "confidence": 0.92}
    assert route_gate(state) == "WORKOUT_GENERATE"


def test_low_confidence_diverts_to_clarify():
    # "I did a workout yesterday, can you adjust it?" — genuinely ambiguous.
    state = {"route": "WORKOUT_LOG", "confidence": 0.35}
    assert route_gate(state) == "clarify"


def test_threshold_boundary_is_inclusive_above():
    # Exactly at the 0.6 threshold should NOT clarify (>= passes).
    assert route_gate({"route": "COACH", "confidence": 0.6}) == "COACH"
    assert route_gate({"route": "COACH", "confidence": 0.59}) == "clarify"


def test_adjust_request_is_not_workout_log():
    text = "I did a workout yesterday, can you adjust it?"
    state = {
        "route": "WORKOUT_LOG",
        "confidence": 0.92,
        "messages": [("user", text)],
    }
    assert log_route_is_adjust_request(state)
    assert route_gate(state) == "clarify"


def test_concrete_log_is_not_adjust_misroute():
    text = "I just did 3x10 bench press at 185 lbs"
    state = {"route": "WORKOUT_LOG", "confidence": 0.92, "messages": [("user", text)]}
    assert not log_route_is_adjust_request(state)
    assert route_gate(state) == "WORKOUT_LOG"


def test_adjust_without_spec_clarifies_even_at_high_confidence():
    text = "I did a workout yesterday, can you adjust it?"
    state = {
        "route": "WORKOUT_GENERATE",
        "confidence": 0.92,
        "messages": [("user", text)],
    }
    assert adjust_request_needs_clarify(state)
    assert route_gate(state) == "clarify"


def test_adjust_with_spec_does_not_force_clarify():
    text = "Adjust my 30 min upper body dumbbell session — make it easier"
    state = {
        "route": "WORKOUT_GENERATE",
        "confidence": 0.92,
        "messages": [("user", text)],
    }
    assert not adjust_request_needs_clarify(state)
    assert route_gate(state) == "WORKOUT_GENERATE"


def test_router_corrects_high_confidence_adjust_without_spec():
    decision = RoutingDecision(
        route="WORKOUT_GENERATE",
        confidence=0.91,
        rationale="wants to adjust workout",
        clarify_options=[],
    )
    fake_model = MagicMock()
    fake_model.with_structured_output.return_value.invoke.return_value = decision

    with patch("fitness_coach.router.get_chat_model", return_value=fake_model):
        out = router_node(
            {"messages": [("user", "I did a workout yesterday, can you adjust it?")]}
        )

    assert out["route"] == "WORKOUT_GENERATE"
    assert out["confidence"] <= 0.45


def test_router_corrects_log_misroute_on_adjust():
    decision = RoutingDecision(
        route="WORKOUT_LOG",
        confidence=0.88,
        rationale="mentioned past workout",
        clarify_options=[],
    )
    fake_model = MagicMock()
    fake_model.with_structured_output.return_value.invoke.return_value = decision

    with patch("fitness_coach.router.get_chat_model", return_value=fake_model):
        out = router_node(
            {"messages": [("user", "I did a workout yesterday, can you adjust it?")]}
        )

    assert out["route"] == "WORKOUT_GENERATE"
    assert out["confidence"] <= 0.45
    assert "WORKOUT_LOG" not in out["clarify_options"]


def test_router_node_emits_decision_and_trace():
    decision = RoutingDecision(
        route="COACH", confidence=0.88, rationale="education question", clarify_options=[]
    )
    fake_model = MagicMock()
    fake_model.with_structured_output.return_value.invoke.return_value = decision

    with patch("fitness_coach.router.get_chat_model", return_value=fake_model):
        out = router_node({"messages": [("user", "what muscles does a deadlift work?")]})

    assert out["route"] == "COACH"
    assert out["confidence"] == 0.88
    assert out["trace"] and out["trace"][0]["kind"] == "route"
