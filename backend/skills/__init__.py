"""MedMind Skills Package - lazy imports."""
import importlib

__all__ = [
    "SymptomAnalyzer",
    "MedicalRetriever",
    "ClinicalReasoner",
    "CitationVerifier",
    "SafetyFormatter",
]

_LAZY = {
    "SymptomAnalyzer": "skills.symptom_analyzer",
    "MedicalRetriever": "skills.medical_retriever",
    "ClinicalReasoner": "skills.clinical_reasoner",
    "CitationVerifier": "skills.citation_verifier",
    "SafetyFormatter": "skills.safety_formatter",
}


def __getattr__(name):
    if name in _LAZY:
        return getattr(importlib.import_module(_LAZY[name]), name)
    raise AttributeError(name)
