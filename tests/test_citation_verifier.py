"""Unit tests for the citation verifier's deterministic logic."""
from skills.citation_verifier import CitationVerifier


class DummyLLM:
    """Stand-in for OllamaClient — every test patches `last_response`."""

    def __init__(self, response_json: dict | None = None):
        self.response_json = response_json
        self.last_prompt = None

    def generate(self, prompt, system="", temperature=0.1, json_mode=True,
                 max_tokens=1024, model=None):
        self.last_prompt = prompt
        if self.response_json is None:
            return ""
        import json
        return json.dumps(self.response_json)

    def extract_json(self, text):
        if not text:
            return None
        import json
        try:
            return json.loads(text)
        except Exception:
            return None


def test_invalid_citation_indices_are_stripped():
    v = CitationVerifier(DummyLLM(response_json=None))
    answer = "Headaches can have many causes [S1] including stress [S99]."
    cleaned = v._remove_invalid_citations(answer, max_idx=3)
    assert "[S1]" in cleaned
    assert "[S99]" not in cleaned
    # The invalid marker should be gone, not replaced with an empty bracket.
    assert "[S]" not in cleaned


def test_zero_index_citation_is_stripped():
    v = CitationVerifier(DummyLLM(response_json=None))
    cleaned = v._remove_invalid_citations("foo [S0] bar", max_idx=2)
    assert "[S0]" not in cleaned


def test_no_citations_means_not_grounded():
    v = CitationVerifier(DummyLLM(response_json=None))
    out = v.verify(answer="Just plain text, no markers.", evidence="...", max_source_index=2)
    assert out["grounded"] is False
    assert out["confidence"] < 0.5
    assert out["removed_citations"] == []


def test_unsupported_citations_are_removed_from_answer():
    v = CitationVerifier(DummyLLM(response_json={
        "verified_claims": [
            {"claim": "X", "citation": "S1", "supported": True},
            {"claim": "Y", "citation": "S2", "supported": False},
        ],
        "unsupported_citations": ["S2"],
        "overall_grounded": True,
        "confidence": 0.8,
    }))
    out = v.verify(
        answer="Claim A [S1] and claim B [S2].",
        evidence="--- [S1] ... --- [S2] ...",
        max_source_index=2,
    )
    assert "[S1]" in out["answer"]
    assert "[S2]" not in out["answer"]
    assert out["removed_citations"] == ["S2"]
    assert out["grounded"] is True


def test_verifier_handles_llm_failure_gracefully():
    # generate() returns empty string -> extract_json returns None -> fallback.
    v = CitationVerifier(DummyLLM(response_json=None))
    out = v.verify(
        answer="Claim with citation [S1].",
        evidence="--- [S1] something",
        max_source_index=2,
    )
    # Should not crash and should preserve the in-range citation.
    assert "[S1]" in out["answer"]
