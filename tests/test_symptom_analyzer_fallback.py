"""
Unit tests for the SymptomAnalyzer's deterministic paths:
  - the heuristic fallback when the LLM returns garbage
  - validation of LLM output (clamping out-of-range fields)
"""
from skills.symptom_analyzer import SymptomAnalyzer


class StubLLM:
    """Returns a fixed response and lets extract_json simulate LLM behavior."""

    def __init__(self, parsed=None, raw=""):
        self._parsed = parsed
        self._raw = raw

    def generate(self, **_):
        return self._raw

    def extract_json(self, _):
        return self._parsed


def test_fallback_detects_emergency_keywords():
    a = SymptomAnalyzer(StubLLM(parsed=None))
    out = a.analyze("I have severe chest pain right now")
    assert out["urgency"] == "emergency"
    assert out["query_type"] in {"symptom", "general_health"}


def test_fallback_classifies_nutrition_query():
    a = SymptomAnalyzer(StubLLM(parsed=None))
    out = a.analyze("how many calories are in a banana")
    assert out["query_type"] == "nutrition"
    assert out["urgency"] == "low"


def test_fallback_classifies_fitness_query():
    a = SymptomAnalyzer(StubLLM(parsed=None))
    out = a.analyze("good workout for my back")
    assert out["query_type"] == "fitness"


def test_fallback_detects_arabic_language():
    a = SymptomAnalyzer(StubLLM(parsed=None))
    out = a.analyze("ما هي أعراض السكري؟")
    assert out["language"] == "ar"


def test_validate_clamps_invalid_query_type_to_general():
    a = SymptomAnalyzer(StubLLM(parsed={
        "query_type": "totally_made_up",
        "urgency": "low",
    }))
    out = a.analyze("anything")
    assert out["query_type"] == "general_health"


def test_validate_clamps_invalid_urgency_to_low():
    a = SymptomAnalyzer(StubLLM(parsed={
        "query_type": "symptom",
        "urgency": "ULTRAEMERGENCY",
    }))
    out = a.analyze("anything")
    assert out["urgency"] == "low"


def test_validate_falls_back_subqueries_to_original():
    a = SymptomAnalyzer(StubLLM(parsed={
        "query_type": "symptom",
        "urgency": "low",
        # No sub_queries key.
    }))
    out = a.analyze("my eye hurts")
    assert out["sub_queries"] == ["my eye hurts"]
    assert out["original_query"] == "my eye hurts"
