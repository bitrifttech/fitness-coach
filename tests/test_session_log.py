"""Session log history accumulation across turns."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-used")

from fitness_coach.agents.logger import _match  # noqa: E402


def test_match_appends_log_history():
    state = {
        "log_entries": [{"raw_name": "bench press", "sets": 3, "reps": 10, "weight": 185.0, "weight_unit": "lb"}],
        "trace": [],
    }
    with patch("fitness_coach.agents.logger.exercises.fuzzy_match") as mock:
        mock.return_value = ({"id": "x", "name": "Bench"}, 90.0)
        out = _match(state)
    assert "log_history" in out
    assert len(out["log_history"]) == 1
    assert out["log_history"][0]["matched_name"] == "Bench"
