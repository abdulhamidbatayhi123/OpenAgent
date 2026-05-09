"""
MedMind — Skill 3: Clinical Reasoner
Chain-of-thought medical reasoning over retrieved evidence.

Forces the LLM to reason step-by-step, which dramatically improves
answer quality even with smaller models (4B-8B).
"""

from models.ollama_client import OllamaClient
from config import REASONER_MODEL

REASONER_SYSTEM_EN = """You are a medical knowledge assistant. Your job is to answer health questions using ONLY the evidence provided below.

CRITICAL RULES:
1. Base your answer ONLY on the provided evidence. Never make up medical information.
2. For every factual claim, include a citation like [S1], [S2] referring to the evidence sources.
3. If the evidence does not contain enough information, clearly state: "I don't have enough information in my knowledge base to answer this reliably."
4. Never diagnose. Use phrases like "this could indicate", "common causes include", "evidence suggests".
5. Always recommend consulting a healthcare professional for personal medical decisions.

REASONING STEPS (follow this structure):
Step 1: Identify what the user is asking
Step 2: Review each piece of evidence and note what's relevant
Step 3: Formulate your answer using ONLY supported claims
Step 4: Add citations [S1][S2] to each claim
Step 5: Note any gaps — what the evidence does NOT cover

OUTPUT FORMAT:
Write a clear, helpful answer in natural language. Include [S1], [S2] citations inline.
Do NOT output your reasoning steps — only the final answer."""

REASONER_SYSTEM_AR = """أنت مساعد معرفة طبية. مهمتك الإجابة على الأسئلة الصحية باستخدام الأدلة المقدمة فقط.

قواعد حاسمة:
1. استند فقط إلى الأدلة المقدمة. لا تخترع معلومات طبية أبداً.
2. لكل ادعاء، أضف استشهاداً مثل [S1]، [S2] يشير إلى مصدر الدليل.
3. إذا لم تحتوِ الأدلة على معلومات كافية، قل بوضوح: "لا تتوفر لدي معلومات كافية في قاعدة المعرفة للإجابة على هذا بشكل موثوق."
4. لا تشخّص أبداً. استخدم عبارات مثل "قد يشير هذا إلى"، "الأسباب الشائعة تشمل".
5. أوصِ دائماً باستشارة مختص رعاية صحية.

اكتب إجابة واضحة ومفيدة بلغة طبيعية مع استشهادات [S1] [S2] داخل النص."""


class ClinicalReasoner:
    """Skill 3: Chain-of-thought medical reasoning with citations."""

    def __init__(self, llm: OllamaClient):
        self.llm = llm

    def reason(
        self,
        analysis: dict,
        evidence: str,
        health_profile: dict = None,
        conversation_history: list[dict] = None,
    ) -> str:
        """
        Generate a reasoned, cited answer to a health question.

        Args:
            analysis: Output from SymptomAnalyzer
            evidence: Formatted evidence string from MedicalRetriever
            health_profile: Optional user health profile
            conversation_history: Optional conversation context

        Returns:
            The reasoned answer with [S1][S2] citations
        """
        language = analysis.get("language", "en")
        system_prompt = REASONER_SYSTEM_AR if language == "ar" else REASONER_SYSTEM_EN

        # Build the prompt
        prompt_parts = []

        # Add evidence
        prompt_parts.append(f"EVIDENCE:\n{evidence}")

        # Add health profile context if available
        if health_profile:
            profile_str = self._format_profile(health_profile)
            prompt_parts.append(f"\nUSER HEALTH PROFILE:\n{profile_str}")

        # Add the question
        query = analysis.get("original_query", analysis.get("summary", ""))
        prompt_parts.append(f"\nUSER QUESTION: {query}")

        # Add analysis context
        if analysis.get("symptoms"):
            prompt_parts.append(f"Identified symptoms: {', '.join(analysis['symptoms'])}")
        if analysis.get("medications"):
            prompt_parts.append(f"Current medications: {', '.join(analysis['medications'])}")
        if analysis.get("urgency") in ["high", "emergency"]:
            prompt_parts.append("⚠️ This has been flagged as potentially urgent.")

        prompt = "\n".join(prompt_parts)

        # Use conversation history if available
        if conversation_history:
            messages = list(conversation_history)
            messages.append({"role": "user", "content": prompt})
            return self.llm.generate_with_history(
                messages=messages,
                system=system_prompt,
                temperature=0.3,
                max_tokens=2048,
                model=REASONER_MODEL,
            )

        return self.llm.generate(
            prompt=prompt,
            system=system_prompt,
            temperature=0.3,
            max_tokens=2048,
            model=REASONER_MODEL,
        )

    def reason_stream(
        self,
        analysis: dict,
        evidence: str,
        health_profile: dict = None,
        conversation_history: list[dict] = None,
    ):
        """
        Stream a reasoned answer token-by-token. Yields string chunks.
        Same logic as reason() but uses the streaming Ollama methods.
        """
        language = analysis.get("language", "en")
        system_prompt = REASONER_SYSTEM_AR if language == "ar" else REASONER_SYSTEM_EN

        prompt_parts = []
        prompt_parts.append(f"EVIDENCE:\n{evidence}")

        if health_profile:
            profile_str = self._format_profile(health_profile)
            prompt_parts.append(f"\nUSER HEALTH PROFILE:\n{profile_str}")

        query = analysis.get("original_query", analysis.get("summary", ""))
        prompt_parts.append(f"\nUSER QUESTION: {query}")

        if analysis.get("symptoms"):
            prompt_parts.append(f"Identified symptoms: {', '.join(analysis['symptoms'])}")
        if analysis.get("medications"):
            prompt_parts.append(f"Current medications: {', '.join(analysis['medications'])}")
        if analysis.get("urgency") in ["high", "emergency"]:
            prompt_parts.append("⚠️ This has been flagged as potentially urgent.")

        prompt = "\n".join(prompt_parts)

        if conversation_history:
            messages = list(conversation_history)
            messages.append({"role": "user", "content": prompt})
            yield from self.llm.generate_with_history_stream(
                messages=messages,
                system=system_prompt,
                temperature=0.3,
                max_tokens=2048,
                model=REASONER_MODEL,
            )
        else:
            yield from self.llm.generate_stream(
                prompt=prompt,
                system=system_prompt,
                temperature=0.3,
                max_tokens=2048,
                model=REASONER_MODEL,
            )

    def _format_profile(self, profile: dict) -> str:
        """Format user health profile for the reasoning prompt."""
        parts = []
        if profile.get("age"):
            parts.append(f"Age: {profile['age']}")
        if profile.get("weight_kg"):
            parts.append(f"Weight: {profile['weight_kg']} kg")
        if profile.get("height_cm"):
            parts.append(f"Height: {profile['height_cm']} cm")
        if profile.get("conditions"):
            parts.append(f"Known conditions: {', '.join(profile['conditions'])}")
        if profile.get("medications"):
            meds = []
            for m in profile["medications"]:
                if isinstance(m, dict):
                    meds.append(f"{m.get('name', '')} {m.get('dose', '')}".strip())
                elif isinstance(m, str):
                    meds.append(m)
            parts.append(f"Medications: {', '.join(meds)}")
        if profile.get("allergies"):
            parts.append(f"Allergies: {', '.join(profile['allergies'])}")
        if profile.get("goals"):
            parts.append(f"Health goals: {', '.join(profile['goals'])}")
        return "\n".join(parts) if parts else "No profile available"
