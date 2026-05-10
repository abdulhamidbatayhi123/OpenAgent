"""
MedMind — Configuration Module
All settings, constants, and thresholds in one place.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Paths --------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "vector_store"
PROFILES_DIR = BASE_DIR / "profiles"
HISTORY_DIR = BASE_DIR / "history"

# Ensure directories exist
for d in [DATA_DIR, CHROMA_DIR, PROFILES_DIR, HISTORY_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# --- Ollama Models ------------------------------------------------------------
# LLM_MODEL is the default fallback; per-skill overrides below let you assign
# a small fast model to structured tasks (analyzer, verifier) and a stronger
# model to free-form reasoning. This is the "multi-model" half of the
# multi-agent pipeline.
LLM_MODEL = os.getenv("MEDMIND_LLM_MODEL", "qwen2.5:3b")

# Per-skill model overrides — fall back to LLM_MODEL when unset.
ANALYZER_MODEL = os.getenv("MEDMIND_ANALYZER_MODEL", LLM_MODEL)
REASONER_MODEL = os.getenv("MEDMIND_REASONER_MODEL", LLM_MODEL)
VERIFIER_MODEL = os.getenv("MEDMIND_VERIFIER_MODEL", LLM_MODEL)

VISION_MODEL = os.getenv("MEDMIND_VISION_MODEL", "gemma3:4b")
EMBEDDING_MODEL = os.getenv("MEDMIND_EMBED_MODEL", "nomic-embed-text")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# --- RAG Settings -------------------------------------------------------------
CHUNK_SIZE = 600
CHUNK_OVERLAP = 120
TOP_K_RETRIEVAL = 15
TOP_K_RERANK = 5

# --- Confidence & Grounding --------------------------------------------------
# Minimum retrieval confidence (sigmoid-normalised) required before the
# pipeline will attempt to answer.  Below this, the system refuses honestly.
CONFIDENCE_THRESHOLD = 0.35

# --- Memory -------------------------------------------------------------------
MAX_CONVERSATION_HISTORY = 20

# --- Server -------------------------------------------------------------------
API_HOST = os.getenv("MEDMIND_HOST", "0.0.0.0")
API_PORT = int(os.getenv("MEDMIND_PORT", "8000"))

# --- Telegram Bot -------------------------------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# --- Feature Flags ------------------------------------------------------------
ENABLE_WEB_SEARCH = os.getenv("MEDMIND_WEB_SEARCH", "false").lower() == "true"
ENABLE_VISION = os.getenv("MEDMIND_VISION", "true").lower() == "true"
ENABLE_RERANKER = os.getenv("MEDMIND_RERANKER", "true").lower() == "true"

# --- Trusted Medical Sources -------------------------------------------------
TRUSTED_SOURCES = [
    "medlineplus.gov",
    "who.int",
    "mayoclinic.org",
    "cdc.gov",
    "nih.gov",
    "webmd.com",
    "healthline.com",
]

# --- ChromaDB Collection Names -----------------------------------------------
MEDICAL_COLLECTION = "medical_knowledge"
USER_DOCS_COLLECTION = "user_documents"
