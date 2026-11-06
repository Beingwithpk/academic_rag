from groq import Groq
from fastembed import TextEmbedding
from src.config import GROQ_API_KEY, GROQ_MODEL, EMBEDDING_MODEL
from src.db import get_connection

groq_client = Groq(api_key=GROQ_API_KEY)
embedder = TextEmbedding(model_name=EMBEDDING_MODEL)

def retrieve_chunks(query: str, course_id: str = None, top_k: int = 4):
    """Retrieves most relevant chunks using cosine distance (<=>)."""
    # Generate query vector
    query_vector = list(embedder.embed([query]))[0].tolist()

    # Dynamic WHERE clause to avoid ambiguous parameter types
    where_clauses = []
    params = [query_vector]

    if course_id:
        where_clauses.append("c.course_id = %s")
        params.append(course_id)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    params.extend([query_vector, top_k])

    sql = f"""
        SELECT c.content, c.page_number, d.filename, c.doc_type,
               1 - (c.embedding <=> %s::vector) AS similarity_score
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.id
        {where_sql}
        ORDER BY c.embedding <=> %s::vector ASC
        LIMIT %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            results = cur.fetchall()

    chunks = []
    for row in results:
        chunks.append({
            "content": row[0],
            "page_number": row[1],
            "filename": row[2],
            "doc_type": row[3],
            "score": round(float(row[4]), 4)
        })
    return chunks

def answer_query(query: str, course_id: str = None) -> dict:
    """End-to-end RAG with context grounding and citation extraction."""
    retrieved = retrieve_chunks(query, course_id=course_id, top_k=4)

    if not retrieved or retrieved[0]["score"] < 0.25:
        return {
            "answer": "I cannot find this information in the uploaded course notes.",
            "sources": []
        }

    # Build Grounded Context
    context_blocks = []
    for i, c in enumerate(retrieved, start=1):
        context_blocks.append(
            f"[Source {i} | File: {c['filename']} | Page: {c['page_number']}]\n{c['content']}"
        )
    context_str = "\n\n".join(context_blocks)

    system_prompt = (
        "You are an academic teaching assistant. Your goal is to answer the student's question "
        "strictly based on the provided context below.\n"
        "Guidelines:\n"
        "1. Do not use outside knowledge or extrapolate beyond the facts given.\n"
        "2. If the context does not contain enough information to answer, state clearly: "
        "'I cannot find this information in the uploaded notes.'\n"
        "3. Explicitly cite the source file and page number when stating facts."
    )

    user_prompt = f"Context:\n{context_str}\n\nStudent Question: {query}"

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1
    )

    return {
        "answer": response.choices[0].message.content,
        "sources": retrieved
    }