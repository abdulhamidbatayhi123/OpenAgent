"""
MedMind — Pipeline Orchestrator
Chains all 5 skills into a single pipeline that turns a user's health
question into a verified, cited, safe answer.

Pipeline: Query -> Analyze -> Retrieve -> Reason -> Verify -> Format

Conversational queries (greetings, identity, profile questions) are
handled by a fast-path that skips the RAG pipeline entirely.
"""

import json
import re
import time
from typing import Optional

from models.ollama_client import OllamaClient
from rag.vector_db import VectorDB
from rag.reranker import Reranker
from skills.symptom_analyzer import SymptomAnalyzer
from skills.medical_retriever import MedicalRetriever
from skills.clinical_reasoner import ClinicalReasoner
from skills.citation_verifier import CitationVerifier
from skills.safety_formatter import SafetyFormatter
from config import (
    CONFIDENCE_THRESHOLD,
    PROFILES_DIR,
    HISTORY_DIR,
    MAX_CONVERSATION_HISTORY,
    ENABLE_VISION,
    LLM_MODEL,
)


class Orchestrator:
    """Chains the 5 agentic skills into a complete pipeline."""

    def __init__(self):
        # Core components
        self.llm = OllamaClient()
        self.vector_db = VectorDB()
        self.reranker = Reranker()

        # Initialize all 5 skills
        self.analyzer = SymptomAnalyzer(self.llm)
        self.retriever = MedicalRetriever(self.vector_db, self.reranker)
        self.reasoner = ClinicalReasoner(self.llm)
        self.verifier = CitationVerifier(self.llm)
        self.formatter = SafetyFormatter()

        # User state
        self.health_profile: dict = {}
        self.conversation_history: list[dict] = []
        self.current_session_id: str = ""

        print("[Orchestrator] All 5 skills initialized", flush=True)

    # ── Conversational Fast-Path ─────────────────────────────────────
    # Patterns that should NEVER enter the RAG pipeline.

    _GREETING_PATTERNS = re.compile(
        r"^(hi|hello|hey|howdy|good\s*(morning|evening|afternoon|night)|"
        r"مرحبا|السلام عليكم|اهلا|هلا|صباح الخير|مساء الخير)[\s!.,]*$",
        re.IGNORECASE,
    )
    _IDENTITY_PATTERNS = re.compile(
        r"(what\s*is\s*your\s*name|who\s*are\s*you|tell\s*me\s*about\s*yourself|"
        r"what\s*can\s*you\s*do|ما\s*اسمك|من\s*أنت|من\s*انت|عرف\s*(عن\s*)?نفسك)",
        re.IGNORECASE,
    )
    _PROFILE_PATTERNS = re.compile(
        r"(what\s*is\s*my\s*name|what\'?s\s*my\s*name|do\s*you\s*know\s*my\s*name|"
        r"how\s*old\s*am\s*i|what\s*is\s*my\s*age|what\'?s\s*my\s*age|"
        r"my\s*weight|my\s*height|my\s*allergies|my\s*conditions|my\s*medications|my\s*goals|"
        r"what\s*do\s*you\s*know\s*about\s*me|tell\s*me\s*about\s*my\s*profile|"
        r"ما\s*اسمي|كم\s*عمري|ما\s*وزني|ما\s*طولي)",
        re.IGNORECASE,
    )
    _HEALTH_CALC_PATTERNS = re.compile(
        r"(am\s*i\s*(fat|overweight|underweight|obese|healthy\s*weight|normal\s*weight)|"
        r"(my|calculate\s*my|what\'?s\s*my|what\s*is\s*my)\s*(bmi|body\s*mass|ideal\s*weight|healthy\s*weight)|"
        r"ideal\s*weight\s*(for\s*me|based\s*on)|"
        r"(how\s*much\s*should\s*i\s*weigh|should\s*i\s*lose\s*weight|should\s*i\s*gain\s*weight)|"
        r"(according\s*to\s*my\s*(age|height|weight|profile).*\b(fat|weight|bmi|overweight|ideal|healthy))|"
        r"هل\s*(أنا|انا)\s*(سمين|نحيف|وزني\s*طبيعي|وزني\s*زايد))",
        re.IGNORECASE,
    )
    _THANKS_PATTERNS = re.compile(
        r"^(thanks|thank\s*you|thx|ty|شكرا|مشكور|شكراً)[\s!.,]*$",
        re.IGNORECASE,
    )

    def _is_conversational(self, message: str) -> Optional[str]:
        """
        Detect if a message is conversational (not medical).
        Returns a category string or None if it's a medical query.
        """
        msg = message.strip()
        if self._GREETING_PATTERNS.match(msg):
            return "greeting"
        if self._IDENTITY_PATTERNS.search(msg):
            return "identity"
        if self._PROFILE_PATTERNS.search(msg):
            return "profile"
        if self._HEALTH_CALC_PATTERNS.search(msg):
            return "health_calc"
        if self._THANKS_PATTERNS.match(msg):
            return "thanks"
        return None

    def _handle_conversational(self, message: str, category: str, session_id: str) -> dict:
        """
        Generate a quick, natural response for conversational queries.
        No RAG pipeline needed — just direct LLM or template responses.
        """
        start_time = time.time()
        profile = self.health_profile
        user_name = profile.get("name", "").strip() if profile else ""

        if category == "greeting":
            answer = self._greeting_response(user_name, message)
        elif category == "identity":
            answer = self._identity_response(user_name)
        elif category == "profile":
            answer = self._profile_response(message, profile)
        elif category == "health_calc":
            answer = self._health_calc_response(message, profile)
        elif category == "thanks":
            answer = self._thanks_response(user_name)
        else:
            answer = "How can I help you today?"

        self._save_turn(message, answer)

        return {
            "answer": answer,
            "sources": [],
            "grounded": True,
            "confidence": 1.0,
            "urgency": "none",
            "pipeline_time": round(time.time() - start_time, 2),
            "timings": {"conversational": round(time.time() - start_time, 3)},
            "steps_completed": 0,
            "retrieval_confidence": None,
            "analysis": {"query_type": "conversational", "urgency": "none", "symptoms": [], "medications": []},
            "removed_citations": [],
            "is_conversational": True,
        }

    def _greeting_response(self, user_name: str, message: str) -> str:
        is_arabic = any("؀" <= c <= "ۿ" for c in message)
        if is_arabic:
            name_part = f" {user_name}" if user_name else ""
            return f"أهلاً{name_part}! كيف أقدر أساعدك اليوم؟"
        name_part = f", {user_name}" if user_name else ""
        return f"Hey{name_part}! How can I help you today?"

    def _identity_response(self, user_name: str) -> str:
        name_part = f" Nice to have you here, {user_name}." if user_name else ""
        return (
            f"I'm MedMind, your private health and wellness assistant.{name_part} "
            "I can help you with health questions, nutrition info, medication lookups, "
            "and fitness guidance — all powered by local AI, so your data never leaves "
            "your device. Just ask me anything health-related!"
        )

    def _profile_response(self, message: str, profile: dict) -> str:
        if not profile:
            return (
                "I don't have a health profile set up for you yet. "
                "You can create one by clicking the profile button in the sidebar — "
                "it helps me give you more personalized answers."
            )

        msg_lower = message.lower()
        name = profile.get("name", "")

        # Specific field questions
        if "name" in msg_lower or "اسمي" in msg_lower:
            if name:
                return f"Your name is {name}, as you told me in your profile!"
            return "You haven't set a name in your profile yet. You can add one in the profile settings."

        if "age" in msg_lower or "old" in msg_lower or "عمري" in msg_lower:
            age = profile.get("age")
            if age:
                return f"According to your profile, you're {age} years old."
            return "You haven't set your age in your profile yet."

        if "weight" in msg_lower or "وزني" in msg_lower:
            w = profile.get("weight_kg")
            if w:
                return f"Your weight is {w} kg according to your profile."
            return "You haven't set your weight in your profile yet."

        if "height" in msg_lower or "طولي" in msg_lower:
            h = profile.get("height_cm")
            if h:
                return f"Your height is {h} cm according to your profile."
            return "You haven't set your height in your profile yet."

        # General "what do you know about me" — show full profile
        parts = []
        if name:
            parts.append(f"**Name:** {name}")
        if profile.get("age"):
            parts.append(f"**Age:** {profile['age']}")
        if profile.get("weight_kg"):
            parts.append(f"**Weight:** {profile['weight_kg']} kg")
        if profile.get("height_cm"):
            parts.append(f"**Height:** {profile['height_cm']} cm")
        if profile.get("conditions"):
            parts.append(f"**Conditions:** {', '.join(profile['conditions'])}")
        if profile.get("medications"):
            meds = []
            for m in profile["medications"]:
                if isinstance(m, dict):
                    meds.append(f"{m.get('name', '')} {m.get('dose', '')}".strip())
                elif isinstance(m, str):
                    meds.append(m)
            parts.append(f"**Medications:** {', '.join(meds)}")
        if profile.get("allergies"):
            parts.append(f"**Allergies:** {', '.join(profile['allergies'])}")
        if profile.get("goals"):
            parts.append(f"**Goals:** {', '.join(profile['goals'])}")

        if parts:
            return "Here's what I know about you from your profile:\n\n" + "\n".join(parts)
        return "Your profile is set up but doesn't have much detail yet. You can update it in the sidebar."

    def _thanks_response(self, user_name: str) -> str:
        name_part = f", {user_name}" if user_name else ""
        return f"You're welcome{name_part}! Let me know if you need anything else."

    def _health_calc_response(self, message: str, profile: dict) -> str:
        """Answer BMI / ideal weight / body composition questions using profile data."""
        if not profile:
            return (
                "I'd love to help with that, but I don't have your health profile yet. "
                "Please set up your profile (weight, height, age) using the profile "
                "button in the sidebar, and then ask me again!"
            )

        weight = profile.get("weight_kg")
        height_cm = profile.get("height_cm")
        age = profile.get("age")
        name = profile.get("name", "")

        if not weight or not height_cm:
            missing = []
            if not weight:
                missing.append("weight")
            if not height_cm:
                missing.append("height")
            return (
                f"I need your {' and '.join(missing)} to calculate this. "
                "Please update your profile in the sidebar and ask again!"
            )

        # Calculate BMI
        height_m = height_cm / 100.0
        bmi = weight / (height_m ** 2)
        bmi_rounded = round(bmi, 1)

        # BMI classification (WHO standard)
        if bmi < 18.5:
            category = "underweight"
            emoji = "🔵"
            advice = "You might benefit from a nutrient-dense diet to reach a healthier weight."
        elif bmi < 25.0:
            category = "normal (healthy weight)"
            emoji = "🟢"
            advice = "You're in a healthy range — keep up the good habits!"
        elif bmi < 30.0:
            category = "overweight"
            emoji = "🟡"
            advice = "A balanced diet and regular exercise can help you move toward a healthier range."
        else:
            category = "obese"
            emoji = "🟠"
            advice = "It's a good idea to talk to a healthcare provider about a plan that works for you."

        # Calculate ideal weight range (BMI 18.5–24.9)
        ideal_low = round(18.5 * (height_m ** 2), 1)
        ideal_high = round(24.9 * (height_m ** 2), 1)

        name_part = f", {name}" if name else ""

        parts = [
            f"Here's what I calculated based on your profile{name_part}:\n",
            f"**Your stats:** {weight} kg, {height_cm} cm"
            + (f", {age} years old" if age else ""),
            f"**Your BMI:** {bmi_rounded} — {emoji} {category}",
            f"**Ideal weight range for your height:** {ideal_low}–{ideal_high} kg",
            f"\n{advice}",
            "\n*BMI is a general screening tool and doesn't account for muscle mass, "
            "bone density, or body composition. For a complete picture, consider "
            "consulting a healthcare professional.*",
        ]

        return "\n".join(parts)

    def process(
        self,
        user_message: str,
        session_id: str = "default",
        image_bytes: Optional[bytes] = None,
    ) -> dict:
        """Run the full 5-skill pipeline on a user message."""
        start_time = time.time()
        timings: dict[str, float] = {}

        # Load user profile and history for this session
        if session_id != self.current_session_id:
            self.current_session_id = session_id
            self.health_profile = self._load_profile(session_id)
            self.conversation_history = self._load_history(session_id)

        # ── Fast-path: Conversational queries (no RAG needed) ─────────
        if not image_bytes:
            conv_category = self._is_conversational(user_message)
            if conv_category:
                print(f"[Pipeline] Conversational fast-path: {conv_category}", flush=True)
                return self._handle_conversational(user_message, conv_category, session_id)

        # ── Step 0: Image Analysis (if image provided) ────────────────
        image_context = ""
        if image_bytes and ENABLE_VISION:
            t0 = time.time()
            image_context = self._analyze_image(user_message, image_bytes)
            timings["vision"] = round(time.time() - t0, 3)
            if image_context:
                user_message = f"{user_message}\n\n[Image Analysis: {image_context}]"

        # ── Step 1: Symptom Analyzer ──────────────────────────────────
        print("[Pipeline] Step 1/5: Analyzing query...", flush=True)
        t0 = time.time()
        analysis = self.analyzer.analyze(user_message, self.health_profile)
        timings["analyze"] = round(time.time() - t0, 3)
        print(f"  - Type: {analysis['query_type']}, Urgency: {analysis['urgency']}", flush=True)
        print(f"  - Sub-queries: {analysis['sub_queries']}", flush=True)

        # ── Step 2: Medical Retriever ─────────────────────────────────
        print("[Pipeline] Step 2/5: Retrieving evidence...", flush=True)
        t0 = time.time()
        evidence_results = self.retriever.retrieve(analysis)
        retrieval_confidence = self.retriever.get_retrieval_confidence(evidence_results)
        timings["retrieve"] = round(time.time() - t0, 3)
        print(f"  - Found {len(evidence_results)} relevant chunks", flush=True)
        print(f"  - Retrieval confidence: {retrieval_confidence:.2f}", flush=True)

        is_grounded = retrieval_confidence >= CONFIDENCE_THRESHOLD

        if not is_grounded and analysis["urgency"] != "emergency":
            print("[Pipeline] [Warning] Insufficient evidence - refusing to answer", flush=True)
            t0 = time.time()
            response = self.formatter.format(
                answer="",
                analysis=analysis,
                evidence_results=[],
                verification={"grounded": False, "confidence": 0.0},
                is_grounded=False,
            )
            timings["format"] = round(time.time() - t0, 3)
            response["pipeline_time"] = round(time.time() - start_time, 2)
            response["timings"] = timings
            response["steps_completed"] = 2
            response["retrieval_confidence"] = round(retrieval_confidence, 3)
            self._save_turn(user_message, response["answer"])
            return response

        # ── Step 3: Clinical Reasoner ─────────────────────────────────
        print("[Pipeline] Step 3/5: Reasoning over evidence...", flush=True)
        t0 = time.time()
        evidence_text = self.retriever.format_evidence_for_prompt(evidence_results)
        raw_answer = self.reasoner.reason(
            analysis=analysis,
            evidence=evidence_text,
            health_profile=self.health_profile,
            conversation_history=self.conversation_history[-6:],
        )
        timings["reason"] = round(time.time() - t0, 3)
        print(f"  - Generated {len(raw_answer)} char answer", flush=True)

        # ── Step 4: Citation Verifier ─────────────────────────────────
        print("[Pipeline] Step 4/5: Verifying citations...", flush=True)
        t0 = time.time()
        verification = self.verifier.verify(
            answer=raw_answer,
            evidence=evidence_text,
            max_source_index=len(evidence_results),
        )
        timings["verify"] = round(time.time() - t0, 3)
        print(f"  - Grounded: {verification['grounded']}", flush=True)
        print(f"  - Removed citations: {verification.get('removed_citations', [])}", flush=True)

        # ── Step 5: Safety Formatter ──────────────────────────────────
        print("[Pipeline] Step 5/5: Formatting response...", flush=True)
        t0 = time.time()
        response = self.formatter.format(
            answer=verification["answer"],
            analysis=analysis,
            evidence_results=evidence_results,
            verification=verification,
            is_grounded=is_grounded,
        )
        timings["format"] = round(time.time() - t0, 3)

        # Pipeline metadata
        response["pipeline_time"] = round(time.time() - start_time, 2)
        response["timings"] = timings
        response["steps_completed"] = 5
        response["retrieval_confidence"] = round(retrieval_confidence, 3)
        response["analysis"] = {
            "query_type": analysis["query_type"],
            "urgency": analysis["urgency"],
            "symptoms": analysis.get("symptoms", []),
            "medications": analysis.get("medications", []),
        }
        # Surface verifier output so the UI can show citations the verifier
        # stripped before the user saw them.
        response["removed_citations"] = verification.get("removed_citations", [])

        if image_context:
            response["image_analysis"] = image_context

        self._save_turn(user_message, response["answer"])

        print(f"[Pipeline] Complete in {response['pipeline_time']}s — {timings}", flush=True)
        return response

    # ── Streaming Pipeline ─────────────────────────────────────────────
    def process_stream(
        self,
        user_message: str,
        session_id: str = "default",
        image_bytes: Optional[bytes] = None,
    ):
        """
        Generator that yields SSE-formatted events as the pipeline runs.
        Events: step (status), token (streamed answer chunk), done (final metadata).
        """
        import json as _json
        start_time = time.time()
        timings: dict[str, float] = {}

        # Load user state
        if session_id != self.current_session_id:
            self.current_session_id = session_id
            self.health_profile = self._load_profile(session_id)
            self.conversation_history = self._load_history(session_id)

        # Conversational fast-path
        if not image_bytes:
            conv_category = self._is_conversational(user_message)
            if conv_category:
                result = self._handle_conversational(user_message, conv_category, session_id)
                yield f"data: {_json.dumps({'type': 'token', 'content': result['answer']})}\n\n"
                yield f"data: {_json.dumps({'type': 'done', 'metadata': result})}\n\n"
                return

        # Step 0: Image
        image_context = ""
        if image_bytes and ENABLE_VISION:
            t0 = time.time()
            image_context = self._analyze_image(user_message, image_bytes)
            timings["vision"] = round(time.time() - t0, 3)
            if image_context:
                user_message = f"{user_message}\n\n[Image Analysis: {image_context}]"

        # Step 1: Analyze
        yield f"data: {_json.dumps({'type': 'step', 'step': 1, 'name': 'Analyzing query...'})}\n\n"
        t0 = time.time()
        analysis = self.analyzer.analyze(user_message, self.health_profile)
        timings["analyze"] = round(time.time() - t0, 3)

        # Step 2: Retrieve
        yield f"data: {_json.dumps({'type': 'step', 'step': 2, 'name': 'Retrieving evidence...'})}\n\n"
        t0 = time.time()
        evidence_results = self.retriever.retrieve(analysis)
        retrieval_confidence = self.retriever.get_retrieval_confidence(evidence_results)
        timings["retrieve"] = round(time.time() - t0, 3)

        is_grounded = retrieval_confidence >= CONFIDENCE_THRESHOLD

        if not is_grounded and analysis["urgency"] != "emergency":
            t0 = time.time()
            response = self.formatter.format(
                answer="", analysis=analysis, evidence_results=[],
                verification={"grounded": False, "confidence": 0.0}, is_grounded=False,
            )
            timings["format"] = round(time.time() - t0, 3)
            response["pipeline_time"] = round(time.time() - start_time, 2)
            response["timings"] = timings
            response["steps_completed"] = 2
            response["retrieval_confidence"] = round(retrieval_confidence, 3)
            self._save_turn(user_message, response["answer"])
            yield f"data: {_json.dumps({'type': 'token', 'content': response['answer']})}\n\n"
            yield f"data: {_json.dumps({'type': 'done', 'metadata': response})}\n\n"
            return

        # Step 3: Reason (STREAMED)
        yield f"data: {_json.dumps({'type': 'step', 'step': 3, 'name': 'Reasoning...'})}\n\n"
        t0 = time.time()
        evidence_text = self.retriever.format_evidence_for_prompt(evidence_results)
        raw_answer_parts = []
        for chunk in self.reasoner.reason_stream(
            analysis=analysis,
            evidence=evidence_text,
            health_profile=self.health_profile,
            conversation_history=self.conversation_history[-6:],
        ):
            raw_answer_parts.append(chunk)
            yield f"data: {_json.dumps({'type': 'token', 'content': chunk})}\n\n"
        raw_answer = "".join(raw_answer_parts)
        timings["reason"] = round(time.time() - t0, 3)

        # Step 4: Verify
        yield f"data: {_json.dumps({'type': 'step', 'step': 4, 'name': 'Verifying citations...'})}\n\n"
        t0 = time.time()
        verification = self.verifier.verify(
            answer=raw_answer, evidence=evidence_text,
            max_source_index=len(evidence_results),
        )
        timings["verify"] = round(time.time() - t0, 3)

        # Step 5: Format
        yield f"data: {_json.dumps({'type': 'step', 'step': 5, 'name': 'Formatting...'})}\n\n"
        t0 = time.time()
        response = self.formatter.format(
            answer=verification["answer"], analysis=analysis,
            evidence_results=evidence_results, verification=verification,
            is_grounded=is_grounded,
        )
        timings["format"] = round(time.time() - t0, 3)

        response["pipeline_time"] = round(time.time() - start_time, 2)
        response["timings"] = timings
        response["steps_completed"] = 5
        response["retrieval_confidence"] = round(retrieval_confidence, 3)
        response["analysis"] = {
            "query_type": analysis["query_type"],
            "urgency": analysis["urgency"],
            "symptoms": analysis.get("symptoms", []),
            "medications": analysis.get("medications", []),
        }
        response["removed_citations"] = verification.get("removed_citations", [])

        if image_context:
            response["image_analysis"] = image_context

        self._save_turn(user_message, response["answer"])

        # Send final formatted answer (replaces streamed tokens) + metadata.
        # Defensive: ensure every value in response is JSON-serializable.
        try:
            done_event = {"type": "done", "metadata": response}
            done_json = _json.dumps(done_event, default=str)
            yield "data: " + done_json + "\n\n"
        except Exception as ser_err:
            print("[Stream] JSON serialization error in done event: " + str(ser_err), flush=True)
            # Fallback: send at least the answer and sources
            fallback_meta = {
                "answer": str(response.get("answer", "")),
                "sources": response.get("sources", []),
                "grounded": bool(response.get("grounded", False)),
                "confidence": float(response.get("confidence", 0)),
                "urgency": str(response.get("urgency", "none")),
                "pipeline_time": float(response.get("pipeline_time", 0)),
                "steps_completed": int(response.get("steps_completed", 0)),
            }
            fallback_event = {"type": "done", "metadata": fallback_meta}
            yield "data: " + _json.dumps(fallback_event) + "\n\n"

    # ── Image Analysis ────────────────────────────────────────────────
    def _analyze_image(self, user_message: str, image_bytes: bytes) -> str:
        print("[Pipeline] Analyzing image with vision model...", flush=True)
        prompt = (
            f"The user sent this image along with the question: \"{user_message}\"\n\n"
            "Describe what you see in the image. If it's food, estimate the "
            "ingredients and approximate calories. If it's a nutrition label, "
            "extract the key nutritional values. Be factual and concise."
        )
        return self.llm.analyze_image(prompt, image_bytes)

    # ── Health Profile Management ─────────────────────────────────────
    def _load_profile(self, session_id: str) -> dict:
        path = PROFILES_DIR / f"{session_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                profile = json.load(f)
                print(f"[Profile] Loaded profile for '{session_id}'", flush=True)
                return profile
        return {}

    def save_profile(self, session_id: str, profile: dict):
        path = PROFILES_DIR / f"{session_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        self.health_profile = profile
        print(f"[Profile] Saved profile for '{session_id}'", flush=True)

    def get_profile(self, session_id: str) -> dict:
        return self._load_profile(session_id)

    # ── Conversation Memory ───────────────────────────────────────────
    def _load_history(self, session_id: str) -> list[dict]:
        path = HISTORY_DIR / f"{session_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_turn(self, user_message: str, assistant_response: str):
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": assistant_response})

        if len(self.conversation_history) > MAX_CONVERSATION_HISTORY * 2:
            self.conversation_history = self.conversation_history[-(MAX_CONVERSATION_HISTORY * 2):]

        path = HISTORY_DIR / f"{self.current_session_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)

    def clear_history(self, session_id: str):
        path = HISTORY_DIR / f"{session_id}.json"
        if path.exists():
            path.unlink()
        if session_id == self.current_session_id:
            self.conversation_history = []
        print(f"[History] Cleared for '{session_id}'", flush=True)

    # ── Knowledge Base Stats ──────────────────────────────────────────
    def get_stats(self) -> dict:
        db_counts = self.vector_db.count()
        return {
            "knowledge_base": db_counts,
            "llm_model": self.llm.text_model,
            "vision_model": self.llm.vision_model,
            "models": self.llm.models,
            "reranker_enabled": self.reranker.enabled,
            "active_session": self.current_session_id,
            "conversation_turns": len(self.conversation_history) // 2,
        }
