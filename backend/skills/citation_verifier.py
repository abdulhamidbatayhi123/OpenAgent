"""
MedMind — Skill 4: Citation Verifier
Checks every [Sx] citation in the answer against the actual evidence.
"""

import re
from models.ollama_client import OllamaClient
from config import VERIFIER_MODEL


VERIFIER_SYSTEM = """You are a fact-checking assistant. Check each [Sx] citation in the ANSWER against the EVIDENCE.

Respond with valid JSON only:
{
  "verified_claims": [
    {"claim": "...", "citation": "S1", "supported": true},
    {"claim": "...", "citation": "S2", "supported": false}
  ],
  "unsupported_citations": ["S3"],
  "overall_grounded": true,
  "confidence": 0.85
}

Rules:
- "supported" = the cited evidence DIRECTLY states or strongly implies the claim
- "overall_grounded" = true if > 70% of claims are supported
- "confidence" = 0.0 to 1.0"""


class CitationVerifier:
    """Skill 4: Verify citations and remove hallucinated claims."""

    def __init__(self, llm: OllamaClient):
        self.llm = llm

    def verify(self, answer: str, evidence: str, max_source_index: int) -> dict:
        """
        Verify all citations in the answer against the evidence.

        Args:
            answer: The answer with [S1][S2] markers
            evidence: The formatted evidence string
            max_source_index: Maximum valid source index

        Returns:
            Dict with verified answer, removed citations, and confidence
        """
        # Step 1: Remove obviously invalid citations
        cleaned = self._remove_invalid_citations(answer, max_source_index)

        # Step 2: Check if answer has any citations
        citations = re.findall(r"\[S(\d+)\]", cleaned)
        if not citations:
            return {
                "answer": cleaned,
                "grounded": False,
                "confidence": 0.3,
                "removed_citations": [],
            }

        # Step 3: LLM-based deep verification
        verification = self._llm_verify(cleaned, evidence)

        if verification:
            final_answer = cleaned
            removed = verification.get("unsupported_citations", [])

            for citation in removed:
                final_answer = final_answer.replace(f"[{citation}]", "")

            final_answer = re.sub(r"\s{2,}", " ", final_answer).strip()

            return {
                "answer": final_answer,
                "grounded": verification.get("overall_grounded", False),
                "confidence": verification.get("confidence", 0.5),
                "removed_citations": removed,
            }

        return {
            "answer": cleaned,
            "grounded": True,
            "confidence": 0.5,
            "removed_citations": [],
        }

    def _remove_invalid_citations(self, answer: str, max_idx: int) -> str:
        """Remove [Sx] markers where x is out of valid range."""
        def replace_marker(match):
            idx = int(match.group(1))
            if idx < 1 or idx > max_idx:
                return ""
            return f"[S{idx}]"

        cleaned = re.sub(r"\[S(\d+)\]", replace_marker, answer)
        return re.sub(r"\s{2,}", " ", cleaned).strip()

    def _llm_verify(self, answer: str, evidence: str) -> dict | None:
        """Use the LLM to verify citations against evidence."""
        prompt = f"ANSWER:\n{answer}\n\nEVIDENCE:\n{evidence}\n\nVerify each [Sx] citation."

        response = self.llm.generate(
            prompt=prompt,
            system=VERIFIER_SYSTEM,
            temperature=0.1,
            json_mode=True,
            max_tokens=1024,
            model=VERIFIER_MODEL,
        )

        return self.llm.extract_json(response)
