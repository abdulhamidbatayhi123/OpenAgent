"""
MedMind — Skill 5: Safety Formatter
Adds medical disclaimers, structures the response, and ensures safety.
Mostly rule-based — no LLM needed for formatting.

Disclaimers are context-aware: only medical-advice queries get the full
medical disclaimer. Nutrition, fitness, and general-health queries get
lighter notes appropriate to their content.
"""

import re

from config import ENABLE_WEB_SEARCH

# ── Query types that warrant the full medical disclaimer ──────────
_MEDICAL_ADVICE_TYPES = {"symptom", "medication", "emergency"}

# Medical disclaimer templates
DISCLAIMER_EN = (
    "⚠️ *This information is for educational purposes only and does not "
    "constitute medical advice. Always consult a qualified healthcare "
    "professional for personal medical decisions.*"
)

DISCLAIMER_AR = (
    "⚠️ *هذه المعلومات لأغراض تعليمية فقط ولا تشكل نصيحة طبية. "
    "استشر دائماً مختصاً مؤهلاً في الرعاية الصحية للقرارات الطبية الشخصية.*"
)

EMERGENCY_EN = (
    "🚨 **URGENT: Based on the symptoms you described, please seek "
    "immediate medical attention or call emergency services.** Do not "
    "rely on this or any AI system for emergency situations."
)

EMERGENCY_AR = (
    "🚨 **عاجل: بناءً على الأعراض التي وصفتها، يرجى طلب رعاية طبية "
    "فورية أو الاتصال بخدمات الطوارئ.** لا تعتمد على هذا النظام أو أي "
    "نظام ذكاء اصطناعي في حالات الطوارئ."
)


def _build_no_info_message(language: str) -> str:
    """Build the 'no info' message, adapting suggestions based on config."""
    if language == "ar":
        lines = [
            "لا تتوفر لدي معلومات موثوقة كافية في قاعدة المعرفة للإجابة على "
            "هذا السؤال بدقة. أفضل أن أقول لا أعرف بدلاً من إعطائك معلومات "
            "صحية غير صحيحة.\n",
            "**يمكنك تجربة:**",
            "- إعادة صياغة سؤالك",
            "- رفع ملف PDF أو مقال طبي ذي صلة",
        ]
        if not ENABLE_WEB_SEARCH:
            lines.append("- تفعيل البحث عبر الإنترنت في مصادر طبية موثوقة")
        lines.append("- استشارة مقدم الرعاية الصحية مباشرة")
        return "\n".join(lines)

    lines = [
        "I don't have enough reliable information in my knowledge base to "
        "answer this question accurately. I'd rather say I don't know than "
        "give you incorrect health information.\n",
        "**You can try:**",
        "- Rephrasing your question",
        "- Uploading a relevant medical PDF or article",
    ]
    if not ENABLE_WEB_SEARCH:
        lines.append("- Enabling online search for trusted medical sources")
    lines.append("- Consulting your healthcare provider directly")
    return "\n".join(lines)


class SafetyFormatter:
    """Skill 5: Format response with safety disclaimers and structure."""

    def format(
        self,
        answer: str,
        analysis: dict,
        evidence_results: list[dict],
        verification: dict,
        is_grounded: bool,
    ) -> dict:
        """
        Format the final response with safety checks and structure.

        Args:
            answer: The verified answer text
            analysis: Output from SymptomAnalyzer
            evidence_results: Retrieved evidence chunks
            verification: Output from CitationVerifier
            is_grounded: Whether the answer met grounding thresholds

        Returns:
            Complete response dict ready for the API
        """
        language = analysis.get("language", "en")
        urgency = analysis.get("urgency", "low")

        # Case 1: Emergency - show urgent warning
        if urgency == "emergency":
            return self._emergency_response(answer, language, evidence_results, verification)

        # Case 2: Not grounded - refuse to answer
        if not is_grounded:
            return self._no_info_response(language)

        # Case 3: Normal grounded response
        return self._standard_response(
            answer, language, analysis, evidence_results, verification
        )

    def _emergency_response(
        self, answer: str, language: str, results: list[dict], verification: dict
    ) -> dict:
        """Format an emergency response with urgent warnings."""
        warning = EMERGENCY_AR if language == "ar" else EMERGENCY_EN
        disclaimer = DISCLAIMER_AR if language == "ar" else DISCLAIMER_EN

        formatted = f"{warning}\n\n---\n\n{answer}\n\n---\n\n{disclaimer}"

        return {
            "answer": formatted,
            "sources": self._format_sources(results),
            "grounded": verification.get("grounded", False),
            "confidence": verification.get("confidence", 0.0),
            "urgency": "emergency",
            "disclaimer": True,
        }

    def _no_info_response(self, language: str) -> dict:
        """Format a 'I don't know' response."""
        message = _build_no_info_message(language)

        return {
            "answer": message,
            "sources": [],
            "grounded": False,
            "confidence": 0.0,
            "urgency": "none",
            "disclaimer": True,
        }

    def _standard_response(
        self,
        answer: str,
        language: str,
        analysis: dict,
        results: list[dict],
        verification: dict,
    ) -> dict:
        """Format a standard grounded response with context-aware disclaimers."""
        confidence = verification.get("confidence", 0.5)
        query_type = analysis.get("query_type", "general_health")
        urgency = analysis.get("urgency", "low")

        # Build the formatted answer
        parts = [answer]

        # Add urgency note if medium/high
        if urgency == "high":
            note = ("💡 *ملاحظة: يُنصح بمراجعة طبيب لهذه الحالة.*"
                    if language == "ar"
                    else "💡 *Note: It's recommended to consult a doctor about this.*")
            parts.append(note)

        # Context-aware disclaimer: full medical disclaimer only for
        # symptom/medication/emergency queries.  Nutrition and fitness
        # get a lighter note; general_health gets nothing extra.
        needs_medical_disclaimer = query_type in _MEDICAL_ADVICE_TYPES or urgency in ("high", "emergency")

        if needs_medical_disclaimer:
            disclaimer = DISCLAIMER_AR if language == "ar" else DISCLAIMER_EN
            parts.append(f"\n---\n{disclaimer}")

        formatted_answer = "\n\n".join(parts)

        return {
            "answer": formatted_answer,
            "sources": self._format_sources(results),
            "grounded": verification.get("grounded", False),
            "confidence": confidence,
            "urgency": urgency,
            "disclaimer": needs_medical_disclaimer,
        }

    def _format_sources(self, results: list[dict]) -> list[dict]:
        """Format evidence results into clean source objects for the API."""
        sources = []
        for r in results:
            sources.append({
                "label": r.get("source_label", ""),
                "title": r.get("document_title", r.get("source", "Unknown")),
                "source": r.get("source", ""),
                "url": r.get("source_url", ""),
                "section": r.get("section", ""),
                "snippet": r.get("content", "")[:200],
                "score": r.get("rerank_score", r.get("score", 0.0)),
            })
        return sources
