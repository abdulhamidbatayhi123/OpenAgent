"""
MedMind — Data Ingestion Script
Loads the curated medical knowledge base into ChromaDB.

Run this once before starting the server:
    python scripts/ingest.py
"""

import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from rag.vector_db import VectorDB
from rag.chunker import chunk_text
from config import DATA_DIR


def ingest_medical_kb(db: VectorDB):
    """Load the curated medical conditions database."""
    path = DATA_DIR / "medical_kb.json"
    if not path.exists():
        print(f"[Skip] {path} not found")
        return 0

    with open(path, "r", encoding="utf-8") as f:
        conditions = json.load(f)

    chunks = []
    for condition in conditions:
        # Create a comprehensive text for each condition
        text = _format_condition(condition)

        # Chunk the text
        text_chunks = chunk_text(text, chunk_size=600, overlap=120)

        for i, chunk_text_content in enumerate(text_chunks):
            chunks.append({
                "content": chunk_text_content,
                "section": condition.get("category", "General"),
                "document_title": condition["condition"],
                "source": condition.get("source", "Medical Knowledge Base"),
                "source_url": condition.get("source_url", ""),
                "chunk_index": i,
            })

    added = db.add_medical_chunks(chunks)
    print(f"[Medical KB] Loaded {len(conditions)} conditions -> {added} chunks")
    return added


def ingest_drug_database(db: VectorDB):
    """Load the drug information database."""
    path = DATA_DIR / "drug_database.json"
    if not path.exists():
        print(f"[Skip] {path} not found")
        return 0

    with open(path, "r", encoding="utf-8") as f:
        drugs = json.load(f)

    chunks = []
    for drug in drugs:
        text = _format_drug(drug)
        text_chunks = chunk_text(text, chunk_size=600, overlap=120)

        for i, chunk_text_content in enumerate(text_chunks):
            chunks.append({
                "content": chunk_text_content,
                "section": f"Drug: {drug['category']}",
                "document_title": drug["name"],
                "source": drug.get("source", "Drug Database"),
                "source_url": drug.get("source_url", ""),
                "chunk_index": i,
            })

    added = db.add_medical_chunks(chunks)
    print(f"[Drug DB] Loaded {len(drugs)} drugs -> {added} chunks")
    return added


def ingest_nutrition_database(db: VectorDB):
    """Load the nutrition/food database."""
    path = DATA_DIR / "nutrition_db.json"
    if not path.exists():
        print(f"[Skip] {path} not found")
        return 0

    with open(path, "r", encoding="utf-8") as f:
        foods = json.load(f)

    chunks = []
    for food in foods:
        text = _format_food(food)
        chunks.append({
            "content": text,
            "section": f"Nutrition: {food.get('category', 'Food')}",
            "document_title": food["food"],
            "source": food.get("source", "USDA FoodData Central"),
            "source_url": food.get("source_url", ""),
            "chunk_index": 0,
        })

    added = db.add_medical_chunks(chunks)
    print(f"[Nutrition] Loaded {len(foods)} foods -> {added} chunks")
    return added


def _format_condition(c: dict) -> str:
    """Format a medical condition into a readable text for embedding."""
    parts = [
        f"Condition: {c['condition']}",
        f"Category: {c.get('category', 'General')}",
        f"Symptoms: {', '.join(c.get('symptoms', []))}",
        f"Causes: {', '.join(c.get('causes', []))}",
        f"Risk factors: {', '.join(c.get('risk_factors', []))}",
        f"Diagnosis: {c.get('diagnosis', '')}",
        f"Treatment: {c.get('treatment', '')}",
        f"Prevention: {c.get('prevention', '')}",
        f"When to see a doctor: {c.get('when_to_see_doctor', '')}",
    ]
    return "\n".join(parts)


def _format_drug(d: dict) -> str:
    """Format drug information into readable text."""
    parts = [
        f"Drug: {d['name']} ({', '.join(d.get('brand_names', []))})",
        f"Category: {d.get('category', '')}",
        f"Used for: {', '.join(d.get('used_for', []))}",
        f"How it works: {d.get('mechanism', '')}",
        f"Dosage: {d.get('dosage', '')}",
        f"Common side effects: {', '.join(d.get('common_side_effects', []))}",
        f"Serious side effects: {', '.join(d.get('serious_side_effects', []))}",
        f"Drug interactions: {', '.join(d.get('interactions', []))}",
        f"Contraindications: {', '.join(d.get('contraindications', []))}",
        f"Food interactions: {d.get('food_interactions', '')}",
    ]
    return "\n".join(parts)


def _format_food(f: dict) -> str:
    """Format food/nutrition data into readable text."""
    parts = [
        f"Food: {f['food']}",
        f"Serving size: {f.get('serving_size', '')}",
        f"Calories: {f.get('calories', 0)} kcal",
        f"Protein: {f.get('protein_g', 0)}g",
        f"Carbohydrates: {f.get('carbs_g', 0)}g",
        f"Fat: {f.get('fat_g', 0)}g",
        f"Fiber: {f.get('fiber_g', 0)}g",
    ]
    if f.get("notes"):
        parts.append(f"Notes: {f['notes']}")
    nutrients = f.get("key_nutrients", {})
    if nutrients:
        nutrient_str = ", ".join([f"{k}: {v}" for k, v in nutrients.items()])
        parts.append(f"Key nutrients: {nutrient_str}")
    return "\n".join(parts)


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  MedMind — Knowledge Base Ingestion")
    print("=" * 50 + "\n")

    # Check if we should clear existing data
    if "--clear" in sys.argv:
        print("[!] Clearing existing data...")
        db = VectorDB()
        db.clear_all()
    else:
        db = VectorDB()

    total = 0
    total += ingest_medical_kb(db)
    total += ingest_drug_database(db)
    total += ingest_nutrition_database(db)

    print(f"\n{'=' * 50}")
    print(f"  ✅ Total: {total} chunks ingested")
    counts = db.count()
    print(f"  > Medical KB: {counts['medical_kb']} chunks")
    print(f"  > User docs:  {counts['user_documents']} chunks")
    print(f"{'=' * 50}\n")
