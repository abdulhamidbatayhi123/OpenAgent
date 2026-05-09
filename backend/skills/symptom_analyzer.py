"""
MedMind — Skill 1: Symptom Analyzer
Parses user queries to extract symptoms, medications, body systems,
and generates targeted sub-queries for better retrieval.

This is the first step in the pipeline — it turns a vague question
into structured, searchable components.
"""

from models.ollama_client import OllamaClient
from config import ANALYZER_MODEL

ANALYZER_SYSTEM = """You are a medical query analyzer. Your job is to parse a user's health question and extract structured information.

You MUST respond with valid JSON only. No explanations, no markdown, just JSON.

Extract the following:
- "query_type": one of ["symptom", "medication", "nutrition", "fitness", "general_health", "emergency"]
- "symptoms": list of symptoms mentioned (empty list if none)
- "medications": list of medications mentioned (empty list if none)
- "conditions": list of known conditions mentioned (empty list if none)
- "body_systems": list of relevant body systems (e.g., "cardiovascular", "neurological", "musculoskeletal", "digestive", "respiratory")
- "urgency": one of ["low", "medium", "high", "emergency"]
- "sub_queries": list of 1-4 focused search queries that would help answer this question. Each should target a specific aspect.
- "language": "en" or "ar" based on the question language
- "needs_image": true if the question mentions or implies needing visual analysis
- "summary": a clean one-sentence restatement of what the user is asking

Emergency indicators (set urgency to "emergency"):
- Chest pain, difficulty breathing, severe bleeding
- Loss of consciousness, stroke symptoms
- Severe allergic reactions, poisoning
- Suicidal thoughts or self-harm

Example input: "I have headaches and blurred vision and I take metformin, should I worry?"
Example output:
{
  "query_type": "symptom",
  "symptoms": ["headache", "blurred vision"],
  "medications": ["metformin"],
  "conditions": [],
  "body_systems": ["neurological", "ophthalmological", "endocrine"],
  "urgency": "medium",
  "sub_queries": [
    "headache and blurred vision causes",
    "metformin side effects vision problems",
    "when to see a doctor for headache with vision changes"
  ],
  "language": "en",
  "needs_image": false,
  "summary": "User has headaches with blurred vision while taking metformin and wants to know if it's concerning."
}"""


class SymptomAnalyzer:
    """Skill 1: Parse and decompose health queries."""

    def __init__(self, llm: OllamaClient):
        self.llm = llm

    def analyze(self, user_message: str, health_profile: dict = None) -> dict:
        """
        Analyze a user's health query and extract structured information.

        Args:
            user_message: The raw user question
            health_profile: Optional user health profile for context

        Returns:
            Structured dict with query_type, symptoms, sub_queries, etc.
        """
        prompt = f"Analyze this health question:\n\n\"{user_message}\""

        # Add health profile context if available
        if health_profile:
            profile_context = self._format_profile(health_profile)
            prompt += f"\n\nUser health profile:\n{profile_context}"
            prompt += "\nConsider the user's existing conditions and medications when determining urgency and sub-queries."

        response = self.llm.generate(
            prompt=prompt,
            system=ANALYZER_SYSTEM,
            temperature=0.1,  # Low temperature for structured extraction
            json_mode=True,
            model=ANALYZER_MODEL,
        )

        parsed = self.llm.extract_json(response)

        if parsed:
            # Ensure all required fields exist with defaults
            return self._validate_output(parsed, user_message)

        # Fallback: if parsing fails, return a basic analysis
        return self._fallback_analysis(user_message)

    def _validate_output(self, parsed: dict, original_query: str) -> dict:
        """Ensure all required fields are present with valid values."""
        valid_types = ["symptom", "medication", "nutrition", "fitness", "general_health", "emergency"]
        valid_urgency = ["low", "medium", "high", "emergency"]

        return {
            "query_type": parsed.get("query_type", "general_health") if parsed.get("query_type") in valid_types else "general_health",
            "symptoms": parsed.get("symptoms", []),
            "medications": parsed.get("medications", []),
            "conditions": parsed.get("conditions", []),
            "body_systems": parsed.get("body_systems", []),
            "urgency": parsed.get("urgency", "low") if parsed.get("urgency") in valid_urgency else "low",
            "sub_queries": parsed.get("sub_queries", [original_query]),
            "language": parsed.get("language", "en"),
            "needs_image": parsed.get("needs_image", False),
            "summary": parsed.get("summary", original_query),
            "original_query": original_query,
        }

    def _fallback_analysis(self, user_message: str) -> dict:
        """Basic fallback when LLM parsing fails."""
        # Simple heuristic-based analysis
        message_lower = user_message.lower()

        urgency = "low"
        emergency_keywords = ["chest pain", "can't breathe", "unconscious", "severe bleeding", "stroke"]
        if any(kw in message_lower for kw in emergency_keywords):
            urgency = "emergency"

        query_type = "general_health"
        if any(w in message_lower for w in ["symptom", "pain", "hurts", "ache", "fever", "dizzy"]):
            query_type = "symptom"
        elif any(w in message_lower for w in ["calorie", "eat", "diet", "food", "nutrition", "meal"]):
            query_type = "nutrition"
        elif any(w in message_lower for w in ["exercise", "workout", "run", "walk", "gym", "fitness"]):
            query_type = "fitness"
        elif any(w in message_lower for w in ["drug", "medication", "medicine", "pill", "dose"]):
            query_type = "medication"

        return {
            "query_type": query_type,
            "symptoms": [],
            "medications": [],
            "conditions": [],
            "body_systems": [],
            "urgency": urgency,
            "sub_queries": [user_message],
            "language": "ar" if any("\u0600" <= c <= "\u06FF" for c in user_message) else "en",
            "needs_image": False,
            "summary": user_message,
            "original_query": user_message,
        }

    def _format_profile(self, profile: dict) -> str:
        """Format health profile for inclusion in the prompt."""
        parts = []
        if profile.get("conditions"):
            parts.append(f"Known conditions: {', '.join(profile['conditions'])}")
        if profile.get("medications"):
            meds = []
            for m in profile["medications"]:
                if isinstance(m, dict):
                    meds.append(f"{m.get('name', '')} {m.get('dose', '')}".strip())
                elif isinstance(m, str):
                    meds.append(m)
            parts.append(f"Current medications: {', '.join(meds)}")
        if profile.get("allergies"):
            parts.append(f"Allergies: {', '.join(profile['allergies'])}")
        if profile.get("age"):
            parts.append(f"Age: {profile['age']}")
        return "\n".join(parts) if parts else "No profile available"
