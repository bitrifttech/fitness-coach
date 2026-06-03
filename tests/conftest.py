import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Tests are deterministic and must not require a real key or emit LangSmith traces.
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-used")
os.environ.setdefault("CONFIDENCE_THRESHOLD", "0.6")
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ.pop("LANGSMITH_API_KEY", None)
