"""Unit tests for the document chunker — pure functions, no LLM."""
from rag.chunker import chunk_text, chunk_medical_document


def test_short_text_returns_one_chunk():
    text = (
        "Hypertension affects roughly one in three adults worldwide. "
        "It is usually asymptomatic and is detected on routine screening."
    )
    chunks = chunk_text(text, chunk_size=600)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []
    assert chunk_text("tiny") == []  # below default min_chunk_length


def test_long_text_produces_multiple_overlapping_chunks():
    sentence = "Hypertension is a chronic medical condition. " * 60
    chunks = chunk_text(sentence, chunk_size=400, overlap=80)
    assert len(chunks) >= 3
    # Overlap means consecutive chunks share content somewhere.
    for a, b in zip(chunks, chunks[1:]):
        assert any(word in b for word in a.split()[:5])


def test_chunks_break_at_sentence_boundaries():
    text = (
        "First sentence ends here. Second sentence ends here. "
        "Third sentence ends here. Fourth sentence ends here. "
        "Fifth sentence ends here. "
    ) * 10
    chunks = chunk_text(text, chunk_size=200, overlap=40)
    # Most chunks should end on a sentence terminator.
    end_in_period = sum(1 for c in chunks if c.rstrip().endswith("."))
    assert end_in_period >= len(chunks) - 1


def test_chunk_medical_document_attaches_section_metadata():
    body_a = "Patients commonly report headache, fatigue, and dizziness. " * 8
    body_b = "Treatment is usually lifestyle changes and medication. " * 8
    doc = "## Symptoms\n" + body_a + "\n\n## Treatment\n" + body_b
    chunks = chunk_medical_document(doc, title="Hypertension")
    assert any(c["section"].lower().startswith("symptom") for c in chunks)
    assert any(c["section"].lower().startswith("treatment") for c in chunks)
    assert all(c["document_title"] == "Hypertension" for c in chunks)
    assert all("content" in c and "chunk_index" in c for c in chunks)


def test_chunker_prepends_section_for_better_retrieval():
    body = (
        "Diagnosis is established with repeated readings of 130/80 mmHg "
        "or higher on two or more occasions in clinic. "
    ) * 4
    doc = "## Diagnosis\n" + body
    chunks = chunk_medical_document(doc, title="Hypertension")
    # The section title should appear in at least one chunk's content,
    # so vector search picks up "diagnosis" alongside the body text.
    assert any("Diagnosis" in c["content"] for c in chunks)
