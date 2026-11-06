import os
import pymupdf
from fastembed import TextEmbedding
from src.config import EMBEDDING_MODEL
from src.db import get_connection

embedder = TextEmbedding(model_name=EMBEDDING_MODEL)

def recursive_chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    """Splits text into chunks preserving semantic paragraph boundaries."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        cleaned_para = " ".join(para.split())
        if not cleaned_para:
            continue

        if len(current_chunk) + len(cleaned_para) <= chunk_size:
            current_chunk = f"{current_chunk}\n\n{cleaned_para}".strip()
        else:
            if current_chunk:
                chunks.append(current_chunk)
                words = current_chunk.split()
                tail = " ".join(words[-overlap:]) if len(words) > overlap else ""
                current_chunk = f"{tail}\n\n{cleaned_para}".strip()
            else:
                chunks.append(cleaned_para[:chunk_size])
                current_chunk = cleaned_para[chunk_size - overlap:]

    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def ingest_pdf(file_path: str, course_id: str, doc_type: str = "notes", uploaded_by: str = None) -> dict:
    """Extracts text per page, chunks, embeds, and stores in Neon pgvector."""
    filename = os.path.basename(file_path)

    # Use context manager so the file handle is reliably closed on Windows
    with pymupdf.open(file_path) as doc:
        total_chunks = 0
        pages_data = []

        for page_idx in range(len(doc)):
            page_num = page_idx + 1
            page_text = doc[page_idx].get_text()
            if not page_text.strip():
                continue

            page_chunks = recursive_chunk_text(page_text, chunk_size=500, overlap=80)
            if not page_chunks:
                continue

            embeddings = list(embedder.embed(page_chunks))
            pages_data.append((page_num, page_chunks, embeddings))

    # Perform DB writes after the PDF handle is safely closed
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Register Document Record
            cur.execute(
                """
                INSERT INTO documents (filename, course_id, doc_type, uploaded_by)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (filename, course_id, doc_type, uploaded_by)
            )
            doc_id = cur.fetchone()[0]

            # 2. Insert Chunks with explicit vector cast
            for page_num, chunks, embeddings in pages_data:
                for chunk_idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                    # Format float vector array as Postgres vector literal "[0.123, -0.456, ...]"
                    vec_str = "[" + ",".join(str(f) for f in embedding.tolist()) + "]"
                    cur.execute(
                        """
                        INSERT INTO document_chunks 
                        (document_id, course_id, doc_type, page_number, chunk_index, content, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::vector);
                        """,
                        (doc_id, course_id, doc_type, page_num, chunk_idx, chunk_text, vec_str)
                    )
                    total_chunks += 1

    return {
        "document_id": str(doc_id),
        "filename": filename,
        "course_id": course_id,
        "doc_type": doc_type,
        "total_chunks": total_chunks
    }