"""
MedMind — Ollama LLM Client
Unified interface for text generation and vision tasks via local Ollama models.

Supports per-call model override so different skills can use different models:
- Small/fast model for structured tasks (analyzer, verifier)
- Larger model for free-form reasoning
"""

import json
import re
import ollama
from typing import Optional

from config import (
    LLM_MODEL,
    ANALYZER_MODEL,
    REASONER_MODEL,
    VERIFIER_MODEL,
    VISION_MODEL,
    OLLAMA_HOST,
)


class OllamaClient:
    """Wrapper around Ollama for text and vision inference."""

    def __init__(self):
        self.client = ollama.Client(host=OLLAMA_HOST)
        # Default model used when a call doesn't specify one.
        self.text_model = LLM_MODEL
        self.vision_model = VISION_MODEL
        # Per-skill assignments — exposed for stats / debugging.
        self.models = {
            "default": LLM_MODEL,
            "analyzer": ANALYZER_MODEL,
            "reasoner": REASONER_MODEL,
            "verifier": VERIFIER_MODEL,
            "vision": VISION_MODEL,
        }
        self._verify_connection()

    def _verify_connection(self):
        """Check Ollama is running and report assigned models."""
        try:
            models = self.client.list()
            available = [m.model for m in models.models]
            print(f"[Ollama] Connected. Available models: {available}")
            print(f"[Ollama] Skill assignments: {self.models}")
            for role, name in self.models.items():
                if name not in available and not any(name.split(":")[0] in a for a in available):
                    print(f"[Ollama] [Warning] Model '{name}' for role '{role}' not pulled.")
        except Exception as e:
            print(f"[Ollama] [Warning] Connection failed: {e}")
            print("[Ollama] Make sure Ollama is running: 'ollama serve'")

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        json_mode: bool = False,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate a text response from the LLM.

        Args:
            prompt: The user/task prompt
            system: System instruction
            temperature: Creativity level (lower = more focused)
            max_tokens: Maximum response length
            json_mode: If True, request JSON-formatted output
            model: Override which Ollama model to use (defaults to LLM_MODEL)
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        options = {
            "temperature": temperature,
            "num_predict": max_tokens,
        }

        try:
            response = self.client.chat(
                model=model or self.text_model,
                messages=messages,
                options=options,
                format="json" if json_mode else "",
            )
            return response.message.content.strip()
        except Exception as e:
            print(f"[Ollama] Generation error ({model or self.text_model}): {e}")
            return ""

    def generate_stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        model: Optional[str] = None,
    ):
        """
        Stream a text response token-by-token. Yields string chunks.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        options = {
            "temperature": temperature,
            "num_predict": max_tokens,
        }

        try:
            stream = self.client.chat(
                model=model or self.text_model,
                messages=messages,
                options=options,
                stream=True,
            )
            for chunk in stream:
                content = chunk.message.content
                if content:
                    yield content
        except Exception as e:
            print(f"[Ollama] Stream error ({model or self.text_model}): {e}")

    def generate_with_history_stream(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        model: Optional[str] = None,
    ):
        """Stream a response using full conversation history. Yields string chunks."""
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        options = {
            "temperature": temperature,
            "num_predict": max_tokens,
        }

        try:
            stream = self.client.chat(
                model=model or self.text_model,
                messages=full_messages,
                options=options,
                stream=True,
            )
            for chunk in stream:
                content = chunk.message.content
                if content:
                    yield content
        except Exception as e:
            print(f"[Ollama] Stream error ({model or self.text_model}): {e}")

    def generate_with_history(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        model: Optional[str] = None,
    ) -> str:
        """Generate a response using full conversation history."""
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        options = {
            "temperature": temperature,
            "num_predict": max_tokens,
        }

        try:
            response = self.client.chat(
                model=model or self.text_model,
                messages=full_messages,
                options=options,
            )
            return response.message.content.strip()
        except Exception as e:
            print(f"[Ollama] Generation error ({model or self.text_model}): {e}")
            return ""

    def analyze_image(
        self,
        prompt: str,
        image_bytes: bytes,
        system: str = "",
        temperature: float = 0.3,
    ) -> str:
        """Analyze an image using the vision model."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({
            "role": "user",
            "content": prompt,
            "images": [image_bytes],
        })

        try:
            response = self.client.chat(
                model=self.vision_model,
                messages=messages,
                options={"temperature": temperature, "num_predict": 1024},
            )
            return response.message.content.strip()
        except Exception as e:
            print(f"[Ollama] Vision error: {e}")
            return ""

    def extract_json(self, text: str) -> Optional[dict]:
        """Extract JSON from a model response, handling markdown code blocks."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None
