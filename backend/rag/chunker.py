"""
MedMind — Smart Document Chunker
Splits medical texts into semantically meaningful chunks optimized for RAG retrieval.
"""

import re
from typing import Optional


def chunk_text(
    text: str,
    chunk_size: int = 600,
    overlap: int = 120,
    min_chunk_length: int = 80,
) -> list[str]:
    """
    Split text into overlapping chunks, breaking at natural boundaries.

    Medical texts benefit from smaller chunks (500-700 chars) because:
    - Small models handle focused evidence better
    - Each chunk covers one concept/fact
    - Retrieval is more precise

    Args:
        text: The input text to chunk
        chunk_size: Target chunk size in characters
        overlap: Character overlap between consecutive chunks
        min_chunk_length: Minimum chunk length to keep

    Returns:
        List of text chunks
    """
    if not text or len(text.strip()) < min_chunk_length:
        return []

    # Normalize whitespace
    cleaned = " ".join(text.split())

    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks = []
    start = 0

    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))

        # Try to break at sentence boundaries for cleaner chunks
        if end < len(cleaned):
            best_break = _find_best_break(cleaned, start, end)
            if best_break > start + (chunk_size // 3):
                end = best_break

        chunk = cleaned[start:end].strip()
        if len(chunk) >= min_chunk_length:
            chunks.append(chunk)

        if end >= len(cleaned):
            break

        # Move forward with overlap
        start = max(end - overlap, start + 1)

    return chunks


def chunk_medical_document(
    text: str,
    title: str = "",
    chunk_size: int = 600,
    overlap: int = 120,
) -> list[dict]:
    """
    Chunk a medical document into structured pieces with metadata.

    Attempts to detect sections (headers, bullet points) and keeps
    section context in each chunk for better retrieval.

    Args:
        text: Full document text
        title: Document title for metadata
        chunk_size: Target chunk size
        overlap: Overlap between chunks

    Returns:
        List of dicts with 'content', 'section', 'chunk_index' keys
    """
    sections = _split_into_sections(text)
    all_chunks = []
    global_index = 0

    for section_title, section_text in sections:
        chunks = chunk_text(section_text, chunk_size, overlap)

        for chunk in chunks:
            # Prepend section context for better retrieval
            contextualized = chunk
            if section_title and section_title.lower() not in chunk.lower():
                contextualized = f"{section_title}: {chunk}"

            all_chunks.append({
                "content": contextualized,
                "section": section_title or "General",
                "chunk_index": global_index,
                "document_title": title,
            })
            global_index += 1

    return all_chunks


def _find_best_break(text: str, start: int, end: int) -> int:
    """Find the best position to break text at a natural boundary."""
    # Priority: sentence end > semicolon > comma > space
    break_chars = [
        (". ", 0),
        ("? ", 0),
        ("! ", 0),
        (".\n", 0),
        ("; ", -5),
        (", ", -10),
        (" ", -20),
    ]

    best_pos = start
    best_score = -999

    for char, bonus in break_chars:
        pos = text.rfind(char, start + (end - start) // 3, end)
        if pos > start:
            # Prefer breaks closer to the target end
            score = pos + bonus
            if score > best_score:
                best_score = score
                best_pos = pos + len(char)

    return best_pos if best_pos > start else end


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """
    Detect section headers and split text accordingly.
    Handles markdown headers, numbered sections, and ALL-CAPS headers.
    """
    # Patterns that indicate a section header
    header_patterns = [
        r"^#{1,4}\s+(.+)$",                    # Markdown: ## Header
        r"^(\d+\.(?:\d+\.)*\s+.+)$",           # Numbered: 1.2 Header
        r"^([A-Z][A-Z\s]{3,}):?\s*$",          # ALL CAPS: SYMPTOMS
        r"^(?:Section|Chapter)\s+\d+[:.]\s*(.+)$",  # Section 1: Header
    ]

    lines = text.split("\n")
    sections = []
    current_title = ""
    current_lines = []

    for line in lines:
        is_header = False
        for pattern in header_patterns:
            match = re.match(pattern, line.strip(), re.IGNORECASE)
            if match:
                # Save previous section
                if current_lines:
                    content = "\n".join(current_lines).strip()
                    if content:
                        sections.append((current_title, content))

                current_title = match.group(1).strip() if match.groups() else line.strip()
                current_title = current_title.strip("#").strip()
                current_lines = []
                is_header = True
                break

        if not is_header:
            current_lines.append(line)

    # Don't forget the last section
    if current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append((current_title, content))

    # If no sections were detected, return the whole text as one section
    if not sections:
        sections = [("", text)]

    return sections
