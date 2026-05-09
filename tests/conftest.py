"""Add backend/ to sys.path so tests can import skills, rag, etc."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
